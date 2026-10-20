"""
AI_KOM - LangGraph Multi-Agent & Looped AI Engineering Framework
Kristiansand Kommune — Helse og Mestring AI Økonomistyring
"""

import json
from typing import Annotated, TypedDict, Literal, List, Dict, Any
from dataclasses import dataclass
import pydantic

# ============================================================================
# 1. STATE DEFINITION & CHECKPOINTING (Audit Trail)
# ============================================================================

class AgentState(TypedDict):
    messages: List[Dict[str, Any]]
    bruker_id: str
    rolle: str  # 'enhetsleder', 'kommunalsjef', 'okonomidirektor', 'revisor'
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
        last_msg = state["messages"][-1]["content"].lower()
        if "omdisponering" in last_msg or "overføre" in last_msg or "saksframlegg" in last_msg:
            return "saksbehandling_agent"
        elif "prognose" in last_msg or "eoy" in last_msg or "framsikt" in last_msg:
            return "framsikt_eoy_agent"
        else:
            return "regnskap_erp_agent"

class RegnskapERPAgent:
    """Specialized Subgraph for Unit4/Visma SQL queries with Self-Correction Loop."""
    def execute_sql_with_loop(self, state: AgentState) -> AgentState:
        # Loop Engineering: Bounded Self-Correction
        if state["error_count"] >= state["max_retries"]:
            state["final_response"] = "⚠️ For mange SQL-spørrefeil. Forespørselen sendes til manuell gjennomgang."
            return state
        
        # Simulerer SQL execution & self-correction
        try:
            # Sjekker RBAC-tilgang
            where_clause = f"WHERE ansvar_id = '{state['ansvar_id']}'" if state['rolle'] == 'enhetsleder' else ""
            state["sql_query"] = f"SELECT * FROM fact_erp_transactions {where_clause} LIMIT 10;"
            state["sql_result"] = [{"ansvar": state["ansvar_id"], "belop": 450000, "art": "1090 (Overtid)"}]
            state["final_response"] = f"Funnet 10 transaksjoner for ansvar {state['ansvar_id']}."
        except Exception as e:
            state["error_count"] += 1
            # Reflection step: Feed error back to LLM for self-correction in next turn
            state["messages"].append({"role": "system", "content": f"SQL Error encountered: {str(e)}. Retrying query generation..."})
            return self.execute_sql_with_loop(state)
            
        return state

class SaksbehandlingAgent:
    """Specialized Subgraph for Kommuneloven § 14-5 & Human-in-the-Loop Intercepts."""
    def process_reallocation(self, state: AgentState) -> AgentState:
        # Check authority thresholds (Kommuneloven § 14-5)
        # Human-in-the-Loop Interrupt
        if not state["approval_granted"]:
            state["requires_approval"] = True
            state["final_response"] = "⏸️ Omdisponeringsforslaget krever politisk godkjenning fra Bystyret (Kommuneloven § 14-5). Venter på saksbehandlers bekreftelse."
            return state
            
        state["final_response"] = "✅ Omdisponering godkjent og ført i audit_log."
        return state

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
        "requires_approval": state["requires_approval"]
    }
    print(f"[AUDIT LOGGED]: {json.dumps(log_entry)}")

if __name__ == "__main__":
    # Demo pipeline run
    init_state: AgentState = {
        "messages": [{"role": "user", "content": "Kjør avviksanalyse for Randesund Omsorgssenter og omdisponer 100kNOK"}],
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
        "final_response": ""
    }
    
    supervisor = SupervisorAgent()
    target_agent = supervisor.route(init_state)
    print(f"Ruted query to agent: {target_agent}")
