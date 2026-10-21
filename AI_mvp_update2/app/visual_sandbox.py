# ==============================================================================
# VISUAL SANDBOX & TIME-VISUALS SUITE (FT Visual Vocabulary + Time-Visuals 60)
# ==============================================================================
# Inneholder implementasjoner for FT Visual Vocabulary (36 Suite) og Time-Visuals.pdf
# (60 måter å visualisere tidsrekker på) koblet til Edward Tufte Data-Ink Ratio.

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

def get_time_visual_recommendation(user_query: str, data_attributes: dict) -> dict:
    """
    Analyser datastruktur og spørring for å anbefale optimal tidsvisualisering
    basert på Time-Visuals.pdf (60 Time Visualization Types).
    """
    query_lower = user_query.lower()
    periods = data_attributes.get('periods', 12)
    has_target = data_attributes.get('has_target', True)
    has_components = data_attributes.get('has_components', False)
    has_uncertainty = data_attributes.get('has_uncertainty', False)

    if 'prognose' in query_lower or 'eoy' in query_lower or has_uncertainty:
        return {
            'chart_type': 'Fan Chart (P10/P50/P90)',
            'time_visual_id': '11/12 Usikkerhetsvifte',
            'reasoning': 'Viser rullende regnskap YTD med Monte Carlo usikkerhetskonvolutt mot BAC.',
            'category': 'Time & Uncertainty'
        }
    elif 'akkumulert' in query_lower or 'ytd' in query_lower:
        return {
            'chart_type': 'Running Total Area Chart',
            'time_visual_id': '24 Running Total Area',
            'reasoning': 'Akkumulerer månedlige avvik gjennom året for å vise total belastning på kommunekassen.',
            'category': 'Time & Cumulative'
        }
    elif 'endring' in query_lower and ('tertial' in query_lower or 't1' in query_lower or 't2' in query_lower):
        return {
            'chart_type': 'Slope Graph',
            'time_visual_id': '40/41 Slope Graph',
            'reasoning': 'Viser helningsvinkel for endring i avvik fra T1 til T2 per omsorgssenter.',
            'category': 'Time & Change'
        }
    elif 'glidende' in query_lower or 'trend' in query_lower:
        return {
            'chart_type': 'Continuous Line + Moving Average (3M)',
            'time_visual_id': '11/18 Moving Average Line',
            'reasoning': 'Glatter ut månedlige tilfeldige svingninger (f.eks. utbetaling av feriepenger/refusjoner) for å vise underliggende drivtrend.',
            'category': 'Time & Trend'
        }
    elif 'sesong' in query_lower or 'måned' in query_lower:
        return {
            'chart_type': 'Cycle Plot / Sparklines',
            'time_visual_id': '38 Cycle Plot & 46 Sparklines',
            'reasoning': 'Sammenligner sesongmønstre (influensatopper jan-mars, ferieavvikling mai-juli) over flere år.',
            'category': 'Time & Cyclical'
        }
    elif 'komponent' in query_lower or 'fordeling' in query_lower or has_components:
        return {
            'chart_type': 'Stacked Area Chart (% of Total)',
            'time_visual_id': '16/17 Stacked Area Chart',
            'reasoning': 'Viser hvordan faste lønnskostnader, vikarbyrå og varer bygger opp det samlede forbruket over tid.',
            'category': 'Time & Part-to-Whole'
        }
    else:
        return {
            'chart_type': 'Continuous Line with Markers & Reference Line',
            'time_visual_id': '03/33 Line Chart w/ Reference Line',
            'reasoning': 'Klassisk kontinuerlig tidsrekke med budsjettlinje (BAC/PV) og direkte endepunktmerking.',
            'category': 'Time & Continuous'
        }

def create_time_series_fig(chart_type: str, df: pd.DataFrame, title: str = ''):
    """Genererer minimalistiske Tufte-godkjente Plotly figurer for tidsdata."""
    fig = go.Figure()
    
    if 'Fan' in chart_type:
        # Fan Chart P10/P50/P90
        fig.add_trace(go.Scatter(x=df['Måned'], y=df['P90'], mode='lines', line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=df['Måned'], y=df['P10'], mode='lines', fill='tonexty', fillcolor='rgba(211, 47, 47, 0.2)', line=dict(width=0), name='80% Usikkerhet (P10-P90)'))
        fig.add_trace(go.Scatter(x=df['Måned'], y=df['P50'], mode='lines+markers', line=dict(color='#D32F2F', width=3), name='Prognose (P50)'))
        fig.add_trace(go.Scatter(x=df['Måned'], y=df['Faktisk'], mode='lines+markers', line=dict(color='#1976D2', width=4), name='Faktisk YTD'))
    
    elif 'Running Total' in chart_type:
        fig.add_trace(go.Scatter(x=df['Måned'], y=df['Akkumulert_Faktisk'], fill='tozeroy', fillcolor='rgba(25, 118, 210, 0.25)', line=dict(color='#1976D2', width=3), name='Akkumulert YTD'))
        if 'Akkumulert_Budsjett' in df.columns:
            fig.add_trace(go.Scatter(x=df['Måned'], y=df['Akkumulert_Budsjett'], line=dict(color='#388E3C', width=2, dash='dash'), name='Akkumulert Budsjett'))
            
    elif 'Moving Average' in chart_type:
        fig.add_trace(go.Scatter(x=df['Måned'], y=df['Faktisk'], mode='lines+markers', line=dict(color='#9E9E9E', width=1.5), name='Månedlig Faktisk'))
        fig.add_trace(go.Scatter(x=df['Måned'], y=df['Moving_Avg_3M'], mode='lines', line=dict(color='#1976D2', width=3.5), name='3-Mnd Glidende Snitt'))
        
    elif 'Slope' in chart_type:
        for idx, row in df.iterrows():
            color = '#D32F2F' if row['T2'] < row['T1'] else '#388E3C'
            fig.add_trace(go.Scatter(x=['1. Tertial (T1)', '2. Tertial (T2)'], y=[row['T1'], row['T2']], mode='lines+markers+text', text=[f"{row['T1']:.1f}M", f"{row['T2']:.1f}M"], textposition=['middle left', 'middle right'], line=dict(color=color, width=3), name=row['Enhet']))
            
    else:
        # Default Continuous Line with Reference Line
        fig.add_trace(go.Scatter(x=df['Måned'], y=df['Faktisk'], mode='lines+markers', line=dict(color='#1976D2', width=3), name='Faktisk Forbruk'))
        if 'Budsjett' in df.columns:
            fig.add_trace(go.Scatter(x=df['Måned'], y=df['Budsjett'], mode='lines', line=dict(color='#388E3C', width=2, dash='dash'), name='Budsjett (BAC)'))

    # Tufte Minimalist Layout
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color='#1A237E')),
        paper_bgcolor='white',
        plot_bgcolor='white',
        margin=dict(l=40, r=40, t=50, b=40),
        xaxis=dict(showgrid=False, linecolor='#B0BEC5'),
        yaxis=dict(showgrid=True, gridcolor='#ECEFF1', zeroline=True, zerolinecolor='#90A4AE'),
        font=dict(family='Inter, Arial, sans-serif', size=12),
        showlegend=True
    )
    return fig
