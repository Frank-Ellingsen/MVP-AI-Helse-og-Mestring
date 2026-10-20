# app/frontend.py
import os
import sys
import json
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

# Ensure import paths and .env work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

try:
    from app.agent import run_krs_agent
    from app.tools import (
        query_erp_transactions_secure,
        search_knowledge_base,
        search_web_serper,
        generate_monthly_unit_report,
        calculate_eoy_prescriptive_forecast,
        calculate_next_year_salary_budget,
        drill_down_budget_hierarchy,
        process_budget_reallocation,
        get_audit_logs,
        write_audit_log,
        DB_PATH,
    )
    from app.schemas import UserContext, BudgetReallocationInput
except ImportError:
    from agent import run_krs_agent
    from tools import (
        query_erp_transactions_secure,
        search_knowledge_base,
        search_web_serper,
        generate_monthly_unit_report,
        calculate_eoy_prescriptive_forecast,
        calculate_next_year_salary_budget,
        drill_down_budget_hierarchy,
        process_budget_reallocation,
        get_audit_logs,
        write_audit_log,
        DB_PATH,
    )
    from schemas import UserContext, BudgetReallocationInput

# Streamlit Page Config
st.set_page_config(
    page_title="Kristiansand Kommune - Helse & Mestring AI (v3)",
    page_icon="🩺",
    layout="wide",
)

st.title("🩺 Helse og Mestring — Beslutningsstøtte & Økonomistyring (v3)")
st.caption(
    "Hybrid AI-agent, 6-nivås drill-down, RBAC-sikkerhet, GDPR-personvern, RAG-trafikklys, omdisponeringsmotor og uforanderlig audit-logg."
)

# Sidebar - User Context & RBAC Configuration
with st.sidebar:
    st.header("👤 Brukerkontekst & RBAC")
    user_id = st.text_input("Bruker-ID / E-post:", "frank.enhetsleder@kristiansand.kommune.no")
    user_role = st.selectbox(
        "Rolle (RBAC):", ["enhetsleder", "kommunalsjef", "direktor", "revisor"]
    )
    assigned_ansvar = st.text_input("Tildelt Ansvarsområde (kun for enhetsleder):", "2530")

    user_ctx = UserContext(
        user_id=user_id,
        role=user_role,
        assigned_ansvar=assigned_ansvar if user_role == "enhetsleder" else None,
        tillatte_ansvar=[assigned_ansvar] if user_role == "enhetsleder" else [],
    )

    st.divider()
    st.write("**Gjeldende tilgangsbegrensning:**")
    if user_role == "enhetsleder":
        st.warning(f"🔒 Begrenset til enhet `{assigned_ansvar}` (GDPR Skjermet)")
    elif user_role == "kommunalsjef":
        st.info("ℹ️ Tilgang til alle enheter i kommunalsjefområde Helse og Mestring")
    elif user_role == "direktor":
        st.success("🟢 Full tilgang til alle sektorer og enheter")
    else:
        st.info("🔍 Revisor-tilgang: Kun lesing og kontroll av Audit-logg")

    st.divider()
    if st.button("🗑️ Tøm samtale- og økt-state"):
        st.session_state.messages = []
        st.rerun()

# Define Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    [
        "💬 AI-Økonomirådgiver",
        "📊 Månedlig Rapport & Trafikklys",
        "📈 FT Visual Vocabulary",
        "🔮 EOY Prognose & Lønnsbudsjett",
        "🔍 6-Nivås Drill-Down",
        "🔄 Omdisponering & Eskalering",
        "📜 Audit-Logg (Revisorvisning)",
    ]
)

# --- TAB 1: AI Chat ---
with tab1:
    st.subheader("💬 AI Økonomirådgiver med Sikkerhets- og Personvernguardrails")
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": f"Hei {user_id}! Jeg er din AI-økonomirådgiver. Som **{user_role}** kan du stille spørsmål om regnskap, avvik, prognoser eller omdisponeringer.",
            }
        ]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_prompt := st.chat_input("Skriv spørsmålet ditt her..."):
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyserer forespørsel og sjekker RBAC-tilganger..."):
                response = run_krs_agent(user_prompt, user_ctx)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

# --- TAB 2: Monthly Report & RAG Traffic Lights ---
with tab2:
    st.subheader("📊 Månedlig Avviksrapport & RAG Trafikklys")
    c1, c2 = st.columns(2)
    with c1:
        ansvar_input = st.text_input(
            "Ansvarsnummer:", assigned_ansvar if user_role == "enhetsleder" else "2530"
        )
    with c2:
        mnd_input = st.slider("Rapporteringsmåned:", 1, 12, 8)

    if st.button("Hent Månedlig Rapport"):
        raw_res = generate_monthly_unit_report(ansvar_input, mnd_input, user_ctx)
        res = json.loads(raw_res)
        if "sammenfatning" in res:
            sammen = res["sammenfatning"]
            avvik = sammen.get("totalt_avvik_kr", 0)
            rag_text = sammen.get("rag_status", "🟢 GREEN")
            badge_bg = (
                "#dc3545"
                if "🔴" in rag_text
                else ("#ffc107" if "🟡" in rag_text else "#28a745")
            )
            st.markdown(
                f"""
                <div style="background-color: {badge_bg}; padding: 12px; border-radius: 8px; color: white; font-weight: bold; text-align: center; font-size: 18px; margin-bottom: 20px;">
                    RAG STATUS: {rag_text} | Samlet Avvik: {avvik:,.0f} kr
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.json(res)

# --- TAB 3: FT Visual Vocabulary ---
with tab3:
    st.subheader("📈 Financial Times Visual Vocabulary")
    st.caption("Visuell avviksanalyse og korrelasjon mellom sykefravær og overtid.")

    # Sample Plotly Diverging Bar Chart
    df_ft = pd.DataFrame(
        {
            "Artskonto": [
                "100000 Fast lønn",
                "109000 Overtid",
                "110000 Innleie vikarer",
                "169000 Refusjon NAV",
                "120000 Drift/Forbruk",
            ],
            "Avvik_Kr": [-150000, 1850000, 1200000, -850000, 320000],
        }
    )
    df_ft["Farge"] = df_ft["Avvik_Kr"].apply(lambda x: "#dc3545" if x > 0 else "#28a745")

    fig = go.Figure(
        go.Bar(
            x=df_ft["Avvik_Kr"],
            y=df_ft["Artskonto"],
            orientation="h",
            marker_color=df_ft["Farge"],
        )
    )
    fig.update_layout(
        title="Avvik pr. Artskonto (Diverging Bar)",
        xaxis_title="Avvik i Kr",
        yaxis_title="Artskonto",
        template="plotly_white",
    )
    st.plotly_chart(fig, width="stretch")

# --- TAB 4: EOY Forecast & Salary Budgeting ---
with tab4:
    st.subheader("🔮 EOY Prognose & Lønnsbudsjettering")
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        forbruk = st.number_input("Hittil forbruk (kr):", value=18500000.0)
    with fc2:
        budsjett = st.number_input("Årsbudsjett (kr):", value=24000000.0)
    with fc3:
        sykefraver = st.number_input("Sykefravær (%):", value=9.9)

    if st.button("Kjør Årsprognose"):
        res_eoy = calculate_eoy_prescriptive_forecast(
            ansvar_input, forbruk, budsjett, sykefraver, user_ctx
        )
        st.json(res_eoy)

    st.divider()
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        fte = st.number_input("Antall Årsverk (FTE):", value=32.5)
    with sc2:
        deflator = st.number_input("Deflator (%):", value=4.1)
    with sc3:
        tillegg = st.number_input("Ulempe/Turnus (%):", value=18.0)

    if st.button("Beregne Lønnsbudsjett"):
        res_sal = calculate_next_year_salary_budget(
            ansvar_input, fte, deflator, tillegg, user_ctx
        )
        st.json(res_sal)

# --- TAB 5: 6-Level Drill-Down ---
with tab5:
    st.subheader("🔍 6-Nivås Drill-Down (Sektor ➔ Transaksjonsbilag)")
    d1, d2, d3 = st.columns(3)
    with d1:
        sektor_v = st.selectbox(
            "Sektor:", ["Helse og Mestring", "Oppvekst", "By- og stedsutvikling"]
        )
    with d2:
        ks_v = st.selectbox(
            "Kommunalsjefområde:", ["Alle", "Heldøgns omsorg", "Hjemmebaserte tjenester"]
        )
    with d3:
        ansvar_v = st.selectbox("Ansvar:", ["Alle", "2530", "2580"])

    if st.button("Utfør Drill-Down"):
        res_dd = drill_down_budget_hierarchy(
            sektor=sektor_v,
            ks_omrade=None if ks_v == "Alle" else ks_v,
            ansvar_id=None if ansvar_v == "Alle" else ansvar_v,
            user_ctx=user_ctx,
        )
        st.json(res_dd)

# --- TAB 6: Budget Reallocation & Escalation ---
with tab6:
    st.subheader("🔄 Budsjettomdisponering & Fullmaktseskalering")
    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        fra_e = st.text_input("Fra Enhet (Mindreforbruk):", "2580")
    with rc2:
        til_e = st.text_input("Til Enhet (Merforbruk):", "2530")
    with rc3:
        belop_e = st.number_input("Beløp (kr):", value=1500000.0)

    begr_e = st.text_area(
        "Begrunnelse:",
        "Omdisponering fra ubenyttet ramme i Hjemmetjenesten til dekning av avvik på Omsorgssenter.",
    )

    if st.button("Prosessere Omdisponering"):
        inp_re = BudgetReallocationInput(
            fra_ansvar=fra_e,
            til_ansvar=til_e,
            belop_kr=belop_e,
            begrunnelse=begr_e,
        )
        res_re = process_budget_reallocation(inp_re, user_ctx)
        st.json(res_re)

# --- TAB 7: Audit Log (Revisorvisning) ---
with tab7:
    st.subheader("📜 Uforanderlig Audit-Logg & Innsyn (Revisorvisning)")
    st.caption(
        "Fullstendig etterprøvbart revisjonsspor over alle brukerhandlinger, AI-spørringer, SQL-kall og omdisponeringsforslag (jf. Arkivlova og Kommuneloven)."
    )

    if st.button("🔄 Oppdater Audit-Logg"):
        st.rerun()

    logs = get_audit_logs(limit=50)
    if logs:
        df_logs = pd.DataFrame(logs)
        st.dataframe(df_logs, width="stretch")
    else:
        st.info("Ingen audit-logger registrert enda.")
