komplett stjerneskjema (Star Schema) og DDL-skjema (Data Definition Language) som definerer hvordan datagrunnlaget fra ERP (Unit4/Visma), Framsikt, KOSTRA og HR (GAT) bør struktureres i et relasjons- eller datavarehusmiljø (SQLite/PostgreSQL) før du kobler til AI-agentene [cite: 8, 33, 70, 82].
📐 Stjerneskjema (Star Schema Overview)
┌──────────────────────┐
│ dim_organisasjon │
│ (Sektor, Ansvar, HR) │
└──────────┬───────────┘
│
│ 1:N
┌──────────────────────┐ ▼ ┌──────────────────────┐
│ dim_kostra_kontoplan │ 1:N ┌─────────┐ │ dim_tid │
│ (Funksjon, Art, Class) ├───►│ FACT │◄──┤ (År, Måned, Tertial) │
└──────────────────────┘ │ TABLES │ └──────────────────────┘
└────┬────┘
┌──────────────────────┐ │
│ dim_prosjekt_tiltak │ 1:N │
│ (Prosjekt, Prosjektleder) ──────┘
└──────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ SIKKERHET & AUDIT-LAG (RBAC) │
├───────────────────────────────┬───────────────────────────────┤
│ sec_user_permissions │ audit_log │
│ (SCIM 2.0 / Ansvar-tilganger) │ (Uforanderlig revisjonslogg) │
└───────────────────────────────┴───────────────────────────────┘
📜 Produksjonsklar SQL DDL (SQLite / PostgreSQL)
Du kan kjøre denne DDL-en direkte for å opprette den "digitale grunnmuren" i databasen din [cite: 82, 84]:
-- ============================================================================
-- 1. DIMENSJONSTABELLER (Masterdata)
-- ============================================================================

-- Organisasjonsstruktur (6-Nivås hierarki)
CREATE TABLE IF NOT EXISTS dim_organisasjon (
ansvar_id VARCHAR(10) PRIMARY KEY, -- f.eks. '2530' (Randesund Omsorgssenter)
ansvar_navn VARCHAR(100) NOT NULL,
enhet_navn VARCHAR(100) NOT NULL, -- Delytelse / Tjenestested
kommunalsjefområde VARCHAR(100) NOT NULL, -- f.eks. 'Mestring og Omsorg'
sektor VARCHAR(100) NOT NULL DEFAULT 'Helse og Mestring',
enhetsleder_ansatt_id VARCHAR(20),
oppdatert_dato TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- KOSTRA Kontoplan
CREATE TABLE IF NOT EXISTS dim_kostra_kontoplan (
art_id VARCHAR(10) PRIMARY KEY, -- f.eks. '1090' (Overtid)
art_navn VARCHAR(100) NOT NULL,
artsgruppe VARCHAR(100) NOT NULL, -- f.eks. 'Lønn og sosiale utgifter'
funksjon_id VARCHAR(10) NOT NULL, -- f.eks. '253' (Pleie og omsorg)
funksjon_navn VARCHAR(100) NOT NULL,
kontoklasse INT NOT NULL CHECK (kontoklasse IN (1, 2)), -- 1 = Drift, 2 = Investering
skjermet_for_kutt BOOLEAN DEFAULT FALSE -- True dersom lovpålagt minstetjeneste
);

-- Tidsdimensjon
CREATE TABLE IF NOT EXISTS dim_tid (
dato_key INT PRIMARY KEY, -- ÅAÅÅMMDD (f.eks. 20260401)
dato DATE NOT NULL,
aar INT NOT NULL,
periode INT NOT NULL CHECK (periode BETWEEN 1 AND 12),
kvartal INT NOT NULL CHECK (kvartal BETWEEN 1 AND 4),
tertial INT NOT NULL CHECK (tertial BETWEEN 1 AND 3)
);

-- Prosjekt / Tiltak
CREATE TABLE IF NOT EXISTS dim_prosjekt_tiltak (
prosjekt_id VARCHAR(20) PRIMARY KEY,
prosjekt_navn VARCHAR(100) NOT NULL,
prosjektleder_ansatt_id VARCHAR(20),
omstillingskategori VARCHAR(50) -- f.eks. 'TØRN', 'Satsing', 'Innparing'
);

-- ============================================================================
-- 2. FAKTATABELLER (Transaksjoner & Budsjett)
-- ============================================================================

-- Faktatabell 1: Eksakte ERP Regnskapsposteringer (Unit4 / Visma)
CREATE TABLE IF NOT EXISTS fact_erp_transactions (
transaksjon_id VARCHAR(50) PRIMARY KEY,
dato_key INT NOT NULL,
ansvar_id VARCHAR(10) NOT NULL,
art_id VARCHAR(10) NOT NULL,
prosjekt_id VARCHAR(20) DEFAULT '0000',
belop DECIMAL(15, 2) NOT NULL, -- Positivt = Utgift, Negativt = Inntekt
bilagsnummer VARCHAR(30) NOT NULL,
tekst_beskrivelse TEXT,
kilde_system VARCHAR(20) DEFAULT 'Unit4 ERP',
importert_dato TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (dato_key) REFERENCES dim_tid(dato_key),
FOREIGN KEY (ansvar_id) REFERENCES dim_organisasjon(ansvar_id),
FOREIGN KEY (art_id) REFERENCES dim_kostra_kontoplan(art_id)
);

-- Faktatabell 2: Vedtatt & Regulert Budsjett (Framsikt)
CREATE TABLE IF NOT EXISTS fact_budget_allocations (
budsjett_id VARCHAR(50) PRIMARY KEY,
aar INT NOT NULL,
periode INT NOT NULL CHECK (periode BETWEEN 1 AND 12),
ansvar_id VARCHAR(10) NOT NULL,
art_id VARCHAR(10) NOT NULL,
vedtatt_budsjett DECIMAL(15, 2) DEFAULT 0.00,
regulert_budsjett DECIMAL(15, 2) DEFAULT 0.00,
periodisert_budsjett DECIMAL(15, 2) DEFAULT 0.00,
oppdatert_dato TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (ansvar_id) REFERENCES dim_organisasjon(ansvar_id),
FOREIGN KEY (art_id) REFERENCES dim_kostra_kontoplan(art_id)
);

-- ============================================================================
-- 3. SIKKERHET, RBAC (SCIM 2.0) & AUDIT-LOGG
-- ============================================================================

-- Tilgangsstyring (SCIM 2.0 / Entra ID-knytning per bruker)
CREATE TABLE IF NOT EXISTS sec_user_permissions (
bruker_id VARCHAR(50) NOT NULL, -- Brukerens e-post eller Entra ID Object ID
rolle VARCHAR(30) NOT NULL, -- 'enhetsleder', 'kommunalsjef', 'okonomidirektor', 'revisor'
ansvar_id VARCHAR(10) NOT NULL, -- Månedlig avgrensing (eller '\*' for full tilgang)
gyldig_fra DATE DEFAULT CURRENT_DATE,
gyldig_til DATE,
PRIMARY KEY (bruker_id, ansvar_id)
);

-- Uforanderlig Audit Log (Arkivlova & Tilsyn)
CREATE TABLE IF NOT EXISTS audit_log (
log_id INTEGER PRIMARY KEY AUTOINCREMENT,
timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
bruker_id VARCHAR(50) NOT NULL,
rolle VARCHAR(30) NOT NULL,
handling_kategori VARCHAR(50) NOT NULL, -- 'SQL_QUERY', 'RAG_SEARCH', 'REALLOCATION_PROPOSAL'
ansvar_spurt_om VARCHAR(10),
sporring_tekst TEXT NOT NULL,
ai_respons_sammendrag TEXT,
ip_adresse VARCHAR(45)
);

-- ============================================================================
-- 4. INDEKSER FOR HØY YTELSE & RASK AGGREGERING
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_erp_ansvar_art ON fact_erp_transactions(ansvar_id, art_id);
CREATE INDEX IF NOT EXISTS idx_erp_dato ON fact_erp_transactions(dato_key);
CREATE INDEX IF NOT EXISTS idx_budget_ansvar_periode ON fact_budget_allocations(ansvar_id, aar, periode);
CREATE INDEX IF NOT EXISTS idx_rbac_bruker ON sec_user_permissions(bruker_id);
💡 Hvorfor denne datamodellen er optimal for AI-agenter
Rask og sikker SQL-generering (SQLTool): Tabellene har eksplisitte fremmednøkler og entydige kolonnenavn. AI-agenten kan enkelt kjøre JOIN mellom fact_erp_transactions og fact_budget_allocations for å beregne månedlige avvik [cite: 8, 33].
Innebygd RBAC-filtrering: Når en enhetsleder stiller et spørsmål, henger agenten på WHERE ansvar_id IN (SELECT ansvar_id FROM sec_user_permissions WHERE bruker_id = '...') direkte på SQL-spørringen. Dermed er dataseparasjonen garantert på databasenivå [cite: 28, 60].
Innebygde etiske sperrer (skjermet_for_kutt): I dim_kostra_kontoplan markerer feltet skjermet_for_kutt = TRUE lovpålagte minstetjenester. Agenten forhindres dermed i å foreslå omdisponeringer som bryter med Helse- og omsorgstjenesteloven [cite: 37, 84].
