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

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    build_pdf_rag_index()
    populate_demo_erp_data()
    print("=== Databasen er ferdig opprettet og klar til bruk! ===")
