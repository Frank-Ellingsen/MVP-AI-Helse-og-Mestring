# Systemarkitektur — Control Office Hub & Multi-Agent System

## Multi-Agent Subgraphs in LangGraph
- **Supervisor Router**: Dirigerer spørringer til kjerneagenter.
- **RegnskapERPAgent**: Håndterer SQL mot ERP med Bounded Loop & Auto-Self-Correction.
- **SaksbehandlingAgent**: Utarbeider saksframlegg jf. Kommuneloven § 14-5.

## Loop Engineering
- **Bounded Loops**: `max_iterations = 5`
- **Self-Correction**: Fanger `OperationalError` og reparerer SQL
- **HITL Interrupt**: Venter på saksbehandlers godkjenning ved omdisponeringer
- **Audit Logging**: Uforanderlig `audit_log` for Kommunerevisjonen (NKRF)


---

### 📈 Time-Visuals Engine & Visual Chat Reasoning (Time-Visuals.pdf)

Systemet er utvidet med en **Visual Explanation Engine** basert på **Time-Visuals.pdf (60 Ways to Visualize Time)** av Alan Smith / Financial Times:

1. **Automatisk Visualiseringsanbefaling i AI-Chaten**:
   * Når en bruker stiller spørsmål om tidsrekker, månedlige avvik, rullende prognoser eller tertialvise endringer, kobler AI-agenten automatisk på .
   * Agenten returnerer både faglig tekstforklaring, presis hjemmelshenvisning (§ 14-5) og en kognitivt optimaliserte visualiseringsanbefaling.

2. **Oversikt over Integrerte Tidsdiagrammer**:
   * **Fan Chart (P10/P50/P90)**: Monte Carlo usikkerhetsvifte for rullende helårsprognose.
   * **Running Total Area Chart**: Akkumulert merforbruk YTD mot periodisert ramme.
   * **Slope Graph**: Endring i avvik og CPI fra 1. tertial til 2. tertial.
   * **Continuous Line + 3M Moving Average**: Glatter ut støy fra sluttoppgjør og utbetalinger for å avdekke underliggende lønnstrend.
   * **Cycle Plot & Sparklines**: Edward Tufte-mikrografer som sammenligner sesongmønstre (f.eks. influensatopper jan-mars vs ferieavvikling).


---

### 📈 Time-Visuals Engine & Visual Chat Reasoning (Time-Visuals.pdf)

Systemet er utvidet med en **Visual Explanation Engine** basert på **Time-Visuals.pdf (60 Ways to Visualize Time)** av Alan Smith / Financial Times:

1. **Automatisk Visualiseringsanbefaling i AI-Chaten**:
   * Når en bruker stiller spørsmål om tidsrekker, månedlige avvik, rullende prognoser eller tertialvise endringer, kobler AI-agenten automatisk på .
   * Agenten returnerer både faglig tekstforklaring, presis hjemmelshenvisning (§ 14-5) og en kognitivt optimalisert visualiseringsanbefaling.

2. **Oversikt over Integrerte Tidsdiagrammer**:
   * **Fan Chart (P10/P50/P90)**: Monte Carlo usikkerhetsvifte for rullende helårsprognose.
   * **Running Total Area Chart**: Akkumulert merforbruk YTD mot periodisert ramme.
   * **Slope Graph**: Endring i avvik og CPI fra 1. tertial til 2. tertial.
   * **Continuous Line + 3M Moving Average**: Glatter ut støy fra sluttoppgjør og utbetalinger for å avdekke underliggende lønnstrend.
   * **Cycle Plot & Sparklines**: Edward Tufte-mikrografer som sammenligner sesongmønstre (f.eks. influensatopper jan-mars vs ferieavvikling).
