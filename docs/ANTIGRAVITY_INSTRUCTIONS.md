# Antigravity AI Agent — Utviklingsinstruks

## Oppgave
Videreutvikle `MVP-AI-Helse-og-Mestring` ved å integrere LangGraph subgraphs og utvide FT Visual Sandbox med nye Plotly/Altair-komponenter, Time-Visuals (60 Ways to Visualize Time) og DAX-mål for Power BI.

## Kilder
- `app/visual_sandbox.py`: Inneholder FT Visual Vocabulary (36 Visuals Suite), Time-Visuals (60 Suite) og Power BI DAX-mål.
- `app/agent.py`: Inneholder Multi-Agent Supervisor (`SupervisorAgent` / `SupervisorRouterAgent`) med Time-Visuals Reasoning.
- `app/tools.py`: Inneholder SQL/RAG-verktøy og `recommend_visual_for_chat_response`.
- `app/schemas.py`: Pydantic v2 datakontrakter.
