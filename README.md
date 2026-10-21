# Kristiansand Kommune - Helse og Mestring AI Okonomiradgiver (MVP)

En agentisk AI-beslutningsstottemodell for virksomhetsstyring og okonomioppfolging i Helse og Mestring i Kristiansand kommune. Systemet kombinerer eksakte SQL-sporringer mot ERP-transaksjoner, RAG-oppslag i kommunale styringsdokumenter og tertialrapporter, nettsok via Serper.dev API, maanedlig avviksanalyse med RAG-trafikklys, Financial Times Visual Vocabulary, prediktiv aarsprognose (EOY), preskriptive balansetiltak (§ 14-5), lonnsbudsjettering, 6-nivas interaktiv drill-down, automatisk sjekk av omdisponeringsfullmakter (Kommunedirektor vs. Bystyret/Formannskapet), rollestyring (RBAC) og uforanderlig audit-logg jf. arkivlova.

---

## Arkitektur og Faseinndeling (Uke 1-16 + Day-2 Operations)

Systemet er bygget i trad med AI Engineering Stage-Gate Framework:

- Fase 1 (Uke 1-4) - Pydantic v2 og Verktoy-kontrakter: Strict typevalidering (schemas.py), feilhandling og parameteriserte SQL-oppslag.
- Fase 2 (Uke 5-8) - Grounded RAG og Evidens: Hybrid RAG-arkitektur (tools.py) som kombinerer ustrukturerte dokumenter med strukturerte transaksjonsdata.
- Fase 3 (Uke 9-12) - Agentorkestrering, RBAC og HITL: Tilstandsbasert agentlokke (agent.py), rollebasert tilgangskontroll (enhetsleder, kommunalsjef, okonomidirektor), automatisk eskaleringssjekk for politisk vedtak, og uforanderlig revisjonslogg (audit_log).
- Fase 4 (Uke 13-16) - Produksjon, Containerisering og Eksport: Docker-oppsett (Dockerfile, docker-compose.yml), automatisert PDF- og PowerPoint-generering, og Streamlit multi-tab dashbord.

### Fase 5: Post-Launch Review, Day-2 Operations og Continuous Evals

Naar systemet er satt i produksjon/pilotering, aktiveres Fase 5:

1. Continuous Evals og Trajectory Tracing:
   - Kontinuerlig sporing av LLM-kall, latens og tokenkostnader via Langfuse/LangSmith.
   - Automatisk evaluering av sporringsbaner (trajectory accuracy) mot et versjonert testsett for finansielle sporjsmaal.
2. Drift Detection og Prompt Regression Testing:
   - Overvaaking av prompt drift naar nye tertialrapporter og endrede KOSTRA-forskrifter indekseres.
   - Regresjonstester ved oppgradering av underliggende LLM-modeller.
3. Day-2 Operations og KS Fiks Datasykronisering:
   - Nattlige batch-kjoringer for automatisert ETL-synkronisering mot Unit4/Visma ERP, Framsikt og GAT/turnussystemet.
   - Sjekk av dataferskhet og automatiske varsler ved manglende maanedskjoringer.
4. Kvartalsvis Audittrail og Governance Review:
   - Gjennomgang av audit_log-tabellen sammen med Kommunerevisjonen (NKRF) og Agder Kontrollutvalg.
   - Verifisering av at ingen preskriptive AI-forslag bryter med lovpaalagte minstetjenester i Helse- og omsorgstjenesteloven.

---

## Prosjektstruktur

```text
mvp-krs-kommune-ai/
├── Dockerfile                  # Produksjonsklar Docker-containerisering
├── docker-compose.yml          # Lokalt oppsett
├── .dockerignore               # Docker ekskluderingsregler
├── .env.example                # Mal for API-nokler
├── requirements.txt            # Nodvendige Python-pakker
├── README.md                   # Komplett GitHub-dokumentasjon
│
├── app/                        # Applikasjonskode
│   ├── __init__.py
│   ├── schemas.py              # Pydantic v2 datakontrakter, RBAC og AuditLog
│   ├── tools.py                # SQL, RAG, EOY, Drill-Down, Omdisponering, Time-Visuals og Audit
│   ├── visual_sandbox.py       # FT Visual Vocabulary (36 Suite), Time-Visuals (60 Suite) & Power BI DAX
│   ├── agent.py                # Multi-Agent Supervisor & Looped AI Orkestrering med Visual Reasoning
│   ├── build_rag_index.py      # Opprettelse av SQLite-database, Star Schema og RAG-indeks
│   └── frontend.py             # Streamlit web-grensesnitt (7 faner)
│
├── docs/                       # Arkitektur- og Visual Sandbox-dokumentasjon
│   ├── ANTIGRAVITY_INSTRUCTIONS.md
│   ├── ARCHITECTURE.md
│   └── VISUAL_SANDBOX.md
│
└── reports/                    # Eksempelrapporter
    ├── Maanedsrapport_Helse_og_Mestring.pdf
    └── Maanedsmote_Status_Helse_og_Mestring.pptx
```

---

## Oppstart og Kjoring

### Alternativ A: Kjore med Docker (Anbefalt)

1. Kopier .env.example til .env og fyll inn GEMINI_API_KEY.
2. Kjor kommandoen: docker compose up --build
3. Aapne nettleseren paa http://localhost:8501.

### Alternativ B: Kjore lokalt med Python og Streamlit

1. Installér avhengigheter: pip install -r requirements.txt
2. Sett GEMINI_API_KEY i miljobestemmelser.
3. Bygg databasen: python app/build_rag_index.py
4. Start Streamlit: python -m streamlit run app/frontend.py

📐 Arkitekturdiagram (Mermaid / Systemoversikt)
flowchart TD
subgraph UI ["1. Brukergrensesnitt & Presentasjonslag (Streamlit / frontend-v3.py)"]
User(["👤 Bruker / Leder"]) -->|Velger Rolle & Input| Sidebar["Rollevelger (RBAC)\n• Enhetsleder\n• Kommunalsjef\n• Økonomidirektør\n• Revisor"]
Sidebar --> Tabs["7 Interaktive Faner\n1. AI-Chat\n2. Månedsoversikt & Trafikklys\n3. FT Visual Vocabulary\n4. EOY & Lønnsbudsjett\n5. 6-Nivås Drill-Down\n6. Omdisponering & Eskalering\n7. Audit-Logg (Revisor)"]
Tabs --> Exporters["Eksportmoduler\n• PDF Månedsmelding\n• PowerPoint statusdeck\n• Fargekodet Excel"]
end

    subgraph Agent ["2. AI Agent & Orkestreringslag (AI_KOM Multi-Agent & Looped Engineering / agent.py)"]
        Supervisor["🧭 SupervisorAgent\n• Ruter spørringer til spesialisert subgraf:\n  - regnskap_erp_agent\n  - framsikt_eoy_agent\n  - saksbehandling_agent"]
        SystemPrompt["📜 System Prompt & Rules\n• GDPR & Dataminimering\n• Kommuneloven § 14-5 & Økonomireglement\n• Etisk sperre for lovpålagte minstetjenester\n• Human-in-the-Loop (HITL Intercepts)"]
        ExecutionLoop["🔄 Bounded Self-Correction Loop\n(AgentState Checkpointing & Maks Retries)"]
        Schemas["📐 Pydantic v2 Schemas (schemas.py)\n• Typevalidering av verktøyargumenter"]

        Supervisor --- SystemPrompt
        SystemPrompt --- ExecutionLoop
        ExecutionLoop --- Schemas
    end

    subgraph Tools ["3. Verktøy & Logikklag (tools.py)"]
        SQLTool["💾 RegnskapERPAgent / Secure SQL\n• Parameteriserte spørringer med Self-Correction\n• RBAC WHERE-filtrering\n• K-anonymisering / Maskering"]
        RAGTool["📚 Grounded RAG Search\n• Vektorsøk i Økonomiplan, Tertialrapporter & Forskrifter"]
        EOYTool["🔮 FramsiktEOYAgent & Lønnsmotor\n• Prediktiv EAC/ETC-årsprognose\n• Lønnsrammer, AGA, Pensjon"]
        ReallocTool["⚖️ SaksbehandlingAgent (§ 14-5)\n• Fullmaktssjekk & HITL Godkjenning\n• Saksframlegg-generator"]
        VisTool["📊 Visual Sandbox & Time-Visuals (60 Suite)\n• recommend_visual_for_chat_response\n• Fan Chart P10/P50/P90, 3M Snitt, Slope Graph\n• Power BI DAX-mål"]
    end

    subgraph Governance ["4. Sikkerhet, Audit & Datatilsyn"]
        AuditLog[("📝 Uforanderlig Audit Log\n(audit_log & log_audit_trail)")]
        RBACEngine["🔒 RBAC Enforcement Engine\n(sec_user_permissions / SCIM 2.0)"]
    end

    subgraph Data ["5. Datagrunnlag & Star Schema (Docker & Database)"]
        DB[("🗄️ SQLite / PostgreSQL Star Schema\n• fact_erp_transactions & stg_erp_transactions\n• fact_budget_allocations\n• dim_organisasjon & dim_kostra_kontoplan\n• dim_tid & dim_prosjekt_tiltak")]
        Docs["📄 Kunnskapsbase\n(PDF-er, KOSTRA-veiledere, Lovverk)"]
        KSFiks["📡 KS Fiks / ERP APIs\n(Unit4, Framsikt, GAT)"]
    end

    %% Sammenkoblinger
    Tabs -->|Spørring / Handling| ExecutionLoop
    ExecutionLoop -->|Kaller Verktøy| SQLTool
    ExecutionLoop -->|Kaller Verktøy| RAGTool
    ExecutionLoop -->|Kaller Verktøy| EOYTool
    ExecutionLoop -->|Kaller Verktøy| ReallocTool

    SQLTool -->|Sjekker Tilgang| RBACEngine
    RBACEngine -->|Sikret SQL| DB
    RAGTool -->|Søker i Context| Docs

    SQLTool & RAGTool & EOYTool & ReallocTool -->|Logger handling| AuditLog
    KSFiks -.->|Nattlig Batch Sync| DB

    ExecutionLoop -->|Returnerer Svar & Visualisering| Tabs

🧩 Komponentbeskrivelse av Lagene
Grensesnitt & Presentasjonslag (frontend-v3.py):
Multi-Tab Streamlit Dashboard: Gir tilpassede visninger for alt fra direkte chat med AI-agenten til betingede RAG-trafikklys (🟢, 🟡, 🔴), FT Visual Vocabulary-diagrammer og 6-nivås drill-down [cite: 8, 37, 47].
Rollebasert Sidestolpe (RBAC): Lar brukeren velge sin organisatoriske rolle (enhetsleder, kommunalsjef, økonomidirektør, revisor).
Agent & Orkestreringslag (agent-v3.py):
Gemini 2.0 Flash Function Calling: Tolker spørringen, velger riktig verktøy og strukturerer svaret.
Sikkerhetsregler i Prompten: Sikrer at agenten følger kommuneloven § 14-5, garanterer at AI kun er beslutningsstøtte (Human-in-the-Loop), og hindrer at kuttforslag berører lovpålagte minstetjenester [cite: 37, 53, 84].
Sikkerhetsløkke (Bounded Loop): Begrenser verktøykall til maksimalt 5 iterasjoner for å unngå uendelige sløyfer.
Verktøy & Logikklag (tools-v3.py):
Sikker SQL-Motor (query_erp_transactions_secure): Kjører parameteriserte spørringer mot transaksjonsdatabasen. Påser at enhetsledere automatisk avgrenses til sitt eget ansvarsnummer (WHERE ansvar = '...').
Grounded RAG-Søk (rag_search_documents): Henter relevante avsnitt fra kommunens tertialrapporter, økonomireglement og KOSTRA-veiledere [cite: 84, 87].
Eskalerings- og Omdisponeringsmotor (process_budget_reallocation): Sjekker automatisk om en omdisponering kan avklares av Kommunedirektøren eller må fremmes som saksframlegg for Formannskapet/Bystyret [cite: 106, 108].
Sikkerhet, Audittrail & Governance:
Revisjonslogg (audit_log): Hver eneste brukerhandling, SQL-spørring, AI-analyse og omdisponering lagres uforanderlig i databasen for full etterprøvbarhet fra Kommunerevisjonen (NKRF), Agder Kontrollutvalg og Statsforvalteren [cite: 41, 48].
Infrastruktur & Containerisering (Dockerfile & docker-compose.yml):
Isolert Kjøremiljø: Hele applikasjonen er pakket i Docker med automatisk opprettelse av SQLite-databasen, klar for publisering på kommunens interne skymiljø eller demonstrasjon fra GitHub.
