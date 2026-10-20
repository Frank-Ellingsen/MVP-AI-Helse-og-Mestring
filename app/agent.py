# app/agent.py - Agent-orkestrering med Etikk, Personvern, RBAC, Verktøykall og Audit Log
import os
import sys
import json
from pathlib import Path
from typing import Optional
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
        write_audit_log,
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
        write_audit_log,
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


SYSTEM_PROMPT_GOVERNANCE = """
Du er en spesialist AI-økonomirådgiver for Helse og Mestring i Kristiansand kommune.

Sikkerhets- og etikkregler:
1. Personvern & GDPR: Du behandler KUN aggregerte regnskapstall. Ingen sensitiv personinformasjon om ansatte eller pasienter skal etterspørres eller vises.
2. Beslutningsstøtte (Human-in-the-Loop): Alle vedtak og omdisponeringer du foreslår er veiledende utkast. Endelig godkjenning ligger alltid hos Bystyret, Formannskapet eller Kommunedirektøren jf. kommuneloven § 14-5.
3. Audittrail: Alle spørringer og verktøykall logges uforanderlig til revisjonssporet for ettersyn av Agder Kontrollutvalg og Statsforvalteren.
4. Lovpålagte minstetjenester: Pass på at omstillings- og innsparingstiltak i helse og omsorg ikke reduserer tjenestetilbudet under lovpålagte minstekrav.

Dine kjernefunksjoner dekker hele den kommunale styringskjeden:
- Månedlig rapportering til enhetsledere (månedlige avvik og årsaksanalyse).
- Diagnose & Årsaksanalyse: Identifiser hvorfor avvik oppstår (f.eks. overtid art 109000, innleie/vikar art 110000, etterslep på sykelønnsrefusjon art 169000 eller BPA-vekst).
- Prediktiv EOY-prognose (End-of-Year): Fremskriv historiske månedsmønstre mot årsbudsjett.
- Preskriptive anbefalinger: Foreslå konkrete, lovlige tiltak i henhold til kommunelovens § 14-5 for å gjenreise budsjettbalansen innen 31.12.
- Lønnsbudsjettering: Beregn neste års lønnsrammer inkludert stillingshjemler (FTE), turnustillegg, AGA, pensjon (KLP/KKP) og deflator.
- Hierarkisk Drill-Down: Støtt spørringer og oppslag fra Sektornivå (Nivå 1) helt ned til Enkeltbilag/Transaksjonsnivå (Nivå 6).
- Budsjettomdisponering & Fullmaktseskalering mellom ansvarsområder.

Bruk verktøyene aktivt og oppgi alltid konkrete tall og kilder i svarene dine!
"""


def run_krs_agent(
    user_prompt: str,
    user_ctx: Optional[UserContext] = None,
    max_iterations: int = 8,
) -> str:
    """Kjører agenten med verktøykall, RBAC-sikkerhet og uforanderlig auditlogging."""
    if not os.getenv("GEMINI_API_KEY") and not USE_OLLAMA:
        return "Feil: GEMINI_API_KEY er ikke satt i miljøvariablene."

    if isinstance(user_ctx, str):
        user_ctx = UserContext(user_id="user_session", role=user_ctx)
    elif user_ctx is None:
        user_ctx = UserContext(user_id="user_session", role="direktor")

    write_audit_log(
        user_ctx.user_id,
        user_ctx.role,
        "AGENT_PROMPT",
        user_prompt,
        f"Startet AI-agent (ansvar={user_ctx.assigned_ansvar or 'Alle'})",
    )

    client = get_llm_client()
    role_info = (
        f"[Bruker-ID: {user_ctx.user_id} | Rolle: {user_ctx.role} | "
        f"Tildelt ansvar: {user_ctx.assigned_ansvar or 'Alle'}]"
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
                "description": "SQL SELECT-spørring mot SQLite-databasen for ERP-transaksjoner (med RBAC og GDPR-skjerming)",
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
                return msg.content or "Modellen returnerte et tomt svar."

            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments or "{}")

                print(f"  -> [{MODEL_NAME} Verktøykall] {func_name}({args})")

                try:
                    if func_name == "query_erp_transactions":
                        res = query_erp_transactions(ERPSQLQueryInput(**args), user_ctx=user_ctx)
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
                    else:
                        res = "Ukjent verktøy."
                except Exception as exc:
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
            return final_res.choices[0].message.content

        return "Kunne ikke levere endelig svar innenfor maksimalt antall iterasjoner."
    except Exception as e:
        return f"Feil i agent-kjøring: {str(e)}"


def run_krs_agent_secure(user_prompt: str, user_role: str = "direktor") -> str:
    """Bakoverkompatibel sikkerhetswrapper."""
    ctx = UserContext(user_id="user_session", role=user_role)
    return run_krs_agent(user_prompt=user_prompt, user_ctx=ctx)
