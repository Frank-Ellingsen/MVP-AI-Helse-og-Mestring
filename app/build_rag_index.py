# app/build_rag_index.py
import os
import sys
import sqlite3
import pandas as pd
from pypdf import PdfReader

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Stier til data og database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "..", "data", "db")
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "..", "data", "knowledge_base")

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, "kommune_golden_record.db")


def init_db():
    print(f"-> Initialiserer SQLite databasen: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. RAG-tabell for ustrukturerte dokumentutdrag
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT,
            page INTEGER,
            content TEXT
        );
    """)

    # 2. ERP Transaksjonstabell for stg_erp_transactions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stg_erp_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bilagsnummer TEXT,
            dato TEXT,
            sektor TEXT,
            kommunalsjef_omrade TEXT,
            ansvar TEXT,
            enhet_navn TEXT,
            funksjon TEXT,
            funksjon_navn TEXT,
            artskonto TEXT,
            art_navn TEXT,
            leverandor_ansatt TEXT,
            beskrivelse TEXT,
            budsjett REAL,
            belop REAL
        );
    """)

    # Sørg for at nødvendige kolonner finnes selv om tabellen ble opprettet med eldre skjema
    cursor.execute("PRAGMA table_info(stg_erp_transactions);")
    existing_cols = {row[1] for row in cursor.fetchall()}
    required_cols = {
        "bilagsnummer": "TEXT",
        "dato": "TEXT",
        "sektor": "TEXT",
        "kommunalsjef_omrade": "TEXT",
        "ansvar": "TEXT",
        "enhet_navn": "TEXT",
        "funksjon": "TEXT",
        "funksjon_navn": "TEXT",
        "artskonto": "TEXT",
        "art_navn": "TEXT",
        "leverandor_ansatt": "TEXT",
        "beskrivelse": "TEXT",
        "budsjett": "REAL",
        "belop": "REAL",
    }
    for col_name, col_type in required_cols.items():
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE stg_erp_transactions ADD COLUMN {col_name} {col_type};")

    # tillat NULL på source_system dersom tabellen har eldre skjema
    # 3. Star Schema Dimensjons- og Faktatabeller (jf. star_schema_DDL.md)
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS dim_organisasjon (
            ansvar_id VARCHAR(10) PRIMARY KEY,
            ansvar_navn VARCHAR(100) NOT NULL,
            enhet_navn VARCHAR(100) NOT NULL,
            kommunalsjef_omrade VARCHAR(100) NOT NULL,
            sektor VARCHAR(100) NOT NULL DEFAULT 'Helse og Mestring',
            enhetsleder_ansatt_id VARCHAR(20),
            oppdatert_dato TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dim_kostra_kontoplan (
            art_id VARCHAR(10) PRIMARY KEY,
            art_navn VARCHAR(100) NOT NULL,
            artsgruppe VARCHAR(100) NOT NULL,
            funksjon_id VARCHAR(10) NOT NULL,
            funksjon_navn VARCHAR(100) NOT NULL,
            kontoklasse INT NOT NULL CHECK (kontoklasse IN (1, 2)),
            skjermet_for_kutt BOOLEAN DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS dim_tid (
            dato_key INT PRIMARY KEY,
            dato DATE NOT NULL,
            aar INT NOT NULL,
            periode INT NOT NULL CHECK (periode BETWEEN 1 AND 12),
            kvartal INT NOT NULL CHECK (kvartal BETWEEN 1 AND 4),
            tertial INT NOT NULL CHECK (tertial BETWEEN 1 AND 3)
        );

        CREATE TABLE IF NOT EXISTS dim_prosjekt_tiltak (
            prosjekt_id VARCHAR(20) PRIMARY KEY,
            prosjekt_navn VARCHAR(100) NOT NULL,
            prosjektleder_ansatt_id VARCHAR(20),
            omstillingskategori VARCHAR(50)
        );

        CREATE TABLE IF NOT EXISTS fact_erp_transactions (
            transaksjon_id VARCHAR(50) PRIMARY KEY,
            dato_key INT NOT NULL,
            ansvar_id VARCHAR(10) NOT NULL,
            art_id VARCHAR(10) NOT NULL,
            prosjekt_id VARCHAR(20) DEFAULT '0000',
            belop DECIMAL(15, 2) NOT NULL,
            bilagsnummer VARCHAR(30) NOT NULL,
            tekst_beskrivelse TEXT,
            kilde_system VARCHAR(20) DEFAULT 'Unit4 ERP',
            importert_dato TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dato_key) REFERENCES dim_tid(dato_key),
            FOREIGN KEY (ansvar_id) REFERENCES dim_organisasjon(ansvar_id),
            FOREIGN KEY (art_id) REFERENCES dim_kostra_kontoplan(art_id)
        );

        CREATE TABLE IF NOT EXISTS fact_budget_allocations (
            budsjett_id VARCHAR(50) PRIMARY KEY,
            aar INT NOT NULL,
            periode INT NOT NULL CHECK (periode BETWEEN 1 AND 12),
            ansvar_id VARCHAR(10) NOT NULL,
            art_id VARCHAR(10) NOT NULL,
            vedtatt_budsjett DECIMAL(15, 2) DEFAULT 0.00,
            regulert_budsjett DECIMAL(15, 2) DEFAULT 0.00,
            periodisert_budsjett DECIMAL(15, 2) DEFAULT 0.00,
            oppdatert_dato TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ansvar_id) REFERENCES dim_organisasjon(ansvar_id),
            FOREIGN KEY (art_id) REFERENCES dim_kostra_kontoplan(art_id)
        );

        CREATE TABLE IF NOT EXISTS sec_user_permissions (
            bruker_id VARCHAR(50) NOT NULL,
            rolle VARCHAR(30) NOT NULL,
            ansvar_id VARCHAR(10) NOT NULL,
            gyldig_fra DATE DEFAULT CURRENT_DATE,
            gyldig_til DATE,
            PRIMARY KEY (bruker_id, ansvar_id)
        );

        CREATE INDEX IF NOT EXISTS idx_erp_ansvar_art ON fact_erp_transactions(ansvar_id, art_id);
        CREATE INDEX IF NOT EXISTS idx_erp_dato ON fact_erp_transactions(dato_key);
        CREATE INDEX IF NOT EXISTS idx_budget_ansvar_periode ON fact_budget_allocations(ansvar_id, aar, periode);
        CREATE INDEX IF NOT EXISTS idx_rbac_bruker ON sec_user_permissions(bruker_id);
    """)

    conn.commit()
    conn.close()


def build_pdf_rag_index():
    print(f"-> Indekserer PDF-dokumenter fra {KNOWLEDGE_DIR}...")
    if not os.path.exists(KNOWLEDGE_DIR):
        print("Ingen knowledge_base mappe funnet.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT source_file FROM knowledge_chunks")
    already_indexed = {row[0] for row in cursor.fetchall()}

    for root, _, files in os.walk(KNOWLEDGE_DIR):
        for file in files:
            if file.lower().endswith(".pdf"):
                if file in already_indexed:
                    print(f"  [OK] Allerede indeksert PDF: {file}")
                    continue
                pdf_path = os.path.join(root, file)
                try:
                    reader = PdfReader(pdf_path)
                    for page_idx, page in enumerate(reader.pages):
                        text = page.extract_text()
                        if text and text.strip():
                            cursor.execute(
                                "INSERT INTO knowledge_chunks (source_file, page, content) VALUES (?, ?, ?)",
                                (file, page_idx + 1, text.strip()),
                            )
                    print(f"  [OK] Indeksert PDF: {file} ({len(reader.pages)} sider)")
                except Exception as e:
                    print(f"  [FEIL] Feil under lesing av {file}: {str(e)}")

    conn.commit()
    conn.close()


def populate_demo_erp_data():
    print("-> Genererer realistisk testdata for Helse og Mestring (stg_erp_transactions)...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Synkroniser eksisterende rader som mangler de nye kolonnene
    cursor.execute("PRAGMA table_info(stg_erp_transactions);")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "voucher_number" in existing_cols and "cost_center_code" in existing_cols:
        cursor.execute("""
            UPDATE stg_erp_transactions
            SET
                bilagsnummer = COALESCE(bilagsnummer, voucher_number),
                dato = COALESCE(dato, accounting_date),
                sektor = COALESCE(sektor, CASE WHEN cost_center_code = 'BOMILJO' THEN 'Helse og Mestring' WHEN cost_center_code = 'KOMSKOLE' THEN 'Oppvekst' ELSE 'Sentraladministrasjonen' END),
                kommunalsjef_omrade = COALESCE(kommunalsjef_omrade, CASE WHEN cost_center_code = 'BOMILJO' THEN 'Heldøgns omsorg' WHEN cost_center_code = 'KOMSKOLE' THEN 'Grunnskole' ELSE 'Stab og støtte' END),
                ansvar = COALESCE(ansvar, cost_center_code),
                enhet_navn = COALESCE(enhet_navn, CASE WHEN cost_center_code = 'BOMILJO' THEN 'Kommunal Boenhet (Bo- og Miljø)' WHEN cost_center_code = 'KOMSKOLE' THEN 'Kommunal Grunnskole' ELSE 'Sentraladministrasjonen' END),
                funksjon = COALESCE(funksjon, function_code),
                funksjon_navn = COALESCE(funksjon_navn, CASE WHEN function_code = '254' THEN 'Pleie i institusjon' WHEN function_code = '253' THEN 'Pleie og omsorg i hjemmet' ELSE 'Kommunal tjeneste' END),
                artskonto = COALESCE(artskonto, account_code),
                art_navn = COALESCE(art_navn, description),
                beskrivelse = COALESCE(beskrivelse, description),
                budsjett = COALESCE(budsjett, ROUND(amount * 0.92, 2)),
                belop = COALESCE(belop, amount)
            WHERE bilagsnummer IS NULL
        """)

    cursor.execute("DELETE FROM stg_erp_transactions WHERE bilagsnummer LIKE 'BIL-%'")

    demo_rows = [
        ("DEMO_ERP", "BIL-1001", "2026-08-15", "Helse og Mestring", "Heldøgns omsorg", "2530", "Randesund Omsorgssenter", "253", "Pleie i institusjon", "101000", "Fast lønn", "Ansatt 4012", "Lønnsutbetaling faste stillinger YTD", 12000000.0, 12150000.0),
        ("DEMO_ERP", "BIL-1002", "2026-08-18", "Helse og Mestring", "Heldøgns omsorg", "2530", "Randesund Omsorgssenter", "253", "Pleie i institusjon", "109000", "Overtid", "Ansatt 4012", "Helgedekning og beordret overtid", 400000.0, 1150000.0),
        ("DEMO_ERP", "BIL-1003", "2026-08-20", "Helse og Mestring", "Heldøgns omsorg", "2530", "Randesund Omsorgssenter", "253", "Pleie i institusjon", "110000", "Innleie/Vikarer", "Adecco Helse AS", "Sykefraværsvikarer døgnpleie", 300000.0, 850000.0),
        ("DEMO_ERP", "BIL-1010", "2026-08-21", "Helse og Mestring", "Heldøgns omsorg", "2530", "Randesund Omsorgssenter", "253", "Pleie i institusjon", "169000", "Refusjoner NAV", "NAV Innkreving", "Mottatt sykelønnsrefusjon (etterslep 300k)", -800000.0, -500000.0),
        ("DEMO_ERP", "BIL-1004", "2026-08-22", "Helse og Mestring", "Hjemmebaserte tjenester", "2580", "Hjemmetjenesten Vågsbygd", "258", "Ambulerende hjemmetjeneste", "101000", "Fast lønn", "Ansatt 5110", "Fastlønn hjemmesykepleie YTD", 9600000.0, 9680000.0),
        ("DEMO_ERP", "BIL-1005", "2026-08-25", "Helse og Mestring", "Hjemmebaserte tjenester", "2580", "Hjemmetjenesten Vågsbygd", "258", "Ambulerende hjemmetjeneste", "109000", "Overtid", "Ansatt 5110", "Ekstraomganger sommeravvikling", 240000.0, 690000.0),
        ("DEMO_ERP", "BIL-1006", "2026-08-28", "Helse og Mestring", "Mestring og helse", "2330", "Mestringsenheten", "233", "Forebyggende helse", "169000", "Refusjoner NAV", "NAV Innkreving", "Sykelønnsrefusjon Q2", -400000.0, -460000.0),
        ("DEMO_ERP", "BIL-1007", "2026-08-28", "Helse og Mestring", "Mestring og helse", "2330", "Mestringsenheten", "233", "Forebyggende helse", "101000", "Fast lønn", "Ansatt 6020", "Fastlønn forebyggende team YTD", 6800000.0, 6690000.0),
        ("DEMO_ERP", "BIL-1008", "2026-08-28", "Helse og Mestring", "Heldøgns omsorg", "2540", "Strømmehaven", "253", "Pleie i institusjon", "101000", "Fast lønn", "Ansatt 4501", "Fastlønn døgnomsorg YTD", 11200000.0, 11340000.0),
        ("DEMO_ERP", "BIL-1009", "2026-08-29", "Helse og Mestring", "Heldøgns omsorg", "2540", "Strømmehaven", "253", "Pleie i institusjon", "109000", "Overtid", "Ansatt 4501", "Helgeovertid YTD", 360000.0, 620000.0),
    ]

    if "source_system" in existing_cols:
        cursor.executemany("""
            INSERT INTO stg_erp_transactions (
                source_system, bilagsnummer, dato, sektor, kommunalsjef_omrade, ansvar, enhet_navn,
                funksjon, funksjon_navn, artskonto, art_navn, leverandor_ansatt, beskrivelse, budsjett, belop
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, demo_rows)
    else:
        cursor.executemany("""
            INSERT INTO stg_erp_transactions (
                bilagsnummer, dato, sektor, kommunalsjef_omrade, ansvar, enhet_navn,
                funksjon, funksjon_navn, artskonto, art_navn, leverandor_ansatt, beskrivelse, budsjett, belop
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [r[1:] for r in demo_rows])

    print("  [OK] Synkroniserte YTD M8 ERP-transaksjoner for test.")

    # Synkroniser Star Schema-tabeller (dim_organisasjon, dim_kostra_kontoplan, fact_erp_transactions, fact_budget_allocations, sec_user_permissions)
    org_rows = [
        ("2530", "Randesund Omsorgssenter", "Randesund Omsorgssenter", "Heldøgns omsorg", "Helse og Mestring", "LED-2530"),
        ("2580", "Hjemmetjenesten Vågsbygd", "Hjemmetjenesten Vågsbygd", "Hjemmebaserte tjenester", "Helse og Mestring", "LED-2580"),
        ("2540", "Strømmehaven", "Strømmehaven", "Heldøgns omsorg", "Helse og Mestring", "LED-2540"),
        ("2330", "Mestringsenheten", "Mestringsenheten", "Mestring og helse", "Helse og Mestring", "LED-2330"),
    ]
    cursor.executemany("""
        INSERT OR REPLACE INTO dim_organisasjon (
            ansvar_id, ansvar_navn, enhet_navn, kommunalsjef_omrade, sektor, enhetsleder_ansatt_id
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, org_rows)

    kostra_rows = [
        ("101000", "Fast lønn", "Lønn og sosiale utgifter", "253", "Pleie og omsorg", 1, 1),
        ("109000", "Overtid", "Lønn og sosiale utgifter", "253", "Pleie og omsorg", 1, 0),
        ("110000", "Innleie/Vikarer", "Lønn og sosiale utgifter", "253", "Pleie og omsorg", 1, 0),
        ("169000", "Sykelønnsrefusjon NAV", "Refusjoner og overføringer", "253", "Pleie og omsorg", 1, 0),
    ]
    cursor.executemany("""
        INSERT OR REPLACE INTO dim_kostra_kontoplan (
            art_id, art_navn, artsgruppe, funksjon_id, funksjon_navn, kontoklasse, skjermet_for_kutt
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, kostra_rows)

    tid_rows = [
        (20260815, "2026-08-15", 2026, 8, 3, 2),
        (20260818, "2026-08-18", 2026, 8, 3, 2),
        (20260820, "2026-08-20", 2026, 8, 3, 2),
        (20260821, "2026-08-21", 2026, 8, 3, 2),
        (20260822, "2026-08-22", 2026, 8, 3, 2),
        (20260825, "2026-08-25", 2026, 8, 3, 2),
        (20260828, "2026-08-28", 2026, 8, 3, 2),
        (20260829, "2026-08-29", 2026, 8, 3, 2),
    ]
    cursor.executemany("""
        INSERT OR REPLACE INTO dim_tid (dato_key, dato, aar, periode, kvartal, tertial)
        VALUES (?, ?, ?, ?, ?, ?)
    """, tid_rows)

    fact_rows = [
        ("TX-1001", 20260815, "2530", "101000", "0000", 12150000.0, "BIL-1001", "Lønnsutbetaling faste stillinger YTD", "Unit4 ERP"),
        ("TX-1002", 20260818, "2530", "109000", "TORN-01", 1150000.0, "BIL-1002", "Helgedekning og beordret overtid", "Unit4 ERP"),
        ("TX-1003", 20260820, "2530", "110000", "TORN-01", 850000.0, "BIL-1003", "Sykefraværsvikarer døgnpleie", "Unit4 ERP"),
        ("TX-1010", 20260821, "2530", "169000", "0000", -500000.0, "BIL-1010", "Mottatt sykelønnsrefusjon (etterslep 300k)", "Unit4 ERP"),
        ("TX-1004", 20260822, "2580", "101000", "0000", 9680000.0, "BIL-1004", "Fastlønn hjemmesykepleie YTD", "Unit4 ERP"),
        ("TX-1005", 20260825, "2580", "109000", "TORN-02", 690000.0, "BIL-1005", "Ekstraomganger sommeravvikling", "Unit4 ERP"),
        ("TX-1006", 20260828, "2330", "169000", "0000", -460000.0, "BIL-1006", "Sykelønnsrefusjon Q2", "Unit4 ERP"),
        ("TX-1007", 20260828, "2330", "101000", "0000", 6690000.0, "BIL-1007", "Fastlønn forebyggende team YTD", "Unit4 ERP"),
        ("TX-1008", 20260828, "2540", "101000", "0000", 11340000.0, "BIL-1008", "Fastlønn døgnomsorg YTD", "Unit4 ERP"),
        ("TX-1009", 20260829, "2540", "109000", "TORN-01", 620000.0, "BIL-1009", "Helgeovertid YTD", "Unit4 ERP"),
    ]
    cursor.executemany("""
        INSERT OR REPLACE INTO fact_erp_transactions (
            transaksjon_id, dato_key, ansvar_id, art_id, prosjekt_id, belop, bilagsnummer, tekst_beskrivelse, kilde_system
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, fact_rows)

    budget_rows = [
        ("BUD-2530-101000", 2026, 8, "2530", "101000", 18000000.0, 18000000.0, 12000000.0),
        ("BUD-2530-109000", 2026, 8, "2530", "109000", 600000.0, 600000.0, 400000.0),
        ("BUD-2530-110000", 2026, 8, "2530", "110000", 450000.0, 450000.0, 300000.0),
        ("BUD-2530-169000", 2026, 8, "2530", "169000", -1200000.0, -1200000.0, -800000.0),
        ("BUD-2580-101000", 2026, 8, "2580", "101000", 14400000.0, 14400000.0, 9600000.0),
        ("BUD-2580-109000", 2026, 8, "2580", "109000", 360000.0, 360000.0, 240000.0),
        ("BUD-2330-101000", 2026, 8, "2330", "101000", 10200000.0, 10200000.0, 6800000.0),
        ("BUD-2330-169000", 2026, 8, "2330", "169000", -600000.0, -600000.0, -400000.0),
        ("BUD-2540-101000", 2026, 8, "2540", "101000", 16800000.0, 16800000.0, 11200000.0),
        ("BUD-2540-109000", 2026, 8, "2540", "109000", 540000.0, 540000.0, 360000.0),
    ]
    cursor.executemany("""
        INSERT OR REPLACE INTO fact_budget_allocations (
            budsjett_id, aar, periode, ansvar_id, art_id, vedtatt_budsjett, regulert_budsjett, periodisert_budsjett
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, budget_rows)

    rbac_rows = [
        ("enhetsleder@kristiansand.kommune.no", "enhetsleder", "2530"),
        ("kommunalsjef@kristiansand.kommune.no", "kommunalsjef", "*"),
        ("frank.ellingsen@kristiansand.kommune.no", "direktor", "*"),
        ("revisor@kristiansand.kommune.no", "revisor", "*"),
    ]
    cursor.executemany("""
        INSERT OR REPLACE INTO sec_user_permissions (bruker_id, rolle, ansvar_id)
        VALUES (?, ?, ?)
    """, rbac_rows)
    print("  [OK] Synkroniserte Star Schema (dim_organisasjon, dim_kostra_kontoplan, fact_erp_transactions, fact_budget_allocations, sec_user_permissions).")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    build_pdf_rag_index()
    populate_demo_erp_data()
    print("=== Databasen er ferdig opprettet og klar til bruk! ===")
