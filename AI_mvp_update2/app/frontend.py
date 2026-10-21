import streamlit as st
from app.visual_sandbox import get_dax_snippets, generate_waterfall_chart, generate_scatter_correlation, generate_lollipop_ranking

st.set_page_config(page_title="Kristiansand Kommune — Control Office Hub", layout="wide")
st.title("🏛️ Kristiansand Kommune — Control Office Hub & Visual Sandbox")

tabs = st.tabs([
    "1. AI-Chat", 
    "2. Månedsoversikt & Trafikklys", 
    "3. FT Visual Vocabulary Sandbox (36 Suite)", 
    "4. EOY & Lønnsbudsjett", 
    "5. 6-Nivås Drill-Down", 
    "6. Omdisponering & HITL", 
    "7. Audit-Logg (Revisor)"
])

with tabs[2]:
    st.header("📊 FT Visual Vocabulary Sandbox — Helse og Mestring (Kristiansand)")
    st.markdown("**Edward Tufte Data-Ink Ratio + 9 FT Kognitive Kategorier (36 Visuals Suite)**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(generate_waterfall_chart(), use_container_width=True)
        st.plotly_chart(generate_scatter_correlation(), use_container_width=True)
    with col2:
        st.plotly_chart(generate_lollipop_ranking(), use_container_width=True)
        
        st.subheader("💡 Ferdige Power BI DAX-Mål")
        dax = get_dax_snippets()
        st.code(dax["HM_EOY_Avvik_Prognose"], language="dax")
        st.code(dax["HM_Cost_Performance_Index"], language="dax")
