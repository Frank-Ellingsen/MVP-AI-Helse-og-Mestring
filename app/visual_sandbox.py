# ==============================================================================
# VISUAL SANDBOX & TIME-VISUALS SUITE (FT Visual Vocabulary + Time-Visuals 60)
# ==============================================================================
# Inneholder implementasjoner for FT Visual Vocabulary (36 Suite), Time-Visuals.pdf
# (60 måter å visualisere tidsrekker på) og Power BI DAX-mål koblet til
# Edward Tufte Data-Ink Ratio.

from typing import Dict, Any, Optional
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np


def _apply_tufte_sandbox_layout(
    fig: go.Figure,
    title: str = "",
    subtitle: str = "",
    height: int = 340,
    show_legend: bool = False,
    right_margin: int = 150,
) -> go.Figure:
    """
    Edward Tufte Data-Ink Ratio:
    - Ingen vertikale rutenettlinjer (showgrid=False på x-akse)
    - Dempede farger; kun rødt (#b91c1c) og amber (#b45309) for aktive avvik/risiko
    - Direkte etikettering fremfor separate fargelegender der det er mulig
    """
    full_title = (
        f"<b>{title}</b><br><span style='font-size:12px;color:#4b5563;'>{subtitle}</span>"
        if subtitle
        else f"<b>{title}</b>"
    )
    fig.update_layout(
        title=dict(text=full_title, x=0, xanchor="left", font=dict(size=14, color="#111827")),
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        height=height,
        margin=dict(l=28, r=right_margin, t=58, b=38),
        xaxis=dict(showgrid=False, zeroline=False, linecolor="#111827", ticks="outside"),
        yaxis=dict(showgrid=True, gridcolor="#e5e7eb", zeroline=True, zerolinecolor="#9ca3af", linecolor="#d1d5db"),
        font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=12, color="#111827"),
        showlegend=show_legend,
    )
    return fig


def get_time_visual_recommendation(user_query: str, data_attributes: Optional[dict] = None) -> dict:
    """
    Analyser datastruktur og spørring for å anbefale optimal tidsvisualisering
    basert på Time-Visuals.pdf (60 Time Visualization Types) og FT Visual Vocabulary.
    """
    data_attributes = data_attributes or {}
    query_lower = (user_query or "").lower()
    periods = data_attributes.get("periods", 12)
    has_target = data_attributes.get("has_target", True)
    has_components = data_attributes.get("has_components", False)
    has_uncertainty = data_attributes.get("has_uncertainty", False)

    if any(w in query_lower for w in ["prognose", "eoy", "eac", "etc", "usikkerhet", "monte carlo"]) or has_uncertainty:
        return {
            "chart_type": "Fan Chart (P10/P50/P90)",
            "time_visual_id": "11/12 Usikkerhetsvifte",
            "reasoning": "Viser rullende regnskap YTD med Monte Carlo usikkerhetskonvolutt (P10–P90) og direkte linjemerking mot vedtatt årsbudsjett (BAC).",
            "category": "Time & Uncertainty",
        }
    elif any(w in query_lower for w in ["akkumulert", "ytd", "kumulativ", "s-kurve"]):
        return {
            "chart_type": "Running Total Area Chart",
            "time_visual_id": "24 Running Total Area",
            "reasoning": "Akkumulerer månedlige utgifter og avvik gjennom året (M1–M8) mot periodisert ramme for å vise total belastning på kommunekassen.",
            "category": "Time & Cumulative",
        }
    elif ("endring" in query_lower or "tertial" in query_lower or "t1" in query_lower or "t2" in query_lower or "slope" in query_lower):
        return {
            "chart_type": "Slope Graph",
            "time_visual_id": "40/41 Slope Graph",
            "reasoning": "Viser helningsvinkel for endring i prognoseavvik og CPI fra 1. tertial (T1) til 2. tertial (T2) per omsorgssenter.",
            "category": "Time & Change",
        }
    elif any(w in query_lower for w in ["glidende", "trend", "overtid", "vikar", "109000", "110000"]):
        return {
            "chart_type": "Continuous Line + Moving Average (3M)",
            "time_visual_id": "11/18 Moving Average Line",
            "reasoning": "Glatter ut månedlige tilfeldige svingninger (f.eks. etterbetaling av feriepenger og NAV-refusjoner) for å avdekke underliggende kostnadstrend.",
            "category": "Time & Trend",
        }
    elif any(w in query_lower for w in ["sesong", "måned", "sykefravær", "sparkline", "syklus"]):
        return {
            "chart_type": "Cycle Plot / Sparklines",
            "time_visual_id": "38 Cycle Plot & 46 Sparklines",
            "reasoning": "Sammenligner sesongmønstre (influensatopper jan–mars, ferieavvikling jun–aug) med høy data-ink ratio.",
            "category": "Time & Cyclical",
        }
    elif any(w in query_lower for w in ["komponent", "fordeling", "lønn", "fte", "artskonto"]) or has_components:
        return {
            "chart_type": "Stacked Area Chart (% of Total)",
            "time_visual_id": "16/17 Stacked Area Chart",
            "reasoning": "Viser hvordan fastlønn (101000), overtid (109000) og vikarinnleie (110000) bygger opp det samlede forbruket over tid.",
            "category": "Time & Part-to-Whole",
        }
    else:
        return {
            "chart_type": "Continuous Line with Markers & Reference Line",
            "time_visual_id": "03/33 Line Chart w/ Reference Line",
            "reasoning": "Kontinuerlig tidsrekke med budsjettreferanselinje (BAC/PV) og direkte endepunktmerking uten separat fargelegende.",
            "category": "Time & Continuous",
        }


def get_default_time_series_df(chart_type: str = "") -> pd.DataFrame:
    """Returnerer realistisk tidsseriedatasett for Helse og Mestring (MNOK) tilpasset valgt diagramtype."""
    if "Slope" in chart_type:
        return pd.DataFrame(
            [
                {"Enhet": "2530 Randesund", "T1": 1.15, "T2": 1.75},
                {"Enhet": "2580 Hjemmetj. Vågsbygd", "T1": 0.72, "T2": 1.12},
                {"Enhet": "2540 Strømmehaven", "T1": 0.48, "T2": 0.40},
                {"Enhet": "2330 Mestringsenheten", "T1": -0.05, "T2": -0.17},
            ]
        )

    months = ["Jan", "Feb", "Mar", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Des"]
    budsjett_mnd = [2.00] * 12
    faktisk_mnd = [2.15, 2.28, 2.35, 2.18, 2.25, 2.42, 2.52, 2.35, None, None, None, None]
    akk_budsjett = [round(2.00 * (i + 1), 2) for i in range(12)]
    akk_faktisk = [
        round(sum(x for x in faktisk_mnd[: i + 1] if x is not None), 2) if i < 8 else None
        for i in range(12)
    ]
    # Monte Carlo Fan Chart P10 / P50 / P90 (Kumulativ EAC-bane M8–M12)
    p50 = [None] * 7 + [18.50, 20.80, 23.10, 25.42, 27.75]
    p10 = [None] * 7 + [18.50, 20.35, 22.15, 23.95, 25.85]
    p90 = [None] * 7 + [18.50, 21.30, 24.10, 26.90, 29.65]

    # 3M Moving Average på månedlig forbruk (med prognose M9-M12 for kontinuitet)
    full_mnd = [2.15, 2.28, 2.35, 2.18, 2.25, 2.42, 2.52, 2.35, 2.30, 2.28, 2.32, 2.35]
    moving_avg_3m = pd.Series(full_mnd).rolling(window=3, min_periods=1).mean().round(2).tolist()

    return pd.DataFrame(
        {
            "Måned": months,
            "Budsjett": budsjett_mnd,
            "Faktisk": [akk_faktisk[i] if "Fan" in chart_type else full_mnd[i] for i in range(12)],
            "Faktisk_Mnd": full_mnd,
            "Akkumulert_Faktisk": akk_faktisk,
            "Akkumulert_Budsjett": akk_budsjett,
            "P10": p10,
            "P50": p50,
            "P90": p90,
            "Moving_Avg_3M": moving_avg_3m,
            "Fastlonn_MNOK": [1.55, 1.56, 1.58, 1.56, 1.57, 1.62, 1.65, 1.58, 1.58, 1.59, 1.60, 1.61],
            "Overtid_MNOK": [0.35, 0.42, 0.45, 0.36, 0.40, 0.48, 0.52, 0.45, 0.42, 0.40, 0.42, 0.44],
            "Vikar_MNOK": [0.25, 0.30, 0.32, 0.26, 0.28, 0.32, 0.35, 0.32, 0.30, 0.29, 0.30, 0.30],
        }
    )


def create_time_series_fig(chart_type: str, df: Optional[pd.DataFrame] = None, title: str = "") -> go.Figure:
    """
    Genererer minimalistiske Tufte-godkjente Plotly-figurer for tidsdata
    basert på Time-Visuals.pdf (60 Ways to Visualize Time).
    """
    if df is None or df.empty:
        df = get_default_time_series_df(chart_type)

    fig = go.Figure()

    if "Fan" in chart_type:
        if "P90" not in df.columns:
            df = get_default_time_series_df("Fan")
        # Fan Chart P10/P50/P90 (Monte Carlo Usikkerhetsvifte)
        fig.add_trace(
            go.Scatter(
                x=df["Måned"],
                y=df["P90"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["Måned"],
                y=df["P10"],
                mode="lines",
                fill="tonexty",
                fillcolor="rgba(185, 28, 28, 0.16)",
                line=dict(width=0),
                name="80% Usikkerhet (P10–P90)",
            )
        )
        if "Akkumulert_Budsjett" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["Måned"],
                    y=df["Akkumulert_Budsjett"],
                    mode="lines",
                    line=dict(color="#64748b", width=2, dash="dot"),
                    name="Vedtatt Budsjett (BAC)",
                )
            )
        fig.add_trace(
            go.Scatter(
                x=df["Måned"],
                y=df["P50"],
                mode="lines+markers",
                line=dict(color="#b91c1c", width=2.6, dash="dash"),
                marker=dict(size=5),
                name="Prognose (P50)",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["Måned"],
                y=df["Faktisk"],
                mode="lines+markers",
                line=dict(color="#111827", width=3),
                marker=dict(size=6),
                name="Faktisk YTD (AC)",
            )
        )
        # Direkte etikettering (Tufte-standard)
        last_p50 = df["P50"].dropna().iloc[-1] if df["P50"].dropna().size else 27.75
        last_p90 = df["P90"].dropna().iloc[-1] if df["P90"].dropna().size else 29.65
        last_p10 = df["P10"].dropna().iloc[-1] if df["P10"].dropna().size else 25.85
        fig.add_annotation(
            x=df["Måned"].iloc[-1],
            y=last_p50,
            text=f"  <b>P50 EAC: {last_p50:.2f}M</b>",
            showarrow=False,
            xanchor="left",
            font=dict(color="#b91c1c", size=11),
        )
        fig.add_annotation(
            x=df["Måned"].iloc[-1],
            y=last_p90,
            text=f"  P90: {last_p90:.2f}M",
            showarrow=False,
            xanchor="left",
            font=dict(color="#b45309", size=10),
        )
        fig.add_annotation(
            x=df["Måned"].iloc[-1],
            y=last_p10,
            text=f"  P10: {last_p10:.2f}M",
            showarrow=False,
            xanchor="left",
            font=dict(color="#475569", size=10),
        )

    elif "Running Total" in chart_type:
        if "Akkumulert_Faktisk" not in df.columns:
            df = get_default_time_series_df("Running Total")
        fig.add_trace(
            go.Scatter(
                x=df["Måned"],
                y=df["Akkumulert_Faktisk"],
                fill="tozeroy",
                fillcolor="rgba(51, 65, 85, 0.14)",
                line=dict(color="#111827", width=3),
                mode="lines+markers",
                name="Akkumulert Regnskap YTD (AC)",
            )
        )
        if "Akkumulert_Budsjett" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["Måned"],
                    y=df["Akkumulert_Budsjett"],
                    line=dict(color="#64748b", width=2, dash="dash"),
                    mode="lines",
                    name="Akkumulert Budsjett (BAC)",
                )
            )
            fig.add_annotation(
                x=df["Måned"].iloc[-1],
                y=df["Akkumulert_Budsjett"].iloc[-1],
                text=f"  BAC Årsramme: {df['Akkumulert_Budsjett'].iloc[-1]:.2f}M",
                showarrow=False,
                xanchor="left",
                font=dict(color="#475569", size=11),
            )

    elif "Moving Average" in chart_type:
        if "Moving_Avg_3M" not in df.columns:
            df = get_default_time_series_df("Moving Average")
        y_raw = df["Faktisk_Mnd"] if "Faktisk_Mnd" in df.columns else df["Faktisk"]
        fig.add_trace(
            go.Scatter(
                x=df["Måned"],
                y=y_raw,
                mode="lines+markers",
                line=dict(color="#94a3b8", width=1.5),
                marker=dict(size=5),
                name="Månedlig Faktisk",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["Måned"],
                y=df["Moving_Avg_3M"],
                mode="lines",
                line=dict(color="#b91c1c", width=3),
                name="3-Mnd Glidende Snitt",
            )
        )
        if "Budsjett" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["Måned"],
                    y=df["Budsjett"],
                    mode="lines",
                    line=dict(color="#475569", width=1.8, dash="dot"),
                    name="Månedlig Ramme (BAC)",
                )
            )
        fig.add_annotation(
            x=df["Måned"].iloc[-1],
            y=df["Moving_Avg_3M"].iloc[-1],
            text=f"  <b>3M Snitt: {df['Moving_Avg_3M'].iloc[-1]:.2f}M</b>",
            showarrow=False,
            xanchor="left",
            font=dict(color="#b91c1c", size=11),
        )

    elif "Slope" in chart_type:
        if "T1" not in df.columns or "T2" not in df.columns:
            df = get_default_time_series_df("Slope")
        for _, row in df.iterrows():
            # Økt positivt avvik (merforbruk) fra T1 til T2 markeres i rødt
            worsened = float(row["T2"]) > float(row["T1"]) and float(row["T2"]) > 0
            color = "#b91c1c" if worsened else "#475569"
            fig.add_trace(
                go.Scatter(
                    x=["1. Tertial (T1)", "2. Tertial (T2)"],
                    y=[row["T1"], row["T2"]],
                    mode="lines+markers+text",
                    text=[
                        f"{row['Enhet']}: {row['T1']:+.2f}M  ",
                        f"  {row['Enhet']}: {row['T2']:+.2f}M",
                    ],
                    textposition=["middle left", "middle right"],
                    line=dict(color=color, width=2.8 if worsened else 2.0),
                    marker=dict(size=7, color=color),
                    name=str(row["Enhet"]),
                )
            )

    elif "Stacked Area" in chart_type:
        if "Fastlonn_MNOK" not in df.columns:
            df = get_default_time_series_df("Stacked Area")
        fig.add_trace(
            go.Scatter(
                x=df["Måned"],
                y=df["Fastlonn_MNOK"],
                mode="lines",
                stackgroup="one",
                line=dict(width=1, color="#475569"),
                fillcolor="rgba(71, 85, 105, 0.35)",
                name="101000 Fast lønn",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["Måned"],
                y=df["Overtid_MNOK"],
                mode="lines",
                stackgroup="one",
                line=dict(width=1, color="#b45309"),
                fillcolor="rgba(180, 83, 9, 0.40)",
                name="109000 Overtid",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["Måned"],
                y=df["Vikar_MNOK"],
                mode="lines",
                stackgroup="one",
                line=dict(width=1, color="#b91c1c"),
                fillcolor="rgba(185, 28, 28, 0.45)",
                name="110000 Innleie/Vikarer",
            )
        )

    else:
        # Default Continuous Line with Reference Line & Direct Labeling
        y_series = df["Faktisk_Mnd"] if "Faktisk_Mnd" in df.columns else df["Faktisk"]
        fig.add_trace(
            go.Scatter(
                x=df["Måned"],
                y=y_series,
                mode="lines+markers",
                line=dict(color="#111827", width=2.8),
                marker=dict(size=6),
                name="Faktisk Forbruk (AC)",
            )
        )
        if "Budsjett" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["Måned"],
                    y=df["Budsjett"],
                    mode="lines",
                    line=dict(color="#64748b", width=2, dash="dash"),
                    name="Budsjett (BAC)",
                )
            )
            fig.add_annotation(
                x=df["Måned"].iloc[-1],
                y=df["Budsjett"].iloc[-1],
                text=f"  BAC: {df['Budsjett'].iloc[-1]:.2f}M",
                showarrow=False,
                xanchor="left",
                font=dict(color="#475569", size=11),
            )
        valid_y = y_series.dropna()
        if not valid_y.empty:
            fig.add_annotation(
                x=df["Måned"].iloc[len(valid_y) - 1],
                y=valid_y.iloc[-1],
                text=f"  <b>Faktisk: {valid_y.iloc[-1]:.2f}M</b>",
                showarrow=False,
                xanchor="left",
                font=dict(color="#111827", size=11),
            )

    _apply_tufte_sandbox_layout(
        fig,
        title=title or f"Time-Visuals: {chart_type}",
        subtitle="Edward Tufte Data-Ink Ratio — Time-Visuals.pdf (60 Ways to Visualize Time)",
        height=340,
        show_legend=("Stacked Area" in chart_type),
        right_margin=175,
    )
    return fig


# ==============================================================================
# FT VISUAL VOCABULARY (36 SUITE) & POWER BI DAX SNIPPETS
# ==============================================================================

def generate_waterfall_chart(
    unit_name: str = "Helse og Mestring (Samlet)",
    bac: float = 24.0,
    eac_unadj: float = 27.75,
    tiltak: float = -1.85,
) -> go.Figure:
    """
    FT Part-to-Whole / Time-Visuals #59: Budsjettbro (Waterfall) fra vedtatt ramme (BAC)
    til justert årsprognose (EAC) etter § 14-5 tiltak.
    """
    vac = round(eac_unadj - bac, 2)
    justert_eac = round(eac_unadj + tiltak, 2)
    fig = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "total", "relative", "total"],
            x=[
                "Vedtatt Budsjett (BAC)",
                "Prognoseavvik (VAC)",
                "Ujustert EAC",
                "§ 14-5 Tiltak (TØRN/Refusjon)",
                "Justert EAC",
            ],
            y=[bac, vac, 0, tiltak, 0],
            text=[
                f"{bac:.2f}M",
                f"{vac:+.2f}M",
                f"{eac_unadj:.2f}M",
                f"{tiltak:+.2f}M",
                f"{justert_eac:.2f}M",
            ],
            textposition="outside",
            connector=dict(line=dict(color="#9ca3af", width=1, dash="dot")),
            increasing=dict(marker=dict(color="#b91c1c")),
            decreasing=dict(marker=dict(color="#334155")),
            totals=dict(marker=dict(color="#64748b")),
        )
    )
    _apply_tufte_sandbox_layout(
        fig,
        title=f"Budsjettbro (Waterfall): Fra Vedtatt Ramme (BAC) til Justert EAC — {unit_name}",
        subtitle="FT Category: Part-to-Whole / Time-Visuals #59. Rødt markerer merforbruk; skifergrå viser korrigerende § 14-5 tiltak.",
        height=330,
        show_legend=False,
        right_margin=40,
    )
    fig.update_yaxes(title_text="MNOK", range=[0, max(eac_unadj, bac) * 1.22])
    return fig


def generate_scatter_correlation() -> go.Figure:
    """
    FT Correlation: Scatterplot over Sykefravær (%) vs. Overtids- og vikarutgifter (art 109000/110000).
    """
    df_corr = pd.DataFrame(
        [
            {"Enhet": "2330 Mestringsenheten", "Sykefravaer": 6.5, "Overtid_Vikar_kkr": 210},
            {"Enhet": "2540 Strømmehaven", "Sykefravaer": 7.8, "Overtid_Vikar_kkr": 620},
            {"Enhet": "2530 Randesund Omsorgssenter", "Sykefravaer": 9.5, "Overtid_Vikar_kkr": 2000},
            {"Enhet": "2580 Hjemmetj. Vågsbygd", "Sykefravaer": 11.2, "Overtid_Vikar_kkr": 1650},
            {"Enhet": "Kleplandstunet Sykehjem", "Sykefravaer": 12.4, "Overtid_Vikar_kkr": 2250},
        ]
    )
    point_colors = ["#b91c1c" if s > 8.1 else "#475569" for s in df_corr["Sykefravaer"]]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[6.0, 13.0],
            y=[150, 2350],
            mode="lines",
            line=dict(color="#cbd5e1", width=1.5, dash="dot"),
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df_corr["Sykefravaer"],
            y=df_corr["Overtid_Vikar_kkr"],
            mode="markers+text",
            marker=dict(size=10, color=point_colors),
            text=[f"{r['Enhet']} ({r['Sykefravaer']}%)" for _, r in df_corr.iterrows()],
            textposition=["top right", "top left", "bottom right", "bottom left", "top left"],
            textfont=dict(size=11, color=point_colors),
        )
    )
    fig.add_vline(x=8.1, line_width=1.5, line_dash="dash", line_color="#b45309")
    fig.add_annotation(
        x=8.1,
        y=2300,
        text="  Måltall sykefravær: 8,1 % (r = 0,94)",
        showarrow=False,
        xanchor="left",
        font=dict(color="#b45309", size=11),
    )
    _apply_tufte_sandbox_layout(
        fig,
        title="Korrelasjon: Sykefravær (%) vs. Overtid & Vikarbyrå (art 109000/110000, kkr)",
        subtitle="FT Category: Correlation. Enheter over måltallet på 8,1 % er markert i rødt for TØRN-oppfølging.",
        height=330,
        show_legend=False,
        right_margin=40,
    )
    fig.update_xaxes(title_text="Sykefravær (%)", range=[5.5, 13.8])
    fig.update_yaxes(title_text="Overtid & Vikar YTD (kkr)", range=[0, 2550])
    return fig


def generate_lollipop_ranking() -> go.Figure:
    """
    FT Ranking: Minimal-Ink Lollipop Chart for Cost Performance Index (CPI) per enhet.
    """
    df_cpi = pd.DataFrame(
        [
            {"Enhet": "2530 Randesund Omsorgssenter", "CPI": 0.87},
            {"Enhet": "BOMILJO Kommunal Boenhet", "CPI": 0.92},
            {"Enhet": "2580 Hjemmetjenesten Vågsbygd", "CPI": 0.94},
            {"Enhet": "2540 Strømmehaven", "CPI": 0.97},
            {"Enhet": "2330 Mestringsenheten", "CPI": 1.03},
        ]
    )
    fig = go.Figure()
    for _, row in df_cpi.iterrows():
        cpi_val = float(row["CPI"])
        col = "#b91c1c" if cpi_val < 0.93 else ("#b45309" if cpi_val < 0.98 else "#475569")
        fig.add_trace(
            go.Scatter(
                x=[1.0, cpi_val],
                y=[row["Enhet"], row["Enhet"]],
                mode="lines",
                line=dict(color=col, width=2.5),
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[cpi_val],
                y=[row["Enhet"]],
                mode="markers+text",
                marker=dict(size=11, color=col),
                text=[f"  CPI {cpi_val:.2f}" if cpi_val >= 1.0 else f"CPI {cpi_val:.2f}  "],
                textposition="middle right" if cpi_val >= 1.0 else "middle left",
                textfont=dict(size=11, color=col),
            )
        )
    fig.add_vline(x=1.0, line_width=1.2, line_dash="dash", line_color="#111827")
    fig.add_annotation(
        x=1.0,
        y=4.4,
        text="  Balanseterskel (CPI = 1,00)",
        showarrow=False,
        xanchor="left",
        font=dict(color="#111827", size=11),
    )
    _apply_tufte_sandbox_layout(
        fig,
        title="Rangering av Kostnadseffektivitet (CPI = Periodisert Budsjett / Regnskap)",
        subtitle="FT Category: Ranking (Minimal-Ink Lollipop). CPI < 1,00 indikerer merforbruk mot vedtatt ramme.",
        height=310,
        show_legend=False,
        right_margin=80,
    )
    fig.update_xaxes(title_text="Cost Performance Index (CPI)", range=[0.78, 1.12])
    fig.update_yaxes(showgrid=False)
    return fig


def get_dax_snippets() -> Dict[str, str]:
    """
    Returnerer produksjonsklare Power BI DAX-mål for Helse og Mestring (Kristiansand kommune)
    tilpasset Star Schema (fact_erp_transactions, fact_budget_allocations, dim_tid, dim_organisasjon).
    """
    return {
        "HM_EOY_Avvik_Prognose": (
            "HM_EOY_Avvik_Prognose = \n"
            "VAR _MndPassert = MAX(dim_tid[periode])\n"
            "VAR _RegnskapYTD = CALCULATE(SUM(fact_erp_transactions[belop]), DATESYTD(dim_tid[dato]))\n"
            "VAR _VedtattAarsbudsjett = CALCULATE(SUM(fact_budget_allocations[regulert_budsjett]), ALL(dim_tid[periode]))\n"
            "VAR _LineaerEAC = DIVIDE(_RegnskapYTD, _MndPassert, 0) * 12\n"
            "RETURN\n"
            "    _LineaerEAC - _VedtattAarsbudsjett"
        ),
        "HM_Cost_Performance_Index": (
            "HM_Cost_Performance_Index = \n"
            "VAR _PeriodisertBudsjettYTD = CALCULATE(SUM(fact_budget_allocations[periodisert_budsjett]), DATESYTD(dim_tid[dato]))\n"
            "VAR _RegnskapYTD = CALCULATE(SUM(fact_erp_transactions[belop]), DATESYTD(dim_tid[dato]))\n"
            "RETURN\n"
            "    ROUND(DIVIDE(_PeriodisertBudsjettYTD, _RegnskapYTD, 1.00), 2)"
        ),
        "HM_Moving_Avg_3M_Vikar": (
            "HM_Moving_Avg_3M_Vikar = \n"
            "AVERAGEX(\n"
            "    DATESINPERIOD(dim_tid[dato], LASTDATE(dim_tid[dato]), -3, MONTH),\n"
            "    CALCULATE(\n"
            "        SUM(fact_erp_transactions[belop]),\n"
            "        dim_kostra_kontoplan[art_id] IN {\"109000\", \"110000\"}\n"
            "    )\n"
            ")"
        ),
    }
