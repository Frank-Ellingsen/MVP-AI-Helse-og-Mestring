# Kristiansand Kommune - Helse og Mestring AI Okonomiradgiver (MVP)

En agentisk AI-beslutningsstottemodell for virksomhetsstyring og okonomioppfolging i Helse og Mestring i Kristiansand kommune. Systemet kombinerer eksakte SQL-sporringer mot ERP-transaksjoner, RAG-oppslag i kommunale styringsdokumenter og tertialrapporter, nettsok via Serper.dev API, maanedlig avviksanalyse med RAG-trafikklys, Financial Times Visual Vocabulary, prediktiv aarsprognose (EOY), preskriptive balansetiltak (§ 14-5), lonnsbudsjettering, 6-nivas interaktiv drill-down, automatisk sjekk av omdisponeringsfullmakter (Kommunedirektor vs. Bystyret/Formannskapet), rollestyring (RBAC) og uforanderlig audit-logg jf. arkivlova.

---

## Arkitektur og Faseinndeling (Uke 1-16 + Day-2 Operations)

Systemet er bygget i trad med AI Engineering Stage-Gate Framework:

* Fase 1 (Uke 1-4) - Pydantic v2 og Verktoy-kontrakter: Strict typevalidering (schemas.py), feilhandling og parameteriserte SQL-oppslag.
* Fase 2 (Uke 5-8) - Grounded RAG og Evidens: Hybrid RAG-arkitektur (tools.py) som kombinerer ustrukturerte dokumenter med strukturerte transaksjonsdata.
* Fase 3 (Uke 9-12) - Agentorkestrering, RBAC og HITL: Tilstandsbasert agentlokke (agent.py), rollebasert tilgangskontroll (enhetsleder, kommunalsjef, okonomidirektor), automatisk eskaleringssjekk for politisk vedtak, og uforanderlig revisjonslogg (audit_log).
* Fase 4 (Uke 13-16) - Produksjon, Containerisering og Eksport: Docker-oppsett (Dockerfile, docker-compose.yml), automatisert PDF- og PowerPoint-generering, og Streamlit multi-tab dashbord.

### Fase 5: Post-Launch Review, Day-2 Operations og Continuous Evals
Naar systemet er satt i produksjon/pilotering, aktiveres Fase 5:
1. Continuous Evals og Trajectory Tracing:
   * Kontinuerlig sporing av LLM-kall, latens og tokenkostnader via Langfuse/LangSmith.
   * Automatisk evaluering av sporringsbaner (trajectory accuracy) mot et versjonert testsett for finansielle sporjsmaal.
2. Drift Detection og Prompt Regression Testing:
   * Overvaaking av prompt drift naar nye tertialrapporter og endrede KOSTRA-forskrifter indekseres.
   * Regresjonstester ved oppgradering av underliggende LLM-modeller.
3. Day-2 Operations og KS Fiks Datasykronisering:
   * Nattlige batch-kjoringer for automatisert ETL-synkronisering mot Unit4/Visma ERP, Framsikt og GAT/turnussystemet.
   * Sjekk av dataferskhet og automatiske varsler ved manglende maanedskjoringer.
4. Kvartalsvis Audittrail og Governance Review:
   * Gjennomgang av audit_log-tabellen sammen med Kommunerevisjonen (NKRF) og Agder Kontrollutvalg.
   * Verifisering av at ingen preskriptive AI-forslag bryter med lovpaalagte minstetjenester i Helse- og omsorgstjenesteloven.

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
│   ├── tools.py                # SQL, RAG, EOY, Drill-Down, Omdisponering og Audit
│   ├── agent.py                # Agentorkestrering
│   ├── build_rag_index.py      # Opprettelse av SQLite-database og RAG-indeks
│   └── frontend.py             # Streamlit web-grensesnitt
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
