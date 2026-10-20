# app/frontend.py
import os
import sys
import json
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
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
    page_title="Kristiansand Kommune — Helse og Mestring AI Økonomistyring (v3)",
    layout="wide",
)

# ==============================================================================
# EDWARD TUFTE DATA-INK RATIO STYLING & HELPERS
# ==============================================================================
st.markdown(
    """
    <style>
    /* Tufte Data-Ink Ratio Standards:
       - Zero drop shadows, zero decorative card borders
       - No vertical gridlines in tables
       - Left-align text, right-align numbers with tabular-nums */
    .tufte-kpi-strip {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: 24px;
        padding: 14px 0;
        border-top: 1.5px solid #111827;
        border-bottom: 1px solid #d1d5db;
        margin-bottom: 20px;
    }
    .tufte-kpi-item {
        display: flex;
        flex-direction: column;
    }
    .tufte-kpi-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #6b7280;
        margin-bottom: 4px;
        font-weight: 600;
    }
    .tufte-kpi-value {
        font-size: 22px;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        font-feature-settings: "tnum";
        color: #111827;
    }
    .tufte-kpi-value.risk-red {
        color: #b91c1c;
    }
    .tufte-kpi-value.risk-amber {
        color: #b45309;
    }
    .tufte-kpi-sub {
        font-size: 12px;
        color: #4b5563;
        margin-top: 2px;
        font-variant-numeric: tabular-nums;
    }
    table.tufte-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 8px;
        margin-bottom: 20px;
        font-size: 13px;
    }
    table.tufte-table thead th {
        border-top: 1.5px solid #111827;
        border-bottom: 1px solid #111827;
        border-left: none;
        border-right: none;
        padding: 8px 10px;
        font-weight: 600;
        color: #111827;
        text-align: left;
        background-color: #ffffff;
    }
    table.tufte-table thead th.num,
    table.tufte-table tbody td.num,
    table.tufte-table tfoot td.num {
        text-align: right;
        font-variant-numeric: tabular-nums;
        font-feature-settings: "tnum";
        font-family: "JetBrains Mono", "Consolas", monospace;
    }
    table.tufte-table tbody td {
        border-bottom: 1px solid #e5e7eb;
        border-left: none;
        border-right: none;
        padding: 8px 10px;
        color: #111827;
        text-align: left;
    }
    table.tufte-table tfoot td {
        border-top: 1px solid #111827;
        border-bottom: 2px double #111827;
        border-left: none;
        border-right: none;
        padding: 8px 10px;
        font-weight: 600;
        color: #111827;
    }
    .val-red { color: #b91c1c; font-weight: 600; }
    .val-amber { color: #b45309; font-weight: 600; }
    .val-muted { color: #4b5563; }
    .tufte-notice {
        padding: 12px 14px;
        border-left: 3px solid #334155;
        background-color: #f4f5f7;
        margin: 12px 0;
        font-size: 13.5px;
    }
    .tufte-notice.alert-red {
        border-left-color: #b91c1c;
        background-color: #fef2f2;
    }
    .tufte-notice.alert-amber {
        border-left-color: #b45309;
        background-color: #fffbeb;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def fmt_kr(val: float, signed: bool = False) -> str:
    v = float(val or 0.0)
    prefix = "+" if (signed and v > 0) else ""
    formatted = f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return f"{prefix}{formatted} kr"


def apply_tufte_layout(fig: go.Figure, title: str, subtitle: str = "", height: int = 340) -> go.Figure:
    full_title = f"<b>{title}</b><br><span style='font-size:12px;color:#4b5563;'>{subtitle}</span>" if subtitle else f"<b>{title}</b>"
    fig.update_layout(
        title=dict(text=full_title, x=0, xanchor="left", font=dict(size=14, color="#111827")),
        template="plotly_white",
        height=height,
        margin=dict(l=20, r=140, t=58, b=36),
        showlegend=False,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#111827"),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#111827", ticks="outside")
    fig.update_yaxes(showgrid=True, gridcolor="#e5e7eb", zeroline=False, linecolor="#d1d5db")
    return fig


st.title("Helse og Mestring — Beslutningsstøtte, Prognose (EAC/ETC) & Økonomistyring (v3)")
st.caption(
    "Hybrid AI-agent, S-kurve fremskriving, 6-nivås drill-down, RBAC-sikkerhet, GDPR-personvern, omdisponeringsmotor (§ 14-5) og uforanderlig audit-logg."
)

# Sidebar - User Context & RBAC Configuration
with st.sidebar:
    st.subheader("Brukerkontekst & RBAC")
    user_id = st.text_input("Bruker-ID / E-post:", "frank.ellingsen@kristiansand.kommune.no")
    user_role = st.selectbox(
        "Rolle (RBAC):", ["direktor", "kommunalsjef", "enhetsleder", "revisor"], index=0
    )
    assigned_ansvar_choice = st.selectbox(
        "Tildelt Ansvarsområde (Enhetsleder):",
        [
            "2530 - Randesund Omsorgssenter",
            "2580 - Hjemmetjenesten Vågsbygd",
            "2540 - Strømmehaven",
            "2330 - Mestringsenheten",
        ],
    )
    assigned_ansvar = assigned_ansvar_choice.split(" - ")[0].strip()

    user_ctx = UserContext(
        user_id=user_id,
        role=user_role,
        assigned_ansvar=assigned_ansvar if user_role == "enhetsleder" else None,
        tillatte_ansvar=[assigned_ansvar] if user_role == "enhetsleder" else [],
    )

    st.divider()
    st.write("**Gjeldende tilgangsbegrensning:**")
    if user_role == "enhetsleder":
        st.warning(f"Begrenset til enhet `{assigned_ansvar}` (Enkeltansatte GDPR-skjermet)")
    elif user_role == "kommunalsjef":
        st.info("Tilgang til alle enheter i kommunalsjefområde Helse og Mestring (Fullmakt <= 10,0 MNOK)")
    elif user_role == "direktor":
        st.success("Full tilgang til alle sektorer og enheter (Fullmakt <= 25,0 MNOK)")
    else:
        st.info("Revisor-tilgang: Kun lesing og kontroll av Audit-logg")

    st.divider()
    if st.button("Tøm samtale- og økt-state"):
        st.session_state.messages = []
        st.rerun()

# Define 7 Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    [
        "1. AI-Økonomirådgiver",
        "2. Månedlig Rapport",
        "3. S-Kurve (EAC/ETC) & FT Visuals",
        "4. EOY Prognose & Lønnsbudsjett",
        "5. 6-Nivås Drill-Down",
        "6. Omdisponering (§ 14-5)",
        "7. Audit-Logg (Revisor)",
    ]
)

# ==============================================================================
# TAB 1: AI-ØKONOMIRÅDGIVER
# ==============================================================================
with tab1:
    st.subheader("AI-Økonomirådgiver med Sikkerhets- og Personvernguardrails")
    st.caption("Klikk på et hurtigspørsmål under eller skriv inn ditt eget spørsmål:")

    q_cols = st.columns(4)
    quick_prompts = [
        ("Avviksanalyse 2530 (M8)", "Hva er månedlig avvik og hoveddrivere for ansvar 2530 Randesund Omsorgssenter per august (M8)?"),
        ("EAC-prognose & § 14-5 tiltak", "Beregn EOY/EAC-prognose for ansvar 2530 (hittil forbruk 13 650 000 kr, årsbudsjett 17 850 000 kr, sykefravær 9,5%) og foreslå tiltak etter kommuneloven § 14-5."),
        ("Sykefravær vs. Overtid", "Hvordan henger sykefravær sammen med overtidsforbruk (art 109000) og vikarinnleie (art 110000) i Helse og Mestring?"),
        ("Sjekk fullmaktsgrense", "Kan enhetsleder omdisponere 1 500 000 kr fra ansvar 2580 til 2530?"),
    ]
    triggered_prompt = None
    for idx, (label, prompt_text) in enumerate(quick_prompts):
        if q_cols[idx].button(label, key=f"qp_{idx}", use_container_width=True):
            triggered_prompt = prompt_text

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": f"Hei {user_id}! Jeg er din AI-økonomirådgiver. Som **{user_role}** kan du stille spørsmål om regnskapsavvik, EAC/ETC-prognoser, TØRN-tiltak eller omdisponeringsfullmakter.",
            }
        ]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    chat_input_val = st.chat_input("Spør om regnskapsavvik, EAC/ETC-prognose, TØRN-tiltak, lønnsbudsjett eller fullmakter...")
    active_prompt = triggered_prompt or chat_input_val

    if active_prompt:
        st.session_state.messages.append({"role": "user", "content": active_prompt})
        with st.chat_message("user"):
            st.markdown(active_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyserer forespørsel, sjekker RBAC-tilganger og henter data..."):
                response = run_krs_agent(active_prompt, user_ctx)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

# ==============================================================================
# TAB 2: MÅNEDLIG RAPPORT & AVVIKSOPPSTILLING
# ==============================================================================
with tab2:
    st.subheader("Månedlig Avviksrapport & Artsoppstilling")
    c1, c2 = st.columns([2, 2])
    unit_options = [
        "2530 - Randesund Omsorgssenter",
        "2580 - Hjemmetjenesten Vågsbygd",
        "2540 - Strømmehaven",
        "2330 - Mestringsenheten",
        "BOMILJO - Kommunal Boenhet (Bo- og Miljø)",
    ]
    default_idx = 0
    if user_role == "enhetsleder":
        for i, u in enumerate(unit_options):
            if u.startswith(assigned_ansvar):
                default_idx = i
                break

    with c1:
        ansvar_input = st.selectbox("Ansvarsenhet:", unit_options, index=default_idx)
    with c2:
        mnd_input = st.slider("Rapporteringsperiode (Måned 1–12):", 1, 12, 8)

    raw_res = generate_monthly_unit_report(ansvar_input, mnd_input, user_ctx)
    res = json.loads(raw_res)

    if "feil" in res:
        st.markdown(
            f"<div class='tufte-notice alert-red'><strong>{res['feil']}</strong></div>",
            unsafe_allow_html=True,
        )
    elif "sammenfatning" in res:
        sammen = res["sammenfatning"]
        tot_bud = float(sammen.get("totalt_hittil_budsjett", 0))
        tot_reg = float(sammen.get("totalt_hittil_forbruk", 0))
        tot_avv = float(sammen.get("totalt_avvik_kr", 0))
        cpi_val = float(sammen.get("cpi", tot_bud / tot_reg if tot_reg else 1.0))
        rag_text = sammen.get("rag_status", "GREEN")
        risk_cls = "risk-red" if tot_avv > 500000 else ("risk-amber" if tot_avv > 0 else "")

        st.markdown(
            f"""
            <div class="tufte-kpi-strip">
                <div class="tufte-kpi-item">
                    <span class="tufte-kpi-label">Enhet / Ansvar</span>
                    <span class="tufte-kpi-value">{ansvar_input.split(' - ')[0]}</span>
                    <span class="tufte-kpi-sub">{ansvar_input} (M1–M{mnd_input})</span>
                </div>
                <div class="tufte-kpi-item">
                    <span class="tufte-kpi-label">Budsjett YTD (BAC)</span>
                    <span class="tufte-kpi-value">{fmt_kr(tot_bud)}</span>
                    <span class="tufte-kpi-sub">Periodisert ramme</span>
                </div>
                <div class="tufte-kpi-item">
                    <span class="tufte-kpi-label">Regnskap YTD (AC)</span>
                    <span class="tufte-kpi-value">{fmt_kr(tot_reg)}</span>
                    <span class="tufte-kpi-sub">Bokført per M{mnd_input}</span>
                </div>
                <div class="tufte-kpi-item">
                    <span class="tufte-kpi-label">Netto Avvik YTD</span>
                    <span class="tufte-kpi-value {risk_cls}">{fmt_kr(tot_avv, signed=True)}</span>
                    <span class="tufte-kpi-sub">{rag_text} | CPI: {cpi_val:.2f}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        df_art = pd.DataFrame(res.get("artsoppstilling", []))
        if not df_art.empty:
            df_art["etikett"] = df_art["artskonto"].astype(str) + " " + df_art["art_navn"].astype(str)
            df_art = df_art.sort_values("avvik_kr", ascending=True)

            col_v1, col_v2 = st.columns(2)
            with col_v1:
                colors = [
                    "#b91c1c" if v > 300000 else ("#b45309" if v > 0 else "#64748b")
                    for v in df_art["avvik_kr"]
                ]
                fig_m_avv = go.Figure(
                    go.Bar(
                        x=df_art["avvik_kr"],
                        y=df_art["etikett"],
                        orientation="h",
                        marker_color=colors,
                        text=[f"{v:+,.0f} kr".replace(",", " ") for v in df_art["avvik_kr"]],
                        textposition="outside",
                        cliponaxis=False,
                    )
                )
                apply_tufte_layout(
                    fig_m_avv,
                    "Avvik per Artskonto (YTD)",
                    "Rødt/gult markerer merforbruk eller manglende refusjon; grått er i balanse.",
                    height=300,
                )
                fig_m_avv.add_vline(x=0, line_width=1, line_color="#111827")
                fig_m_avv.update_xaxes(showgrid=False)
                fig_m_avv.update_yaxes(showgrid=False)
                st.plotly_chart(fig_m_avv, width="stretch")

            with col_v2:
                fig_m_comp = go.Figure()
                fig_m_comp.add_trace(
                    go.Bar(
                        x=df_art["hittil_budsjett"],
                        y=df_art["etikett"],
                        orientation="h",
                        name="Budsjett YTD",
                        marker_color="#94a3b8",
                    )
                )
                fig_m_comp.add_trace(
                    go.Bar(
                        x=df_art["hittil_forbruk"],
                        y=df_art["etikett"],
                        orientation="h",
                        name="Regnskap YTD",
                        marker_color="#334155",
                    )
                )
                apply_tufte_layout(
                    fig_m_comp,
                    "Budsjett YTD (Lys grå) vs. Regnskap YTD (Mørk skifer)",
                    f"Sammenligning per artskonto til og med måned {mnd_input}.",
                    height=300,
                )
                fig_m_comp.update_layout(barmode="group")
                fig_m_comp.update_xaxes(showgrid=False)
                fig_m_comp.update_yaxes(showgrid=False)
                st.plotly_chart(fig_m_comp, width="stretch")

            # Tufte HTML Table
            rows_html = ""
            for _, r in df_art.sort_values("avvik_kr", ascending=False).iterrows():
                bud_v = float(r["hittil_budsjett"])
                reg_v = float(r["hittil_forbruk"])
                avv_v = float(r["avvik_kr"])
                pct_v = (avv_v / abs(bud_v) * 100.0) if bud_v != 0 else 0.0
                cls = "val-red" if avv_v > 300000 else ("val-amber" if avv_v > 0 else "val-muted")
                rows_html += f"""
                <tr>
                    <td>{r['artskonto']}</td>
                    <td>{r['art_navn']}</td>
                    <td class="num">{fmt_kr(bud_v)}</td>
                    <td class="num">{fmt_kr(reg_v)}</td>
                    <td class="num {cls}">{fmt_kr(avv_v, signed=True)}</td>
                    <td class="num {cls}">{pct_v:+.1f} %</td>
                </tr>
                """

            tot_pct = (tot_avv / abs(tot_bud) * 100.0) if tot_bud != 0 else 0.0
            tot_cls = "val-red" if tot_avv > 500000 else ("val-amber" if tot_avv > 0 else "")
            st.markdown(
                f"""
                <table class="tufte-table">
                    <thead>
                        <tr>
                            <th>Artskonto</th>
                            <th>Artsnavn</th>
                            <th class="num">Budsjett YTD</th>
                            <th class="num">Regnskap YTD</th>
                            <th class="num">Avvik (kr)</th>
                            <th class="num">Avvik (%)</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                    <tfoot>
                        <tr>
                            <td colspan="2">Sum {ansvar_input}</td>
                            <td class="num">{fmt_kr(tot_bud)}</td>
                            <td class="num">{fmt_kr(tot_reg)}</td>
                            <td class="num {tot_cls}">{fmt_kr(tot_avv, signed=True)}</td>
                            <td class="num {tot_cls}">{tot_pct:+.1f} %</td>
                        </tr>
                    </tfoot>
                </table>
                """,
                unsafe_allow_html=True,
            )

        with st.expander("Vis rådata (JSON)"):
            st.json(res)

# ==============================================================================
# TAB 3: FT VISUAL VOCABULARY & S-KURVE (EAC/ETC)
# ==============================================================================
with tab3:
    st.subheader("Financial Times Visual Vocabulary & S-Kurve (EAC/ETC)")
    st.caption(
        "Edward Tufte Data-Ink Ratio: Direkte etikettering på linjene uten separat fargelegende, null vertikale rutenettlinjer og fremheving kun av aktive risiki."
    )

    ft_unit_profiles = {
        "Hele Sektor Helse og Mestring": {
            "bac_annual": 24.0,
            "ac_m8": 18.5,
            "tiltak_mnok": -1.85,
            "arts": [
                ("109000 Overtid", 1470000),
                ("110000 Innleie / Vikarer", 550000),
                ("101000 Fast lønn", 260000),
                ("169000 Sykelønnsrefusjon NAV (etterslep)", 240000),
                ("101000 Forebyggende team (2330)", -110000),
            ],
        },
        "2530 — Randesund Omsorgssenter": {
            "bac_annual": 17.85,
            "ac_m8": 13.65,
            "tiltak_mnok": -0.93,
            "arts": [
                ("109000 Overtid", 750000),
                ("110000 Innleie / Vikarer", 550000),
                ("169000 Sykelønnsrefusjon NAV", 300000),
                ("101000 Fast lønn", 150000),
            ],
        },
        "2580 — Hjemmetjenesten Vågsbygd": {
            "bac_annual": 14.76,
            "ac_m8": 10.37,
            "tiltak_mnok": -0.45,
            "arts": [
                ("109000 Overtid", 450000),
                ("101000 Fast lønn", 80000),
            ],
        },
        "2540 — Strømmehaven": {
            "bac_annual": 17.34,
            "ac_m8": 11.96,
            "tiltak_mnok": -0.30,
            "arts": [
                ("109000 Overtid", 260000),
                ("101000 Fast lønn", 140000),
            ],
        },
        "2330 — Mestringsenheten": {
            "bac_annual": 9.60,
            "ac_m8": 6.23,
            "tiltak_mnok": 0.0,
            "arts": [
                ("169000 Sykelønnsrefusjon NAV", -60000),
                ("101000 Fast lønn", -110000),
            ],
        },
    }

    selected_ft_unit = st.selectbox(
        "Velg analyseenhet for S-Kurve, Avviksdiagram og Budsjettbro:",
        list(ft_unit_profiles.keys()),
    )
    prof = ft_unit_profiles[selected_ft_unit]
    months = ["Jan", "Feb", "Mar", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Des"]
    bac_series = [round((prof["bac_annual"] / 12.0) * (i + 1), 2) for i in range(12)]
    ac_series = [round((prof["ac_m8"] / 8.0) * (i + 1), 2) for i in range(8)]
    eac_end = round((prof["ac_m8"] / 8.0) * 12.0, 2)
    eac_vac = round(eac_end - prof["bac_annual"], 2)
    eac_series = [None] * 7 + [round(prof["ac_m8"] + (eac_end - prof["ac_m8"]) * (i / 4.0), 2) for i in range(5)]

    # 1. Cumulative S-Curve (Change over Time) with Direct Labeling
    fig_scurve = go.Figure()
    fig_scurve.add_trace(
        go.Scatter(
            x=months,
            y=bac_series,
            mode="lines+markers",
            line=dict(color="#64748b", width=2),
            marker=dict(size=5),
            name="Vedtatt Budsjett (BAC)",
        )
    )
    fig_scurve.add_trace(
        go.Scatter(
            x=months[:8],
            y=ac_series,
            mode="lines+markers",
            line=dict(color="#111827", width=2.8),
            marker=dict(size=6),
            name="Regnskap YTD (AC)",
        )
    )
    eac_color = "#b91c1c" if eac_vac > 0 else "#334155"
    fig_scurve.add_trace(
        go.Scatter(
            x=months[7:],
            y=eac_series[7:],
            mode="lines+markers",
            line=dict(color=eac_color, width=2.4, dash="dash"),
            marker=dict(size=6),
            name="EAC Prognose",
        )
    )
    fig_scurve.add_vline(x=7, line_width=1, line_dash="dot", line_color="#9ca3af")
    fig_scurve.add_annotation(
        x="Des",
        y=eac_end,
        text=f"  <b>EAC Prognose: {eac_end:.2f} MNOK ({eac_vac:+.2f}M)</b>",
        showarrow=False,
        xanchor="left",
        font=dict(color=eac_color, size=12),
    )
    fig_scurve.add_annotation(
        x="Des",
        y=prof["bac_annual"],
        text=f"  Vedtatt BAC: {prof['bac_annual']:.2f} MNOK",
        showarrow=False,
        xanchor="left",
        font=dict(color="#475569", size=12),
    )
    fig_scurve.add_annotation(
        x="Aug",
        y=prof["ac_m8"],
        text=f"AC M8: {prof['ac_m8']:.2f} MNOK  ",
        showarrow=False,
        xanchor="right",
        yshift=12,
        font=dict(color="#111827", size=12),
    )
    apply_tufte_layout(
        fig_scurve,
        f"Kumulativ S-Kurve: Budsjett (BAC) vs. Regnskap (AC) og Fremskrevet Årsprognose (EAC) — {selected_ft_unit}",
        "Akkumulert forbruk M1–M8 og ETC-bane M9–M12 (MNOK). Direkte etikettering uten separat fargelegende.",
        height=360,
    )
    fig_scurve.update_layout(margin=dict(l=20, r=240, t=58, b=36))
    fig_scurve.update_yaxes(title_text="MNOK")
    st.plotly_chart(fig_scurve, width="stretch")

    col_ft1, col_ft2 = st.columns(2)

    # 2. Diverging Bar Chart (Deviation)
    with col_ft1:
        df_ft = pd.DataFrame(prof["arts"], columns=["Artskonto", "Avvik_Kr"]).sort_values("Avvik_Kr", ascending=True)
        df_ft["Farge"] = df_ft["Avvik_Kr"].apply(
            lambda x: "#b91c1c" if x > 300000 else ("#b45309" if x > 0 else "#64748b")
        )
        fig_div = go.Figure(
            go.Bar(
                x=df_ft["Avvik_Kr"],
                y=df_ft["Artskonto"],
                orientation="h",
                marker_color=df_ft["Farge"],
                text=[f"{v:+,.0f} kr".replace(",", " ") for v in df_ft["Avvik_Kr"]],
                textposition="outside",
                cliponaxis=False,
            )
        )
        apply_tufte_layout(
            fig_div,
            "Avvik per KOSTRA Artskonto (Diverging Bar — YTD M8)",
            "Positiv verdi = merforbruk / manglende refusjon. Negativ verdi = mindreforbruk.",
            height=330,
        )
        fig_div.add_vline(x=0, line_width=1, line_color="#111827")
        fig_div.update_xaxes(showgrid=False)
        fig_div.update_yaxes(showgrid=False)
        st.plotly_chart(fig_div, width="stretch")

    # 3. Correlation Scatter Plot (Sykefravær % vs. Overtid kr)
    with col_ft2:
        df_corr = pd.DataFrame(
            [
                {"Enhet": "Mestringsenheten (2330)", "Sykefravaer": 6.5, "Overtid_kkr": 210},
                {"Enhet": "Strømmehaven (2540)", "Sykefravaer": 7.8, "Overtid_kkr": 620},
                {"Enhet": "Randesund Omsorgssenter (2530)", "Sykefravaer": 9.5, "Overtid_kkr": 1150},
                {"Enhet": "Hjemmetjenesten Vågsbygd (2580)", "Sykefravaer": 11.2, "Overtid_kkr": 1450},
                {"Enhet": "Kleplandstunet", "Sykefravaer": 12.4, "Overtid_kkr": 1850},
            ]
        )
        point_colors = ["#b91c1c" if s > 8.1 else "#475569" for s in df_corr["Sykefravaer"]]
        fig_scat = go.Figure()
        # Trendline (r = 0.94)
        fig_scat.add_trace(
            go.Scatter(
                x=[6.0, 13.0],
                y=[110, 1980],
                mode="lines",
                line=dict(color="#cbd5e1", width=1.5, dash="dot"),
                hoverinfo="skip",
            )
        )
        fig_scat.add_trace(
            go.Scatter(
                x=df_corr["Sykefravaer"],
                y=df_corr["Overtid_kkr"],
                mode="markers+text",
                marker=dict(size=10, color=point_colors),
                text=[f"{r['Enhet']} ({r['Sykefravaer']}%)" for _, r in df_corr.iterrows()],
                textposition=["top right", "top left", "bottom right", "top left", "bottom left"],
                textfont=dict(size=11, color=point_colors),
            )
        )
        fig_scat.add_vline(x=8.1, line_width=1.5, line_dash="dash", line_color="#b45309")
        fig_scat.add_annotation(
            x=8.1,
            y=1950,
            text="  Måltall sykefravær: 8,1 % (r = 0,94)",
            showarrow=False,
            xanchor="left",
            font=dict(color="#b45309", size=11),
        )
        apply_tufte_layout(
            fig_scat,
            "Korrelasjon: Sykefravær (%) vs. Overtid (art 109000, kkr)",
            "Enheter over måltallet på 8,1 % er markert i rødt for TØRN- og nærværsoppfølging.",
            height=330,
        )
        fig_scat.update_layout(margin=dict(l=20, r=40, t=58, b=36))
        fig_scat.update_xaxes(title_text="Sykefravær (%)", range=[5.5, 13.8])
        fig_scat.update_yaxes(title_text="Overtid YTD (kkr)", range=[0, 2150])
        st.plotly_chart(fig_scat, width="stretch")

    # 4. Waterfall Chart (Flow / Part-to-Whole: BAC -> EAC -> Tiltak -> Justert EAC)
    justert_eac = round(eac_end + prof["tiltak_mnok"], 2)
    fig_wf = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "total", "relative", "total"],
            x=[
                "Vedtatt Budsjett (BAC)",
                "Fremskrevet Mer-/Mindreforbruk",
                "Ujustert Årsprognose (EAC)",
                "Effekt av § 14-5 Tiltak",
                "Justert EAC (Etter Tiltak)",
            ],
            y=[prof["bac_annual"], eac_vac, 0, prof["tiltak_mnok"], 0],
            text=[
                f"{prof['bac_annual']:.2f}M",
                f"{eac_vac:+.2f}M",
                f"{eac_end:.2f}M",
                f"{prof['tiltak_mnok']:+.2f}M",
                f"{justert_eac:.2f}M",
            ],
            textposition="outside",
            connector=dict(line=dict(color="#9ca3af", width=1, dash="dot")),
            increasing=dict(marker=dict(color="#b91c1c")),
            decreasing=dict(marker=dict(color="#334155")),
            totals=dict(marker=dict(color="#64748b")),
        )
    )
    apply_tufte_layout(
        fig_wf,
        f"Budsjettbro (Waterfall): Fra Vedtatt Ramme (BAC) til Justert Årsprognose (EAC) — {selected_ft_unit}",
        "Viser hvordan § 14-5 tiltak (TØRN-turnus, NAV-refusjonsinnhenting og vikarstopp) reduserer forventet årsavvik.",
        height=320,
    )
    fig_wf.update_layout(margin=dict(l=20, r=40, t=58, b=36))
    fig_wf.update_yaxes(title_text="MNOK", range=[0, max(eac_end, prof["bac_annual"]) * 1.22])
    st.plotly_chart(fig_wf, width="stretch")

    ft_img_path = PROJECT_ROOT / "assets" / "ft-Viz-Guide.png"
    if ft_img_path.exists():
        with st.expander("Vis Financial Times Visual Vocabulary Referanseoversikt"):
            st.image(str(ft_img_path), caption="Financial Times Visual Vocabulary", width="stretch")

# ==============================================================================
# TAB 4: EOY PROGNOSE & LØNNSBUDSJETTERING
# ==============================================================================
with tab4:
    st.subheader("Prediktiv Årsprognose (EAC / ETC) & Preskriptive Balansetiltak (§ 14-5)")
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        forbruk = st.number_input("Akkumulert forbruk hittil AC (kr):", value=18500000.0, step=100000.0)
    with fc2:
        budsjett = st.number_input("Vedtatt årsbudsjett BAC (kr):", value=24000000.0, step=100000.0)
    with fc3:
        sykefraver = st.number_input("Sykefravær (%):", value=9.9, step=0.1)

    res_eoy = json.loads(
        calculate_eoy_prescriptive_forecast(ansvar_input, forbruk, budsjett, sykefraver, user_ctx)
    )
    avv_ytd = float(res_eoy.get("avvik_hittil", 0))
    eac_val = float(res_eoy.get("eoy_prognose", 0))
    etc_val = float(res_eoy.get("etc_gjenstaende", eac_val - forbruk))
    vac_val = float(res_eoy.get("forventet_eoy_avvik", 0))
    cpi_eoy = float(res_eoy.get("cpi", 1.0))
    eoy_cls = "risk-red" if vac_val > 0 else ""

    st.markdown(
        f"""
        <div class="tufte-kpi-strip">
            <div class="tufte-kpi-item">
                <span class="tufte-kpi-label">Påløpt Hittil (AC M1–M8)</span>
                <span class="tufte-kpi-value">{fmt_kr(forbruk)}</span>
                <span class="tufte-kpi-sub">Avvik YTD: {fmt_kr(avv_ytd, signed=True)}</span>
            </div>
            <div class="tufte-kpi-item">
                <span class="tufte-kpi-label">Gjenstående Påløp (ETC M9–M12)</span>
                <span class="tufte-kpi-value">{fmt_kr(etc_val)}</span>
                <span class="tufte-kpi-sub">Fremskrevet 4 mnd</span>
            </div>
            <div class="tufte-kpi-item">
                <span class="tufte-kpi-label">Årsprognose (EAC)</span>
                <span class="tufte-kpi-value {eoy_cls}">{fmt_kr(eac_val)}</span>
                <span class="tufte-kpi-sub">Vedtatt BAC: {fmt_kr(budsjett)}</span>
            </div>
            <div class="tufte-kpi-item">
                <span class="tufte-kpi-label">Forventet Årsavvik (VAC)</span>
                <span class="tufte-kpi-value {eoy_cls}">{fmt_kr(vac_val, signed=True)}</span>
                <span class="tufte-kpi-sub">{res_eoy.get('status')} | CPI: {cpi_eoy:.2f}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    eoy_col1, eoy_col2 = st.columns([3, 2])
    with eoy_col1:
        tiltak_effekt = -min(vac_val * 0.65, vac_val) if vac_val > 0 else 0.0
        justert_eac_kr = eac_val + tiltak_effekt
        fig_eoy_bar = go.Figure(
            go.Bar(
                x=[budsjett, eac_val, justert_eac_kr],
                y=[
                    "Vedtatt Årsbudsjett (BAC)",
                    "Ujustert Årsprognose (EAC)",
                    "Mål-EAC etter § 14-5 Tiltak",
                ],
                orientation="h",
                marker_color=["#64748b", "#b91c1c" if vac_val > 0 else "#334155", "#b45309" if justert_eac_kr > budsjett else "#334155"],
                text=[fmt_kr(budsjett), fmt_kr(eac_val), fmt_kr(justert_eac_kr)],
                textposition="outside",
                cliponaxis=False,
            )
        )
        apply_tufte_layout(
            fig_eoy_bar,
            "Sammenligning: Vedtatt Ramme (BAC) vs. Årsprognose (EAC)",
            "Effekt av korrigerende § 14-5 tiltak i siste tertial.",
            height=250,
        )
        fig_eoy_bar.update_layout(margin=dict(l=20, r=170, t=54, b=28))
        fig_eoy_bar.update_xaxes(showgrid=False)
        fig_eoy_bar.update_yaxes(showgrid=False)
        st.plotly_chart(fig_eoy_bar, width="stretch")

    with eoy_col2:
        st.markdown("**Anbefalte Preskriptive Tiltak (Kommuneloven § 14-5):**")
        for t in res_eoy.get("anbefalte_preskriptive_tiltak", []):
            st.markdown(f"- {t}")

    st.divider()
    st.subheader("Lønnsbudsjettering Neste Økonomiplanår")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        fte = st.number_input("Antall Årsverk / Hjemler (FTE):", value=32.5, step=0.5)
    with sc2:
        deflator = st.number_input("Kommunal Deflator / Lønnsvekst (%):", value=4.1, step=0.1)
    with sc3:
        tillegg = st.number_input("Ulempe/Turnustillegg (%):", value=18.0, step=0.5)

    res_sal = json.loads(
        calculate_next_year_salary_budget(ansvar_input, fte, deflator, tillegg, user_ctx)
    )
    grunn_kr = float(res_sal.get("beregnet_grunnlonn", 0))
    till_kr = float(res_sal.get("beregnet_tillegg", 0))
    sos_kr = float(res_sal.get("beregnet_sosiale_utgifter", (grunn_kr + till_kr) * 0.22))
    def_kr = float(res_sal.get("beregnet_deflator_paslag", 0))
    tot_sal_kr = float(res_sal.get("neste_ar_lonnsbudsjett_inkl_aga_pensjon_og_deflator", 0))

    sal_col1, sal_col2 = st.columns([1, 1])
    with sal_col1:
        fig_sal = go.Figure(
            go.Bar(
                x=[grunn_kr, till_kr, sos_kr, def_kr],
                y=[
                    "1. Grunnlønn (art 101000)",
                    "2. Turnustillegg (art 112000)",
                    "3. AGA & Pensjon (+22%)",
                    f"4. Deflator ({deflator:.1f}%)",
                ],
                orientation="h",
                marker_color=["#334155", "#475569", "#64748b", "#94a3b8"],
                text=[fmt_kr(grunn_kr), fmt_kr(till_kr), fmt_kr(sos_kr), fmt_kr(def_kr)],
                textposition="outside",
                cliponaxis=False,
            )
        )
        apply_tufte_layout(
            fig_sal,
            "Lønnsbudsjett per Kostnadskomponent",
            f"Totalt lønnsbudsjett for {fte:.1f} FTE: {fmt_kr(tot_sal_kr)}",
            height=260,
        )
        fig_sal.update_layout(margin=dict(l=20, r=170, t=54, b=28))
        fig_sal.update_xaxes(showgrid=False)
        fig_sal.update_yaxes(showgrid=False)
        st.plotly_chart(fig_sal, width="stretch")

    with sal_col2:
        st.markdown(
            f"""
            <table class="tufte-table">
                <thead>
                    <tr>
                        <th>Lønnskomponent</th>
                        <th>Beregningsgrunnlag</th>
                        <th class="num">Beløp (kr)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Ordinær grunnlønn (art 101000)</td>
                        <td>{fte:.1f} FTE × 650 000 kr</td>
                        <td class="num">{fmt_kr(grunn_kr)}</td>
                    </tr>
                    <tr>
                        <td>Ubekvem- og turnustillegg (art 112000)</td>
                        <td>{tillegg:.1f} % av grunnlønn</td>
                        <td class="num">{fmt_kr(till_kr)}</td>
                    </tr>
                    <tr>
                        <td>Arbeidsgiveravgift og pensjon (KLP/KKP)</td>
                        <td>Faktor 1,22 (+22 % sosiale utgifter)</td>
                        <td class="num">{fmt_kr(sos_kr)}</td>
                    </tr>
                    <tr>
                        <td>Pris- og lønnsvekst (Kommunal deflator)</td>
                        <td>{deflator:.1f} % påslag neste økonomiplanår</td>
                        <td class="num">{fmt_kr(def_kr)}</td>
                    </tr>
                </tbody>
                <tfoot>
                    <tr>
                        <td colspan="2">Totalt lønnsbudsjett neste år</td>
                        <td class="num">{fmt_kr(tot_sal_kr)}</td>
                    </tr>
                </tfoot>
            </table>
            """,
            unsafe_allow_html=True,
        )

# ==============================================================================
# TAB 5: 6-NIVÅS INTERAKTIV DRILL-DOWN
# ==============================================================================
with tab5:
    st.subheader("6-Nivås Interaktiv Drill-Down (Sektor ➔ Enkeltbilag)")
    st.caption(
        "Velg filtre fra venstre mot høyre for å drille ned fra Sektornivå (Nivå 1) til Enkeltbilag (Nivå 6, GDPR-skjermet)."
    )
    d1, d2, d3, d4, d5 = st.columns(5)
    with d1:
        sektor_v = st.selectbox("1. Sektor:", ["Helse og Mestring", "Oppvekst"])
    with d2:
        ks_v = st.selectbox(
            "2. Kommunalsjefområde:",
            ["Alle", "Heldøgns omsorg", "Hjemmebaserte tjenester", "Mestring og helse", "Grunnskole"],
        )
    with d3:
        ansvar_v = st.selectbox(
            "3. Ansvar / Enhet:",
            ["Alle", "2530", "2580", "2540", "2330", "BOMILJO", "KOMSKOLE"],
        )
    with d4:
        funksjon_v = st.selectbox(
            "4. KOSTRA-Funksjon:",
            ["Alle", "253", "254", "258", "233", "202"],
        )
    with d5:
        art_v = st.selectbox(
            "5. KOSTRA-Artskonto:",
            ["Alle", "101000", "109000", "110000", "169000"],
        )

    raw_dd = drill_down_budget_hierarchy(
        sektor=sektor_v,
        ks_omrade=None if ks_v == "Alle" else ks_v,
        ansvar_id=None if ansvar_v == "Alle" else ansvar_v,
        funksjon_id=None if funksjon_v == "Alle" else funksjon_v,
        art_id=None if art_v == "Alle" else art_v,
        user_ctx=user_ctx,
    )
    res_dd = json.loads(raw_dd)

    if isinstance(res_dd, dict) and "feil" in res_dd:
        st.markdown(
            f"<div class='tufte-notice alert-red'><strong>{res_dd['feil']}</strong></div>",
            unsafe_allow_html=True,
        )
    elif isinstance(res_dd, list):
        # Level 6: Enkeltbilag
        st.markdown(
            "<div class='tufte-notice'><strong>Aktuelt visningsnivå: Nivå 6 — Transaksjonsbilag (GDPR-skjermet på ansatt-ID)</strong></div>",
            unsafe_allow_html=True,
        )
        df_l6 = pd.DataFrame(res_dd)
        if not df_l6.empty and "belop" in df_l6.columns:
            rows_l6 = ""
            for _, r in df_l6.iterrows():
                rows_l6 += f"""
                <tr>
                    <td>{r.get('bilagsnummer', '')}</td>
                    <td>{r.get('dato', '')}</td>
                    <td>{r.get('leverandor_ansatt', '')}</td>
                    <td>{r.get('beskrivelse', '')}</td>
                    <td class="num">{fmt_kr(float(r.get('belop', 0)))}</td>
                </tr>
                """
            st.markdown(
                f"""
                <table class="tufte-table">
                    <thead>
                        <tr>
                            <th>Bilagsnummer</th>
                            <th>Dato</th>
                            <th>Leverandør / Ansatt</th>
                            <th>Beskrivelse</th>
                            <th class="num">Bokført Beløp</th>
                        </tr>
                    </thead>
                    <tbody>{rows_l6}</tbody>
                </table>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("Ingen transaksjonsbilag funnet for dette utvalget.")
    elif isinstance(res_dd, dict) and "rader" in res_dd:
        lvl_name = res_dd.get("visningsnivaa", "Hierarki")
        st.markdown(
            f"<div class='tufte-notice'><strong>Aktuelt visningsnivå: {lvl_name}</strong></div>",
            unsafe_allow_html=True,
        )
        df_dd = pd.DataFrame(res_dd["rader"])
        if not df_dd.empty:
            label_cols = [c for c in df_dd.columns if c not in ("hittil_budsjett", "hittil_forbruk", "avvik_kr", "RAG")]
            df_dd["Enhet_Label"] = df_dd[label_cols].astype(str).agg(" — ".join, axis=1)

            fig_dd = go.Figure(
                go.Bar(
                    x=df_dd["avvik_kr"],
                    y=df_dd["Enhet_Label"],
                    orientation="h",
                    marker_color=[
                        "#b91c1c" if v > 500000 else ("#b45309" if v > 0 else "#64748b")
                        for v in df_dd["avvik_kr"]
                    ],
                    text=[f"{v:+,.0f} kr".replace(",", " ") for v in df_dd["avvik_kr"]],
                    textposition="outside",
                    cliponaxis=False,
                )
            )
            apply_tufte_layout(
                fig_dd,
                f"Avvik per enhet på {lvl_name}",
                "Sortert etter størst avvik (kr).",
                height=max(240, len(df_dd) * 42 + 90),
            )
            fig_dd.add_vline(x=0, line_width=1, line_color="#111827")
            fig_dd.update_layout(margin=dict(l=20, r=160, t=54, b=28))
            fig_dd.update_xaxes(showgrid=False)
            fig_dd.update_yaxes(showgrid=False, autorange="reversed")
            st.plotly_chart(fig_dd, width="stretch")

            dd_rows_html = ""
            for _, r in df_dd.iterrows():
                b_v = float(r.get("hittil_budsjett", 0))
                f_v = float(r.get("hittil_forbruk", 0))
                a_v = float(r.get("avvik_kr", 0))
                cls = "val-red" if a_v > 500000 else ("val-amber" if a_v > 0 else "val-muted")
                dd_rows_html += f"""
                <tr>
                    <td>{r['Enhet_Label']}</td>
                    <td class="num">{fmt_kr(b_v)}</td>
                    <td class="num">{fmt_kr(f_v)}</td>
                    <td class="num {cls}">{fmt_kr(a_v, signed=True)}</td>
                    <td class="{cls}">{r.get('RAG', '')}</td>
                </tr>
                """
            s_b = float(df_dd["hittil_budsjett"].sum())
            s_f = float(df_dd["hittil_forbruk"].sum())
            s_a = float(df_dd["avvik_kr"].sum())
            s_cls = "val-red" if s_a > 500000 else ("val-amber" if s_a > 0 else "")
            st.markdown(
                f"""
                <table class="tufte-table">
                    <thead>
                        <tr>
                            <th>Hierarkienhet ({lvl_name})</th>
                            <th class="num">Budsjett YTD</th>
                            <th class="num">Regnskap YTD</th>
                            <th class="num">Avvik (kr)</th>
                            <th>Status (RAG)</th>
                        </tr>
                    </thead>
                    <tbody>{dd_rows_html}</tbody>
                    <tfoot>
                        <tr>
                            <td>Sum utvalg</td>
                            <td class="num">{fmt_kr(s_b)}</td>
                            <td class="num">{fmt_kr(s_f)}</td>
                            <td class="num {s_cls}">{fmt_kr(s_a, signed=True)}</td>
                            <td></td>
                        </tr>
                    </tfoot>
                </table>
                """,
                unsafe_allow_html=True,
            )

# ==============================================================================
# TAB 6: BUDSJETTOMDISPONERING & FULLMAKTSESKALERING
# ==============================================================================
with tab6:
    st.subheader("Budsjettomdisponering & Fullmaktseskalering (Kommuneloven § 14-5)")
    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        fra_e = st.selectbox("Fra Enhet (Mindreforbruk):", ["2330", "2580", "2540", "2530"], index=0)
    with rc2:
        til_e = st.selectbox("Til Enhet (Merforbruk):", ["2530", "2580", "2540", "2330"], index=0)
    with rc3:
        belop_e = st.number_input("Omdisponeringsbeløp (kr):", value=1500000.0, step=100000.0)

    begr_e = st.text_area(
        "Faglig og økonomisk begrunnelse:",
        "Omdisponering for å dekke merforbruk knyttet til lovpålagt døgnpleie og forsinket sykelønnsrefusjon ved Randesund Omsorgssenter.",
    )

    inp_re = BudgetReallocationInput(
        fra_ansvar=fra_e,
        til_ansvar=til_e,
        belop_kr=belop_e,
        begrunnelse=begr_e,
    )
    res_re = json.loads(process_budget_reallocation(inp_re, user_ctx))
    vurd = res_re.get("vurdering", {})
    status_str = vurd.get("status", "")
    eskaler = vurd.get("krever_eskalering", False)
    notice_cls = "alert-red" if ("AVVIST" in status_str or "POLITISK" in status_str) else ("alert-amber" if eskaler else "")

    st.markdown(
        f"""
        <div class="tufte-notice {notice_cls}">
            <div><strong>Fullmaktsstatus:</strong> {status_str}</div>
            <div style="margin-top:4px;"><strong>Beslutningsmyndighet:</strong> {vurd.get('beslutningsmyndighet', '')}</div>
            <div style="margin-top:4px;"><strong>Overføring:</strong> Fra ansvar {fra_e} til ansvar {til_e} — <strong>{fmt_kr(belop_e)}</strong></div>
            <div style="margin-top:4px;"><strong>Hjemmel:</strong> {vurd.get('hjemmel', '')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Visual: Delegation Authority Scale
    fig_auth = go.Figure()
    thresholds = [
        ("Enhetsleder (eget ansvar)", 1800000),
        ("Kommunalsjef (samme sektor)", 10000000),
        ("Kommunedirektør (kommunen)", 25000000),
        ("Foreslått Omdisponering", belop_e),
    ]
    fig_auth.add_trace(
        go.Bar(
            x=[t[1] for t in thresholds],
            y=[t[0] for t in thresholds],
            orientation="h",
            marker_color=["#94a3b8", "#64748b", "#475569", "#b91c1c" if eskaler else "#111827"],
            text=[fmt_kr(t[1]) for t in thresholds],
            textposition="outside",
            cliponaxis=False,
        )
    )
    apply_tufte_layout(
        fig_auth,
        "Delegeringsfullmakter i Kristiansand Kommune vs. Foreslått Beløp",
        "Beløp over 25,0 MNOK (eller mellom sektorer uten fullmakt) krever vedtak i Bystyret jf. Kommuneloven § 14-5.",
        height=260,
    )
    fig_auth.update_layout(margin=dict(l=20, r=170, t=54, b=28))
    fig_auth.update_xaxes(showgrid=False)
    fig_auth.update_yaxes(showgrid=False)
    st.plotly_chart(fig_auth, width="stretch")

# ==============================================================================
# TAB 7: AUDIT-LOGG (REVISORVISNING)
# ==============================================================================
with tab7:
    st.subheader("Uforanderlig Audit-Logg & Innsyn (Revisorvisning)")
    st.caption(
        "Fullstendig etterprøvbart revisjonsspor over alle brukerhandlinger, AI-spørringer, SQL-kall og omdisponeringsforslag (jf. Arkivlova og Kommuneloven)."
    )

    logs = get_audit_logs(limit=50)
    if logs:
        df_logs = pd.DataFrame(logs)
        act_counts = df_logs["action_type"].value_counts().reset_index()
        act_counts.columns = ["Handlingstype", "Antall"]

        fig_aud = go.Figure(
            go.Bar(
                x=act_counts["Antall"],
                y=act_counts["Handlingstype"],
                orientation="h",
                marker_color=[
                    "#b91c1c" if ("DENIED" in a or "VIOLATION" in a) else "#334155"
                    for a in act_counts["Handlingstype"]
                ],
                text=act_counts["Antall"],
                textposition="outside",
                cliponaxis=False,
            )
        )
        apply_tufte_layout(
            fig_aud,
            "Fordeling av Revisjonshendelser etter Handlingstype",
            f"Siste {len(df_logs)} loggførte hendelser i SQLite audit_log.",
            height=240,
        )
        fig_aud.update_xaxes(showgrid=False)
        fig_aud.update_yaxes(showgrid=False, autorange="reversed")
        st.plotly_chart(fig_aud, width="stretch")

        csv_bytes = df_logs.to_csv(index=False, sep=";").encode("utf-8")
        st.download_button(
            "Eksporter Audit-Logg (CSV)",
            data=csv_bytes,
            file_name="krs_kommune_audit_log.csv",
            mime="text/csv",
        )
        st.dataframe(df_logs, width="stretch", hide_index=True)
    else:
        st.info("Ingen audit-logger registrert enda.")
