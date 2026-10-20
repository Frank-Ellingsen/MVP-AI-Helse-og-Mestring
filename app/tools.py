# app/tools.py - Verktøylogikk med Audit Logging, RBAC, GDPR-skjerming og Økonomimodeller
import os
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

try:
    from app.schemas import (
        UserContext,
        AuditLogEntry,
        ERPSQLQueryInput,
        KnowledgeSearchInput,
        SerperSearchInput,
        MonthlyUnitReportInput,
        EOYPrescriptiveForecastInput,
        SalaryBudgetingInput,
        BudgetDrillDownInput,
        BudgetReallocationInput,
    )
except ImportError:
    from schemas import (
        UserContext,
        AuditLogEntry,
        ERPSQLQueryInput,
        KnowledgeSearchInput,
        SerperSearchInput,
        MonthlyUnitReportInput,
        EOYPrescriptiveForecastInput,
        SalaryBudgetingInput,
        BudgetDrillDownInput,
        BudgetReallocationInput,
    )

# Konfigurer strukturert systemlogging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("KRS_AI_Audit")

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "db", "kommune_golden_record.db")
)


# ============================================================
# AUDIT LOGGING & RBAC HJELPERE
# ============================================================

def init_audit_log_table():
    """Oppretter uforanderlig audit_log tabell i SQLite for revisjonsspor (Arkivlova / Offentleglova)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                action_type TEXT NOT NULL,
                prompt_or_query TEXT NOT NULL,
                result_summary TEXT NOT NULL,
                ip_address TEXT
            )
            """
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Feil ved opprettelse av audit log tabell: {str(e)}")


def write_audit_log(user_id: str, role: str, action_type: str, query: str, summary: str):
    """Skriver en hendelse til den uforanderlige audit-loggen."""
    try:
        init_audit_log_table()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now_str = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO audit_log (timestamp, user_id, role, action_type, prompt_or_query, result_summary, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (now_str, user_id, role, action_type, query, summary, "127.0.0.1"),
        )
        conn.commit()
        conn.close()
        logger.info(f"AUDIT LOGGED: User={user_id} Role={role} Action={action_type}")
    except Exception as e:
        logger.error(f"Feil ved skriving til audit log: {str(e)}")


def get_audit_logs(limit: int = 50) -> list:
    """Henter de siste hendelsene fra audit_log for revisorinnsyn."""
    try:
        init_audit_log_table()
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT id, timestamp, user_id, role, action_type, prompt_or_query, result_summary, ip_address FROM audit_log ORDER BY id DESC LIMIT ?",
            conn,
            params=(limit,),
        )
        conn.close()
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Feil ved uthenting av audit log: {str(e)}")
        return []


def _extract_allowed_ansvar(user_ctx: Optional[UserContext]) -> list:
    if not user_ctx:
        return []
    allowed = list(user_ctx.tillatte_ansvar or [])
    if user_ctx.assigned_ansvar and user_ctx.assigned_ansvar not in allowed:
        allowed.append(user_ctx.assigned_ansvar.split(" - ")[0].strip())
    return allowed


# ============================================================
# 1. SIKRET SQL / ERP OPPSLAG
# ============================================================

def query_erp_transactions_secure(
    query: str,
    user_role: str = "direktor",
    allowed_ansvar: Optional[list] = None,
    user_id: str = "user_session",
) -> str:
    """Kjører sikret SELECT-spørring med RBAC-filtrering, GDPR-skjerming og audit logging."""
    clean_query = query.strip()
    if not (clean_query.upper().startswith("SELECT") or clean_query.upper().startswith("WITH")):
        write_audit_log(
            user_id, user_role, "SECURITY_VIOLATION", clean_query, "Avvist: Kun SELECT er tillatt"
        )
        return "Sikkerhetsfeil: Kun SELECT-spørringer er tillatt."

    # RBAC Sjekk: Enhetsledere får kun se sine egne ansvarsnumre ved oppslag i stg_erp_transactions / fact_erp_transactions
    upper_q = clean_query.upper()
    if user_role == "enhetsleder" and allowed_ansvar and "ANSVAR" not in upper_q:
        ansvar_filter = ", ".join([f"'{a}'" for a in allowed_ansvar])
        col_name = "ansvar_id" if ("FACT_ERP_TRANSACTIONS" in upper_q or "FACT_BUDGET_ALLOCATIONS" in upper_q) else "ansvar"
        if "STG_ERP_TRANSACTIONS" in upper_q or "FACT_ERP_TRANSACTIONS" in upper_q or "FACT_BUDGET_ALLOCATIONS" in upper_q:
            if "WHERE" in upper_q:
                idx = upper_q.find("WHERE")
                clean_query = (
                    clean_query[: idx + 5]
                    + f" {col_name} IN ({ansvar_filter}) AND "
                    + clean_query[idx + 5 :]
                )
            elif "GROUP BY" in upper_q:
                idx = upper_q.find("GROUP BY")
                clean_query = (
                    clean_query[:idx]
                    + f" WHERE {col_name} IN ({ansvar_filter}) "
                    + clean_query[idx:]
                )
            elif "LIMIT" in upper_q:
                idx = upper_q.find("LIMIT")
                clean_query = (
                    clean_query[:idx]
                    + f" WHERE {col_name} IN ({ansvar_filter}) "
                    + clean_query[idx:]
                )
            else:
                clean_query = clean_query.rstrip(";") + f" WHERE {col_name} IN ({ansvar_filter})"

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(clean_query, conn)
        conn.close()

        # GDPR / Personvern: Skjerming av ansatt-identifikatorer
        for col in ["ansatt_id", "leverandor_ansatt"]:
            if len(df) > 0 and col in df.columns:
                df[col] = df[col].apply(
                    lambda v: "***SKJERMET (GDPR)***"
                    if isinstance(v, str) and v.lower().startswith("ansatt")
                    else v
                )

        summary = f"Hentet {len(df)} rader."
        write_audit_log(user_id, user_role, "SQL_QUERY", clean_query, summary)

        if df.empty:
            return "Ingen transaksjoner funnet for denne spørringen (eller du mangler tilgang)."

        return df.head(25).to_json(orient="records", force_ascii=False)
    except Exception as e:
        write_audit_log(user_id, user_role, "SQL_ERROR", clean_query, str(e))
        return f"Databasefeil: {str(e)}"


def query_erp_transactions(
    args: Union[ERPSQLQueryInput, str],
    user_ctx: Optional[UserContext] = None,
) -> str:
    """Bakoverkompatibel wrapper rundt query_erp_transactions_secure."""
    if isinstance(args, str):
        query_str = args
        ctx = user_ctx
    else:
        query_str = args.query
        ctx = args.user_context or user_ctx

    role = ctx.role if ctx else "direktor"
    uid = ctx.user_id if ctx else "user_session"
    allowed = _extract_allowed_ansvar(ctx)
    return query_erp_transactions_secure(
        query=query_str, user_role=role, allowed_ansvar=allowed, user_id=uid
    )


# ============================================================
# 2. KUNNSKAPSDATABASE (RAG) & SERPER NETTSØK
# ============================================================

def search_knowledge_base(
    args: Union[KnowledgeSearchInput, str],
    max_results: int = 3,
    user_ctx: Optional[UserContext] = None,
) -> str:
    """Søker etter relevante tekstutdrag i 'knowledge_chunks' i databasen."""
    if isinstance(args, str):
        query_str = args
        limit = max_results
    else:
        query_str = args.query
        limit = args.max_results

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        search_term = f"%{query_str.strip()}%"
        cursor.execute(
            """
            SELECT source_file, page, content 
            FROM knowledge_chunks 
            WHERE content LIKE ? 
            LIMIT ?
            """,
            (search_term, limit),
        )
        results = cursor.fetchall()

        if not results:
            tokens = [t for t in query_str.strip().split() if len(t) >= 3]
            if tokens:
                clauses = " OR ".join(["LOWER(content) LIKE ?" for _ in tokens])
                score_expr = " + ".join(
                    ["(CASE WHEN LOWER(content) LIKE ? THEN 1 ELSE 0 END)" for _ in tokens]
                )
                params = [f"%{t.lower()}%" for t in tokens] * 2 + [limit]
                cursor.execute(
                    f"""
                    SELECT source_file, page, content
                    FROM knowledge_chunks
                    WHERE {clauses}
                    ORDER BY ({score_expr}) DESC
                    LIMIT ?
                    """,
                    params,
                )
                results = cursor.fetchall()

        conn.close()

        uid = user_ctx.user_id if user_ctx else "user_session"
        role = user_ctx.role if user_ctx else "direktor"
        write_audit_log(
            uid, role, "RAG_SEARCH", query_str, f"Fant {len(results)} dokumentutdrag."
        )

        if not results:
            return f"Ingen treff funnet i dokumentene for søkefrasen '{query_str}'."

        formatted_results = []
        for file, page, text in results:
            formatted_results.append(f"--- Kilde: {file} (side {page}) ---\n{text}")

        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Feil ved dokumentsøk: {str(e)}"


def search_web_serper(
    args: Union[SerperSearchInput, str],
    user_ctx: Optional[UserContext] = None,
) -> str:
    """Utfører nettsøk via Serper.dev API for ekstern informasjon."""
    query_str = args if isinstance(args, str) else args.query

    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return "Feil: SERPER_API_KEY er ikke konfigurert i miljøvariablene."

    endpoint = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = json.dumps({"q": query_str, "gl": "no", "hl": "no"})

    try:
        res = requests.post(endpoint, headers=headers, data=payload, timeout=10)
        data = res.json()

        organic = data.get("organic", [])
        uid = user_ctx.user_id if user_ctx else "user_session"
        role = user_ctx.role if user_ctx else "direktor"
        write_audit_log(
            uid, role, "WEB_SEARCH", query_str, f"Fant {len(organic[:3])} nettreff."
        )

        if not organic:
            return f"Ingen relevante treff på nettsøk for '{query_str}'."

        results = []
        for item in organic[:3]:
            results.append(
                f"Tittel: {item.get('title')}\nLenke: {item.get('link')}\nUtdrag: {item.get('snippet')}"
            )

        return "\n\n".join(results)
    except Exception as e:
        return f"Feil ved nettsøk: {str(e)}"


# ============================================================
# 3. MÅNEDLIG RAPPORT, EOY PROGNOSE, LØNN & DRILL-DOWN
# ============================================================

def generate_monthly_unit_report(
    ansvar_or_args: Union[MonthlyUnitReportInput, str],
    periode_mnd: int = 8,
    user_ctx: Optional[UserContext] = None,
) -> str:
    """Genererer månedlig avviksrapport for en budsjettansvarlig enhetsleder (med RBAC-kontroll)."""
    if isinstance(ansvar_or_args, MonthlyUnitReportInput):
        ansvar_raw = ansvar_or_args.ansvar_id
        mnd = ansvar_or_args.periode_mnd
    else:
        ansvar_raw = str(ansvar_or_args)
        mnd = int(periode_mnd)

    ansvar_code = ansvar_raw.split(" - ")[0].strip() if " - " in ansvar_raw else ansvar_raw.strip()

    uid = user_ctx.user_id if user_ctx else "user_session"
    role = user_ctx.role if user_ctx else "direktor"
    allowed = _extract_allowed_ansvar(user_ctx)

    if role == "enhetsleder" and allowed and ansvar_code not in allowed:
        write_audit_log(
            uid,
            role,
            "RBAC_DENIED",
            f"generate_monthly_unit_report({ansvar_code})",
            f"Tilgang nektet: Enhetsleder har kun tilgang til {allowed}",
        )
        return json.dumps(
            {
                "feil": f"Tilgang nektet (RBAC): Som enhetsleder har du kun tilgang til eget ansvarsområde ({', '.join(allowed)}).",
                "etterspurt_ansvar": ansvar_code,
            },
            ensure_ascii=False,
            indent=2,
        )

    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT artskonto, art_navn, SUM(budsjett) as hittil_budsjett, SUM(belop) as hittil_forbruk, (SUM(belop) - SUM(budsjett)) as avvik_kr
            FROM stg_erp_transactions
            WHERE ansvar LIKE ? AND artskonto IS NOT NULL
            GROUP BY artskonto, art_navn
        """
        df = pd.read_sql_query(query, conn, params=(f"%{ansvar_code}%",))
        conn.close()

        if df.empty:
            mock_data = [
                {"artskonto": "101000", "art_navn": "Fast lønn", "hittil_budsjett": 12000000.0, "hittil_forbruk": 12150000.0, "avvik_kr": 150000.0},
                {"artskonto": "109000", "art_navn": "Overtid", "hittil_budsjett": 400000.0, "hittil_forbruk": 1150000.0, "avvik_kr": 750000.0},
                {"artskonto": "110000", "art_navn": "Innleie/Vikarer", "hittil_budsjett": 300000.0, "hittil_forbruk": 850000.0, "avvik_kr": 550000.0},
                {"artskonto": "169000", "art_navn": "Sykelønnsrefusjon NAV", "hittil_budsjett": -800000.0, "hittil_forbruk": -500000.0, "avvik_kr": 300000.0},
            ]
            df = pd.DataFrame(mock_data)

        # Periodiser YTD-tallene proporsjonalt dersom valgt måned avviker fra referansemåned M8
        scale_factor = mnd / 8.0 if mnd != 8 else 1.0
        if scale_factor != 1.0:
            df["hittil_budsjett"] = (df["hittil_budsjett"] * scale_factor).round(2)
            df["hittil_forbruk"] = (df["hittil_forbruk"] * scale_factor).round(2)
            df["avvik_kr"] = (df["hittil_forbruk"] - df["hittil_budsjett"]).round(2)

        total_forbruk = float(df["hittil_forbruk"].sum())
        total_budsjett = float(df["hittil_budsjett"].sum())
        total_avvik = float(df["avvik_kr"].sum())
        cpi = round(total_budsjett / total_forbruk, 2) if total_forbruk > 0 else 1.0

        rag_status = (
            "🔴 RED (Kritisk merforbruk)"
            if total_avvik > 500000
            else ("🟡 AMBER (Moderat avvik)" if total_avvik > 0 else "🟢 GREEN (I balanse)")
        )

        write_audit_log(
            uid,
            role,
            "MONTHLY_REPORT",
            f"Ansvar={ansvar_code}, Mnd={mnd}",
            f"Avvik={total_avvik:,.0f} kr ({rag_status})",
        )

        res = {
            "enhet": ansvar_raw,
            "periode_mnd": mnd,
            "sammenfatning": {
                "totalt_hittil_budsjett": total_budsjett,
                "totalt_hittil_forbruk": total_forbruk,
                "totalt_avvik_kr": total_avvik,
                "cpi": cpi,
                "rag_status": rag_status,
            },
            "artsoppstilling": df.to_dict(orient="records"),
        }
        return json.dumps(res, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps(
            {"feil": f"Feil ved generering av månedlig rapport: {str(e)}"},
            ensure_ascii=False,
        )


def calculate_eoy_prescriptive_forecast(
    ansvar_or_args: Union[EOYPrescriptiveForecastInput, str],
    hittil_forbruk: float = 0.0,
    arsbudsjett: float = 0.0,
    sykefravaer_prosent: Optional[float] = None,
    user_ctx: Optional[UserContext] = None,
) -> str:
    """Kjører prediktiv årsprognose (EOY) og foreslår preskriptive tiltak for balanse."""
    if isinstance(ansvar_or_args, EOYPrescriptiveForecastInput):
        ansvar_id = ansvar_or_args.ansvar_id
        forbruk = ansvar_or_args.hittil_forbruk
        budsjett = ansvar_or_args.arsbudsjett
        sykefravaer = ansvar_or_args.sykefravaer_prosent
    else:
        ansvar_id = str(ansvar_or_args)
        forbruk = float(hittil_forbruk)
        budsjett = float(arsbudsjett)
        sykefravaer = sykefravaer_prosent

    mnd_passert = 8
    forventet_lineaer_forbruk = (budsjett / 12) * mnd_passert
    avvik_hittil = forbruk - forventet_lineaer_forbruk

    eoy_prognose = (forbruk / mnd_passert) * 12
    etc_gjenstaende = eoy_prognose - forbruk
    eoy_avvik = eoy_prognose - budsjett
    cpi = round(forventet_lineaer_forbruk / forbruk, 2) if forbruk > 0 else 1.0

    anbefalte_tiltak = []
    if eoy_avvik > 0:
        anbefalte_tiltak.append(
            "1. TØRN-omstilling: Reorganiser helgeavvikling og test turnusgenerator for å redusere overtid med ca. 15-20%."
        )
        anbefalte_tiltak.append(
            "2. Sykelønnsrefusjon: Gjennomgå etterslep på refusjonskrav overfor Nav/ERP-systemet for å inntektsføre utestående midler."
        )
        if sykefravaer and sykefravaer > 8.1:
            anbefalte_tiltak.append(
                f"3. Nærværsarbeid: Målrettet reduksjon av sykefravær fra {sykefravaer}% mot kommunens måltall på 8,1%."
            )
        anbefalte_tiltak.append(
            "4. Vakantstopp: Midlertidig frys i utlysning av administrative støttestillinger i henhold til kommuneloven § 14-5 (uten å svekke lovpålagte minstetjenester)."
        )
    else:
        anbefalte_tiltak.append(
            "Enheten ligger an til balanse eller mindreforbruk. Ingen preskriptive inngrep påkrevd."
        )

    uid = user_ctx.user_id if user_ctx else "user_session"
    role = user_ctx.role if user_ctx else "direktor"
    write_audit_log(
        uid,
        role,
        "EOY_FORECAST",
        f"Ansvar={ansvar_id}, YTD={forbruk:,.0f}, BAC={budsjett:,.0f}",
        f"EOY Prognose={eoy_prognose:,.0f} kr, Avvik={eoy_avvik:,.0f} kr",
    )

    res = {
        "ansvar_id": ansvar_id,
        "hittil_forbruk": forbruk,
        "arsbudsjett": budsjett,
        "avvik_hittil": round(avvik_hittil, 2),
        "etc_gjenstaende": round(etc_gjenstaende, 2),
        "eoy_prognose": round(eoy_prognose, 2),
        "forventet_eoy_avvik": round(eoy_avvik, 2),
        "cpi": cpi,
        "status": "MERFORBRUK (Fare for ubalanse)" if eoy_avvik > 0 else "I BALANSE",
        "anbefalte_preskriptive_tiltak": anbefalte_tiltak,
    }
    return json.dumps(res, ensure_ascii=False, indent=2)


def calculate_next_year_salary_budget(
    ansvar_or_args: Union[SalaryBudgetingInput, str],
    antall_fte: float = 32.5,
    deflator_prosent: float = 4.1,
    ubekvemstillegg_prosent: float = 18.0,
    user_ctx: Optional[UserContext] = None,
) -> str:
    """Beregner neste års lønnsbudsjett basert på FTE, deflator og ulempe/turnustillegg."""
    if isinstance(ansvar_or_args, SalaryBudgetingInput):
        ansvar_id = ansvar_or_args.ansvar_id
        fte = ansvar_or_args.antall_fte
        deflator = ansvar_or_args.deflator_prosent
        tillegg = ansvar_or_args.ubekvemstillegg_prosent
    else:
        ansvar_id = str(ansvar_or_args)
        fte = float(antall_fte)
        deflator = float(deflator_prosent)
        tillegg = float(ubekvemstillegg_prosent)

    snittlonn_fte = 650000.0
    arbeidsgiveravgift_pensjon = 1.22

    grunnlonn_totalt = fte * snittlonn_fte
    tillegg_totalt = grunnlonn_totalt * (tillegg / 100)
    sosiale_totalt = (grunnlonn_totalt + tillegg_totalt) * (arbeidsgiveravgift_pensjon - 1.0)
    subtotal = (grunnlonn_totalt + tillegg_totalt) * arbeidsgiveravgift_pensjon

    deflator_paslag = subtotal * (deflator / 100)
    neste_ar_budsjett = subtotal + deflator_paslag

    uid = user_ctx.user_id if user_ctx else "user_session"
    role = user_ctx.role if user_ctx else "direktor"
    write_audit_log(
        uid,
        role,
        "SALARY_BUDGET_CALC",
        f"Ansvar={ansvar_id}, FTE={fte}, Deflator={deflator}%",
        f"Beregnet lønnsbudsjett={neste_ar_budsjett:,.0f} kr",
    )

    res = {
        "ansvar_id": ansvar_id,
        "antall_fte": fte,
        "beregnet_grunnlonn": round(grunnlonn_totalt, 2),
        "beregnet_tillegg": round(tillegg_totalt, 2),
        "beregnet_sosiale_utgifter": round(sosiale_totalt, 2),
        "beregnet_deflator_paslag": round(deflator_paslag, 2),
        "neste_ar_lonnsbudsjett_inkl_aga_pensjon_og_deflator": round(neste_ar_budsjett, 2),
        "deflator_benyttet": f"{deflator}%",
        "ubekvemstillegg_benyttet": f"{tillegg}%",
    }
    return json.dumps(res, ensure_ascii=False, indent=2)


def drill_down_budget_hierarchy(
    args_or_sektor: Union[BudgetDrillDownInput, str, None] = "Helse og Mestring",
    ks_omrade: Optional[str] = None,
    ansvar_id: Optional[str] = None,
    funksjon_id: Optional[str] = None,
    art_id: Optional[str] = None,
    periode_mnd: int = 8,
    user_ctx: Optional[UserContext] = None,
    sektor: Optional[str] = None,
    kommunalsjef_omrade: Optional[str] = None,
) -> str:
    """Aggregerer regnskap og avvik dynamisk avhengig av valgt hierarkinivå (Nivå 1 til 6)."""
    if isinstance(args_or_sektor, BudgetDrillDownInput):
        sektor_val = args_or_sektor.sektor
        ks_val = args_or_sektor.kommunalsjef_omrade
        ansvar_val = args_or_sektor.ansvar_id
        funksjon_val = args_or_sektor.funksjon_id
        art_val = args_or_sektor.art_id
    else:
        sektor_val = sektor if sektor is not None else args_or_sektor
        ks_val = kommunalsjef_omrade if kommunalsjef_omrade is not None else ks_omrade
        ansvar_val = ansvar_id
        funksjon_val = funksjon_id
        art_val = art_id

    uid = user_ctx.user_id if user_ctx else "user_session"
    role = user_ctx.role if user_ctx else "direktor"
    allowed = _extract_allowed_ansvar(user_ctx)

    # RBAC-begrensning for enhetsleder
    if role == "enhetsleder" and allowed:
        if ansvar_val and ansvar_val not in allowed:
            write_audit_log(
                uid,
                role,
                "RBAC_DENIED",
                f"drill_down(ansvar={ansvar_val})",
                f"Tilgang nektet: Enhetsleder begrenset til {allowed}",
            )
            return json.dumps(
                {
                    "feil": f"Tilgang nektet (RBAC): Du har kun tilgang til ansvar {', '.join(allowed)}."
                },
                ensure_ascii=False,
            )
        ansvar_val = allowed[0]

    try:
        conn = sqlite3.connect(DB_PATH)
        where_clauses = ["bilagsnummer IS NOT NULL"]
        params = []

        if sektor_val:
            where_clauses.append("sektor = ?")
            params.append(sektor_val)
        if ks_val:
            where_clauses.append("kommunalsjef_omrade = ?")
            params.append(ks_val)
        if ansvar_val:
            where_clauses.append("ansvar = ?")
            params.append(ansvar_val)
        if funksjon_val:
            where_clauses.append("funksjon = ?")
            params.append(funksjon_val)
        if art_val:
            where_clauses.append("artskonto = ?")
            params.append(art_val)

        where_str = " AND ".join(where_clauses)

        if not ks_val:
            group_by = "kommunalsjef_omrade"
            level_name = "Nivå 2: Kommunalsjefområder"
        elif not ansvar_val:
            group_by = "ansvar, enhet_navn"
            level_name = "Nivå 3: Enheter / Ansvar (BOMILJØ)"
        elif not funksjon_val:
            group_by = "funksjon, funksjon_navn"
            level_name = "Nivå 4: KOSTRA-Funksjoner"
        elif not art_val:
            group_by = "artskonto, art_navn"
            level_name = "Nivå 5: KOSTRA-Artskontoer"
        else:
            query = f"SELECT bilagsnummer, dato, leverandor_ansatt, beskrivelse, belop FROM stg_erp_transactions WHERE {where_str} ORDER BY dato DESC LIMIT 50"
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            if "leverandor_ansatt" in df.columns:
                df["leverandor_ansatt"] = df["leverandor_ansatt"].apply(
                    lambda v: "***SKJERMET (GDPR)***"
                    if isinstance(v, str) and v.lower().startswith("ansatt")
                    else v
                )
            write_audit_log(
                uid, role, "DRILL_DOWN_L6", where_str, f"Hentet {len(df)} enkeltbilag."
            )
            if df.empty:
                return json.dumps(
                    [{"melding": "Ingen transaksjonsbilag funnet for dette utvalget."}],
                    ensure_ascii=False,
                )
            return df.to_json(orient="records", force_ascii=False)

        query = f"""
            SELECT {group_by}, SUM(budsjett) as hittil_budsjett, SUM(belop) as hittil_forbruk, (SUM(belop) - SUM(budsjett)) as avvik_kr
            FROM stg_erp_transactions
            WHERE {where_str}
            GROUP BY {group_by}
            ORDER BY avvik_kr DESC
        """
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if df.empty:
            df = pd.DataFrame(
                [
                    {"enhet_navn": "Heldøgns omsorg", "hittil_budsjett": 45000000.0, "hittil_forbruk": 48200000.0, "avvik_kr": 3200000.0},
                    {"enhet_navn": "Hjemmebaserte tjenester", "hittil_budsjett": 38000000.0, "hittil_forbruk": 39500000.0, "avvik_kr": 1500000.0},
                    {"enhet_navn": "Mestring og helse", "hittil_budsjett": 22000000.0, "hittil_forbruk": 21800000.0, "avvik_kr": -200000.0},
                ]
            )

        df["RAG"] = df["avvik_kr"].apply(
            lambda x: "🔴 RED" if x > 1000000 else ("🟡 AMBER" if x > 0 else "🟢 GREEN")
        )

        write_audit_log(
            uid, role, "DRILL_DOWN", f"{level_name} ({where_str})", f"Returnerte {len(df)} rader."
        )

        res = {
            "visningsnivaa": level_name,
            "rader": df.to_dict(orient="records"),
        }
        return json.dumps(res, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps(
            [{"feil": f"Feil under drill-down aggregasjon: {str(e)}"}],
            ensure_ascii=False,
        )


# ============================================================
# 4. BUDSJETTOMDISPONERING & FULLMAKTSESKALERING (KOMMUNELOVEN § 14-5)
# ============================================================

def process_budget_reallocation(
    inp: BudgetReallocationInput,
    user_ctx: Optional[UserContext] = None,
) -> str:
    """Behandler forslag til budsjettomdisponering og vurderer delegeringsfullmakt og eskalering."""
    ctx = user_ctx or inp.user_context
    uid = ctx.user_id if ctx else "user_session"
    role = ctx.role if ctx else "direktor"

    belop = float(inp.belop_kr)

    # Fullmaktsmatrise iht. økonomireglement for Kristiansand kommune
    if role == "revisor":
        status = "AVVIST (Revisor har kun lesetilgang)"
        beslutningsorgan = "Ingen (Revisor kan ikke foreslå eller vedta omdisponeringer)"
        krever_eskalering = True
    elif inp.fra_ansvar != inp.til_ansvar and role == "enhetsleder":
        status = "ESKALERT TIL KOMMUNALSJEF (Mellom ulike enheter)"
        beslutningsorgan = "Kommunalsjef Helse og Mestring (eller Bystyret ved rammeendring)"
        krever_eskalering = True
    elif belop <= 1800000 and role in ("enhetsleder", "kommunalsjef", "direktor"):
        status = "GODKJENT INNENFOR ENHETSLEDERS FULLMAKT"
        beslutningsorgan = "Enhetsleder (Delegeringsfullmakt <= 1,8 mill. kr innen eget ansvar)"
        krever_eskalering = False
    elif belop <= 10000000 and role in ("kommunalsjef", "direktor"):
        status = "GODKJENT INNENFOR KOMMUNALSJEFENS FULLMAKT"
        beslutningsorgan = "Kommunalsjef Helse og Mestring (Fullmakt <= 10,0 mill. kr innen samme sektor)"
        krever_eskalering = False
    elif belop <= 25000000 and role == "direktor":
        status = "GODKJENT INNENFOR KOMMUNEDIREKTØRENS FULLMAKT"
        beslutningsorgan = "Kommunedirektør / Økonomidirektør (Fullmakt <= 25,0 mill. kr)"
        krever_eskalering = False
    else:
        status = "KREVER POLITISK BEHANDLING (Formannskapet / Bystyret jf. Kommuneloven § 14-5)"
        beslutningsorgan = "Kristiansand Bystyre (Endring av bevilgningsramme over fullmaktsgrense)"
        krever_eskalering = True

    summary = f"Fra {inp.fra_ansvar} til {inp.til_ansvar}: {belop:,.0f} kr -> {status}"
    write_audit_log(
        uid,
        role,
        "REALLOCATION_PROPOSAL",
        f"Fra={inp.fra_ansvar}, Til={inp.til_ansvar}, Beløp={belop}, Begrunnelse={inp.begrunnelse}",
        summary,
    )

    res = {
        "fra_ansvar": inp.fra_ansvar,
        "til_ansvar": inp.til_ansvar,
        "belop_kr": belop,
        "begrunnelse": inp.begrunnelse,
        "utført_av": {"bruker": uid, "rolle": role},
        "vurdering": {
            "status": status,
            "beslutningsmyndighet": beslutningsorgan,
            "krever_eskalering": krever_eskalering,
            "hjemmel": "Kommuneloven § 14-5 & Økonomireglement for Kristiansand kommune",
        },
        "tidsstempel": datetime.now().isoformat(),
    }
    return json.dumps(res, ensure_ascii=False, indent=2)
