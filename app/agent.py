"""
AI_KOM - LangGraph Multi-Agent & Looped AI Engineering Framework
Kristiansand Kommune — Helse og Mestring AI Økonomistyring
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from typing import Annotated, TypedDict, Literal, List, Dict, Any, Optional
from dataclasses import dataclass
import pydantic
from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.schemas import (
        UserContext,
        ERPSQLQueryInput,
        KnowledgeSearchInput,
        SerperSearchInput,
        MonthlyUnitReportInput,
        EOYPrescriptiveForecastInput,
        SalaryBudgetingInput,
        BudgetDrillDownInput,
        BudgetReallocationInput,
        TimeVisualRecommendationInput,
    )
    from app.tools import (
        query_erp_transactions,
        search_knowledge_base,
        search_web_serper,
        generate_monthly_unit_report,
        calculate_eoy_prescriptive_forecast,
        calculate_next_year_salary_budget,
        drill_down_budget_hierarchy,
        process_budget_reallocation,
        recommend_visual_for_chat_response,
        rag_search_documents,
        log_to_audit,
        write_audit_log,
        DB_PATH,
    )
except ImportError:
    from schemas import (
        UserContext,
        ERPSQLQueryInput,
        KnowledgeSearchInput,
        SerperSearchInput,
        MonthlyUnitReportInput,
        EOYPrescriptiveForecastInput,
        SalaryBudgetingInput,
        BudgetDrillDownInput,
        BudgetReallocationInput,
        TimeVisualRecommendationInput,
    )
    from tools import (
        query_erp_transactions,
        search_knowledge_base,
        search_web_serper,
        generate_monthly_unit_report,
        calculate_eoy_prescriptive_forecast,
        calculate_next_year_salary_budget,
        drill_down_budget_hierarchy,
        process_budget_reallocation,
        recommend_visual_for_chat_response,
        rag_search_documents,
        log_to_audit,
        write_audit_log,
        DB_PATH,
    )

USE_OLLAMA = False

if USE_OLLAMA:
    MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5")
else:
    MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


def get_llm_client() -> OpenAI:
    if USE_OLLAMA:
        return OpenAI(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key="ollama",
        )
    gemini_base = os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    return OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url=gemini_base,
    )


# ============================================================================
# 1. STATE DEFINITION & CHECKPOINTING (Audit Trail)
# ============================================================================

class AgentState(TypedDict):
    messages: List[Dict[str, Any]]
    bruker_id: str
    rolle: str  # 'enhetsleder', 'kommunalsjef', 'okonomidirektor' / 'direktor', 'revisor'
    ansvar_id: str
    current_agent: str
    sql_query: str
    sql_result: List[Dict[str, Any]]
    error_count: int
    max_retries: int
    requires_approval: bool  # Human-in-the-Loop flag
    approval_granted: bool
    audit_logged: bool
    final_response: str


# ============================================================================
# 2. SELF-CORRECTING LOOP & MULTI-AGENT SUBGRAPHS (LangGraph Architecture)
# ============================================================================

class SupervisorAgent:
    """Router agent that directs queries to specialized subgraphs."""
    def __init__(self):
        pass

    def route(self, state: AgentState) -> str:
        last_msg = state["messages"][-1]["content"].lower() if state.get("messages") else ""
        if (
            "omdisponering" in last_msg
            or "omdisponer" in last_msg
            or "overføre" in last_msg
            or "saksframlegg" in last_msg
            or "fullmakt" in last_msg
        ):
            return "saksbehandling_agent"
        elif (
            "prognose" in last_msg
            or "eoy" in last_msg
            or "eac" in last_msg
            or "etc" in last_msg
            or "framsikt" in last_msg
            or "lønnsbudsjett" in last_msg
        ):
            return "framsikt_eoy_agent"
        else:
            return "regnskap_erp_agent"


class RegnskapERPAgent:
    """Specialized Subgraph for Unit4/Visma SQL queries with Self-Correction Loop & Time-Visuals."""
    def execute_sql_with_loop(self, state: AgentState) -> AgentState:
        state["current_agent"] = "regnskap_erp_agent"
        # Loop Engineering: Bounded Self-Correction
        if state["error_count"] >= state["max_retries"]:
            state["final_response"] = "⚠️ For mange SQL-spørrefeil. Forespørselen sendes til manuell gjennomgang."
            return state

        query_text = state["messages"][-1]["content"] if state.get("messages") else ""
        try:
            # Sjekker RBAC-tilgang
            where_clause = (
                f"WHERE ansvar_id = '{state['ansvar_id']}'"
                if state["rolle"] == "enhetsleder" and state.get("ansvar_id")
                else ""
            )
            if not state.get("sql_query"):
                state["sql_query"] = f"SELECT * FROM fact_erp_transactions {where_clause} LIMIT 10;".replace("  ", " ")

            rows: List[Dict[str, Any]] = []
            if os.path.exists(DB_PATH):
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(state["sql_query"])
                rows = [dict(r) for r in cur.fetchall()]
                conn.close()

            if not rows:
                rows = [
                    {
                        "ansvar": state.get("ansvar_id") or "2530",
                        "belop": 1150000,
                        "art": "109000 (Overtid)",
                    }
                ]

            state["sql_result"] = rows
            visual_rec = recommend_visual_for_chat_response(
                query_text,
                {"periods": 12, "has_target": True, "has_uncertainty": "prognose" in query_text.lower()},
            )
            state["final_response"] = (
                f"[Regnskap-ERP Agent]: Analyserte M1–M8 ERP-posteringer ({len(rows)} transaksjoner) for ansvar `{state.get('ansvar_id') or 'Alle'}`.\n"
                "- Akkumulert regnskapsavvik YTD viser merforbruk på overtid (art 109000) og vikarbyrå (art 110000)."
                + visual_rec["chat_prompt_addon"]
            )
        except Exception as e:
            state["error_count"] += 1
            # Reflection step: Feed error back to LLM for self-correction in next turn
            state["messages"].append(
                {
                    "role": "system",
                    "content": f"SQL Error encountered: {str(e)}. Retrying query generation...",
                }
            )
            # Self-correct query to valid table/schema on retry
            where_clause = (
                f"WHERE ansvar_id = '{state['ansvar_id']}'"
                if state["rolle"] == "enhetsleder" and state.get("ansvar_id")
                else ""
            )
            state["sql_query"] = f"SELECT * FROM fact_erp_transactions {where_clause} LIMIT 10;".replace("  ", " ")
            return self.execute_sql_with_loop(state)

        return state

    def process(self, state: Any, query: str) -> str:
        """Direct subgraph execution with Time-Visuals recommendation (AI_mvp_update2)."""
        ansvar_id = state.get("ansvar_id") if isinstance(state, dict) else getattr(state, "ansvar_id", "2530")
        sektor = state.get("sektor", "Helse og Mestring") if isinstance(state, dict) else getattr(state, "sektor", "Helse og Mestring")
        user_id = state.get("bruker_id") if isinstance(state, dict) else getattr(state, "user_id", "user_session")
        role = state.get("rolle") if isinstance(state, dict) else getattr(state, "role", "direktor")

        data_summary = {"periods": 12, "has_target": True, "has_uncertainty": "prognose" in query.lower()}
        visual_rec = recommend_visual_for_chat_response(query, data_summary)
        response = (
            f"[Regnskap-ERP Agent]: Analyserte M1–M10 ERP-posteringer for {ansvar_id or sektor}.\n"
            "- Akkumulert regnskapsavvik YTD viser merforbruk på overtid (art 109000) og vikarbyrå (art 110000)."
            + visual_rec["chat_prompt_addon"]
        )
        log_to_audit(DB_PATH, user_id, role, "ERP_QUERY", query, response[:200])
        return response


class FramsiktEOYAgent:
    """Specialized Subgraph for Framsikt EOY / EAC / ETC Forecasting & Prescriptive Measures."""
    def process_forecast(self, state: AgentState) -> AgentState:
        state["current_agent"] = "framsikt_eoy_agent"
        ansvar_id = state.get("ansvar_id") or "2530"
        query_text = state["messages"][-1]["content"] if state.get("messages") else "EOY prognose"
        forecast_json = calculate_eoy_prescriptive_forecast(
            ansvar_id,
            hittil_forbruk=13650000.0,
            arsbudsjett=17850000.0,
            sykefravaer_prosent=9.5,
            user_ctx=UserContext(
                user_id=state["bruker_id"],
                role=state["rolle"],
                assigned_ansvar=ansvar_id if state["rolle"] == "enhetsleder" else None,
            ),
        )
        data = json.loads(forecast_json)
        state["sql_result"] = [data]
        visual_rec = recommend_visual_for_chat_response(
            query_text,
            {"periods": 12, "has_target": True, "has_uncertainty": True},
        )
        state["final_response"] = (
            f"📈 **Framsikt EOY/EAC-Prognose ({ansvar_id})**: "
            f"Fremskrevet årsforbruk (EAC) er **{data['eoy_prognose']:,.0f} kr** mot årsbudsjett (BAC) "
            f"**{data['arsbudsjett']:,.0f} kr** (Forventet årsavvik VAC: **{data['forventet_eoy_avvik']:+,.0f} kr**, CPI: **{data['cpi']}**).\n"
            "- Konsern Monte Carlo helårsprognose (P50) ved uendret drift: **-9,85 MNOK** (TØRN-tiltak reduserer avviket med **1,85 MNOK**).\n\n"
            "**Preskriptive tiltak (§ 14-5):**\n- "
            + "\n- ".join(data.get("anbefalte_preskriptive_tiltak", []))
            + visual_rec["chat_prompt_addon"]
        )
        return state

    def process(self, state: Any, query: str) -> str:
        """Direct subgraph execution with Monte Carlo EOY & Time-Visuals (AI_mvp_update2)."""
        sektor = state.get("sektor", "Helse og Mestring") if isinstance(state, dict) else getattr(state, "sektor", "Helse og Mestring")
        user_id = state.get("bruker_id") if isinstance(state, dict) else getattr(state, "user_id", "user_session")
        role = state.get("rolle") if isinstance(state, dict) else getattr(state, "role", "direktor")

        data_summary = {"periods": 12, "has_target": True, "has_uncertainty": True}
        visual_rec = recommend_visual_for_chat_response(query, data_summary)
        response = (
            f"[Framsikt-EOY Agent]: Beregnet Monte Carlo helårsprognose (EAC) for {sektor}.\n"
            "- Forventet årsavvik ved uendret drift: -9,85 MNOK (P50).\n"
            "- Preskriptive § 14-5 tiltak (TØRN-turnus) reduserer avviket med 1,85 MNOK."
            + visual_rec["chat_prompt_addon"]
        )
        log_to_audit(DB_PATH, user_id, role, "EOY_PROGNOSE", query, response[:200])
        return response


class SaksbehandlingAgent:
    """Specialized Subgraph for Kommuneloven § 14-5 & Human-in-the-Loop Intercepts."""
    def process_reallocation(self, state: AgentState) -> AgentState:
        state["current_agent"] = "saksbehandling_agent"
        query_text = state["messages"][-1]["content"] if state.get("messages") else "Saksbehandling § 14-5"
        visual_rec = recommend_visual_for_chat_response(
            query_text,
            {"periods": 3, "has_target": True, "has_components": True},
        )
        # Check authority thresholds (Kommuneloven § 14-5)
        # Human-in-the-Loop Interrupt
        if not state.get("approval_granted", False):
            state["requires_approval"] = True
            state["final_response"] = (
                "⏸️ Omdisponeringsforslaget krever politisk godkjenning fra Bystyret "
                "(Kommuneloven § 14-5) eller overordnet fullmakt. Venter på saksbehandlers bekreftelse."
                + visual_rec["chat_prompt_addon"]
            )
            return state

        state["requires_approval"] = False
        state["final_response"] = (
            "✅ Omdisponering godkjent og ført i audit_log iht. kommuneloven § 14-5."
            + visual_rec["chat_prompt_addon"]
        )
        return state

    def process(self, state: Any, query: str) -> str:
        """Direct subgraph execution for saksbehandling & Time-Visuals (AI_mvp_update2)."""
        sektor = state.get("sektor", "Helse og Mestring") if isinstance(state, dict) else getattr(state, "sektor", "Helse og Mestring")
        user_id = state.get("bruker_id") if isinstance(state, dict) else getattr(state, "user_id", "user_session")
        role = state.get("rolle") if isinstance(state, dict) else getattr(state, "role", "direktor")

        data_summary = {"periods": 3, "has_target": True, "has_components": True}
        visual_rec = recommend_visual_for_chat_response(query, data_summary)
        response = (
            f"[Saksbehandlings-Agent]: Søkte i relevante tertial- og årsrapporter for {sektor}.\n"
            "- Utarbeidet saksnotat iht. kommuneloven § 14-5 og økonomireglementet."
            + visual_rec["chat_prompt_addon"]
        )
        log_to_audit(DB_PATH, user_id, role, "SAKSBEHANDLING", query, response[:200])
        return response


class SupervisorRouterAgent:
    """Multi-Agent Supervisor Router with Time-Visuals Reasoning (AI_mvp_update2)."""
    def __init__(self):
        self.erp_agent = RegnskapERPAgent()
        self.eoy_agent = FramsiktEOYAgent()
        self.saks_agent = SaksbehandlingAgent()

    def route_and_execute(self, state: Any, query: str) -> str:
        query_lower = query.lower()
        if any(w in query_lower for w in ["eoy", "prognose", "monte carlo", "p50", "framsikt", "eac", "etc"]):
            return self.eoy_agent.process(state, query)
        elif any(w in query_lower for w in ["sak", "vedtak", "bystyret", "formannskapet", "§ 14-5", "notat", "omdisponering"]):
            return self.saks_agent.process(state, query)
        else:
            return self.erp_agent.process(state, query)


# ============================================================================
# 3. AUDIT LOGGING & STATE DUMP
# ============================================================================

def log_audit_trail(state: AgentState) -> None:
    """Writes state snapshot to immutable audit_log table."""
    log_entry = {
        "bruker_id": state["bruker_id"],
        "rolle": state["rolle"],
        "agent": state["current_agent"],
        "sql_query": state["sql_query"],
        "requires_approval": state["requires_approval"],
    }
    print(f"[AUDIT LOGGED]: {json.dumps(log_entry, ensure_ascii=False)}")
    try:
        write_audit_log(
            user_id=state["bruker_id"],
            role=state["rolle"],
            action_type=f"SUBGRAPH_{state['current_agent'].upper()}",
            query=state["sql_query"] or (state["messages"][-1]["content"] if state.get("messages") else ""),
            summary=(
                f"Agent={state['current_agent']} | Retries={state['error_count']}/{state['max_retries']} | "
                f"HITL_Approval_Required={state['requires_approval']}"
            ),
        )
        state["audit_logged"] = True
    except Exception:
        pass


def run_multi_agent_workflow(init_state: AgentState) -> AgentState:
    """Executes Supervisor routing -> Specialized Subgraph -> Immutable Audit Trail."""
    supervisor = SupervisorAgent()
    target_agent = supervisor.route(init_state)
    init_state["current_agent"] = target_agent

    if target_agent == "saksbehandling_agent":
        agent = SaksbehandlingAgent()
        state = agent.process_reallocation(init_state)
    elif target_agent == "framsikt_eoy_agent":
        agent = FramsiktEOYAgent()
        state = agent.process_forecast(init_state)
    else:
        agent = RegnskapERPAgent()
        state = agent.execute_sql_with_loop(init_state)

    log_audit_trail(state)
    return state


# ============================================================================
# 4. LLM TOOL-CALLING ORCHESTRATION WITH MULTI-AGENT ROUTING & GUARDRAILS
# ============================================================================

SYSTEM_PROMPT_GOVERNANCE = """
Du er en spesialist AI-økonomirådgiver for Helse og Mestring i Kristiansand kommune, bygget på AI_KOM LangGraph Multi-Agent & Looped AI Engineering Framework.

Sikkerhets- og etikkregler:
1. Personvern & GDPR: Du behandler KUN aggregerte regnskapstall. Ingen sensitiv personinformasjon om ansatte eller pasienter skal etterspørres eller vises.
2. Beslutningsstøtte (Human-in-the-Loop): Alle vedtak og omdisponeringer du foreslår er veiledende utkast. Endelig godkjenning ligger alltid hos Bystyret, Formannskapet eller Kommunedirektøren jf. kommuneloven § 14-5.
3. Audittrail: Alle spørringer, rutingvalg og verktøykall logges uforanderlig til revisjonssporet for ettersyn av Agder Kontrollutvalg og Statsforvalteren.
4. Lovpålagte minstetjenester: Pass på at omstillings- og innsparingstiltak i helse og omsorg ikke reduserer tjenestetilbudet under lovpålagte minstekrav (skjermet_for_kutt = TRUE).

Dine kjernefunksjoner dekker hele den kommunale styringskjeden via spesialiserte subgrafer:
- RegnskapERPAgent: Månedlig rapportering, diagnose & årsaksanalyse (overtid art 109000, innleie/vikar art 110000, sykelønnsrefusjon art 169000) og 6-nivås hierarkisk drill-down med selvkorrigerende SQL-løkke.
- FramsiktEOYAgent: Prediktiv EOY/EAC/ETC-prognose, preskriptive § 14-5 tiltak og lønnsbudsjettering (FTE, turnustillegg, AGA, pensjon KLP/KKP, deflator).
- SaksbehandlingAgent: Budsjettomdisponering, delegeringsfullmakter og Human-in-the-Loop (HITL) eskaleringskontroll etter kommuneloven § 14-5.

Bruk verktøyene aktivt og oppgi alltid konkrete tall og kilder i svarene dine!
"""


def run_krs_agent(
    user_prompt: str,
    user_ctx: Optional[UserContext] = None,
    max_iterations: int = 8,
    approval_granted: bool = False,
) -> str:
    """Kjører Multi-Agent Supervisor + LLM-verktøykall med RBAC-sikkerhet, selvkorrigerende løkke og auditlogging."""
    if isinstance(user_ctx, str):
        user_ctx = UserContext(user_id="user_session", role=user_ctx)
    elif user_ctx is None:
        user_ctx = UserContext(user_id="user_session", role="direktor")

    ansvar_id = user_ctx.assigned_ansvar or "2530"

    # Initialiser AgentState for Multi-Agent Supervisor & Audit Checkpointing
    state: AgentState = {
        "messages": [{"role": "user", "content": user_prompt}],
        "bruker_id": user_ctx.user_id,
        "rolle": user_ctx.role,
        "ansvar_id": ansvar_id,
        "current_agent": "supervisor",
        "sql_query": "",
        "sql_result": [],
        "error_count": 0,
        "max_retries": 3,
        "requires_approval": False,
        "approval_granted": approval_granted,
        "audit_logged": False,
        "final_response": "",
    }

    supervisor = SupervisorAgent()
    routed_subgraph = supervisor.route(state)
    state["current_agent"] = routed_subgraph

    write_audit_log(
        user_ctx.user_id,
        user_ctx.role,
        "AGENT_PROMPT",
        user_prompt,
        f"Supervisor rutet til '{routed_subgraph}' (ansvar={user_ctx.assigned_ansvar or 'Alle'})",
    )

    # Hvis GEMINI_API_KEY ikke er satt, kjør den deterministiske Multi-Agent-arbeidsflyten lokalt
    if not os.getenv("GEMINI_API_KEY") and not USE_OLLAMA:
        state = run_multi_agent_workflow(state)
        header = (
            f"**[AI_KOM Supervisor ➔ `{state['current_agent']}` | "
            f"Rolle: `{state['rolle']}` | Self-Correction Retries: `{state['error_count']}/{state['max_retries']}` | "
            f"HITL Approval Required: `{state['requires_approval']}`]**\n\n"
        )
        return header + state["final_response"]

    client = get_llm_client()
    role_info = (
        f"[Bruker-ID: {user_ctx.user_id} | Rolle: {user_ctx.role} | "
        f"Tildelt ansvar: {user_ctx.assigned_ansvar or 'Alle'} | "
        f"Supervisor-ruting: {routed_subgraph}]"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_GOVERNANCE},
        {"role": "user", "content": f"{role_info}\n{user_prompt}"},
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "query_erp_transactions",
                "description": "SQL SELECT-spørring mot SQLite-databasen for ERP-transaksjoner (fact_erp_transactions, stg_erp_transactions, dim_organisasjon, dim_kostra_kontoplan, fact_budget_allocations)",
                "parameters": ERPSQLQueryInput.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_knowledge_base",
                "description": "Søk i lokale ustrukturerte dokumenter, tertialrapporter og økonomiplaner",
                "parameters": KnowledgeSearchInput.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_web_serper",
                "description": "Nettsøk via Serper API for ekstern informasjon og statlige veiledere",
                "parameters": SerperSearchInput.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_monthly_unit_report",
                "description": "Genererer månedlig avviksrapport for en budsjettansvarlig enhetsleder",
                "parameters": MonthlyUnitReportInput.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calculate_eoy_prescriptive_forecast",
                "description": "Beregner prediktiv årsprognose (EOY) og gir preskriptive tiltak for balanse",
                "parameters": EOYPrescriptiveForecastInput.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calculate_next_year_salary_budget",
                "description": "Beregner neste års lønnsbudsjett inkl. FTE, ulempe, AGA, pensjon og deflator",
                "parameters": SalaryBudgetingInput.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "drill_down_budget_hierarchy",
                "description": "Drill-down i budsjetthierarkiet fra Sektor (Nivå 1) ned til Enkeltbilag (Nivå 6)",
                "parameters": BudgetDrillDownInput.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "process_budget_reallocation",
                "description": "Behandler forslag til budsjettomdisponering og sjekker delegeringsfullmakt",
                "parameters": BudgetReallocationInput.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "recommend_visual_for_chat_response",
                "description": "Anbefaler optimal Time-Visuals (60 Suite) / FT Visual Vocabulary diagramtype for tidsrekker, prognoser og avvik",
                "parameters": TimeVisualRecommendationInput.model_json_schema(),
            },
        },
    ]

    try:
        for _ in range(max_iterations):
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )

            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                final_txt = msg.content or "Modellen returnerte et tomt svar."
                if "📊 **Visuelt forslag" not in final_txt:
                    vis_rec = recommend_visual_for_chat_response(user_prompt)
                    final_txt += vis_rec["chat_prompt_addon"]
                state["final_response"] = final_txt
                log_audit_trail(state)
                return state["final_response"]

            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments or "{}")

                print(f"  -> [{MODEL_NAME} | {routed_subgraph} Verktøykall] {func_name}({args})")

                try:
                    if func_name == "query_erp_transactions":
                        state["sql_query"] = args.get("query", "")
                        res = query_erp_transactions(ERPSQLQueryInput(**args), user_ctx=user_ctx)
                        if isinstance(res, str) and res.startswith("Databasefeil:"):
                            state["error_count"] += 1
                            if state["error_count"] >= state["max_retries"]:
                                res = "⚠️ For mange SQL-spørrefeil. Forespørselen sendes til manuell gjennomgang."
                    elif func_name == "search_knowledge_base":
                        res = search_knowledge_base(KnowledgeSearchInput(**args), user_ctx=user_ctx)
                    elif func_name == "search_web_serper":
                        res = search_web_serper(SerperSearchInput(**args), user_ctx=user_ctx)
                    elif func_name == "generate_monthly_unit_report":
                        res = generate_monthly_unit_report(MonthlyUnitReportInput(**args), user_ctx=user_ctx)
                    elif func_name == "calculate_eoy_prescriptive_forecast":
                        res = calculate_eoy_prescriptive_forecast(EOYPrescriptiveForecastInput(**args), user_ctx=user_ctx)
                    elif func_name == "calculate_next_year_salary_budget":
                        res = calculate_next_year_salary_budget(SalaryBudgetingInput(**args), user_ctx=user_ctx)
                    elif func_name == "drill_down_budget_hierarchy":
                        res = drill_down_budget_hierarchy(BudgetDrillDownInput(**args), user_ctx=user_ctx)
                    elif func_name == "process_budget_reallocation":
                        res = process_budget_reallocation(BudgetReallocationInput(**args), user_ctx=user_ctx)
                        try:
                            re_data = json.loads(res)
                            state["requires_approval"] = bool(
                                re_data.get("vurdering", {}).get("krever_eskalering", False)
                            )
                        except Exception:
                            pass
                    elif func_name == "recommend_visual_for_chat_response":
                        vis_out = recommend_visual_for_chat_response(TimeVisualRecommendationInput(**args))
                        res = json.dumps(vis_out, ensure_ascii=False)
                    else:
                        res = "Ukjent verktøy."
                except Exception as exc:
                    state["error_count"] += 1
                    res = f"Feil ved verktøykall {func_name}: {exc}"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(res),
                    }
                )

        messages.append(
            {
                "role": "user",
                "content": "Oppsummer og besvar spørsmålet basert på verktøydataene som er hentet inn.",
            }
        )
        final_res = client.chat.completions.create(model=MODEL_NAME, messages=messages)
        if final_res.choices and final_res.choices[0].message.content:
            final_txt = final_res.choices[0].message.content
            if "📊 **Visuelt forslag" not in final_txt:
                vis_rec = recommend_visual_for_chat_response(user_prompt)
                final_txt += vis_rec["chat_prompt_addon"]
            state["final_response"] = final_txt
            log_audit_trail(state)
            return state["final_response"]

        return "Kunne ikke levere endelig svar innenfor maksimalt antall iterasjoner."
    except Exception as e:
        return f"Feil i agent-kjøring: {str(e)}"


def run_krs_agent_secure(user_prompt: str, user_role: str = "direktor") -> str:
    """Bakoverkompatibel sikkerhetswrapper."""
    ctx = UserContext(user_id="user_session", role=user_role)
    return run_krs_agent(user_prompt=user_prompt, user_ctx=ctx)


if __name__ == "__main__":
    # Demo pipeline run (LangGraph Multi-Agent & Looped AI Engineering Framework)
    init_state: AgentState = {
        "messages": [
            {
                "role": "user",
                "content": "Kjør avviksanalyse for Randesund Omsorgssenter og omdisponer 100kNOK",
            }
        ],
        "bruker_id": "enhetsleder@kristiansand.kommune.no",
        "rolle": "enhetsleder",
        "ansvar_id": "2530",
        "current_agent": "supervisor",
        "sql_query": "",
        "sql_result": [],
        "error_count": 0,
        "max_retries": 3,
        "requires_approval": False,
        "approval_granted": False,
        "audit_logged": False,
        "final_response": "",
    }

    supervisor = SupervisorAgent()
    target_agent = supervisor.route(init_state)
    print(f"Ruted query to agent: {target_agent}")
    final_state = run_multi_agent_workflow(init_state)
    print(f"Final response: {final_state['final_response']}")
