# app/schemas.py - Datakontrakter inkludert RBAC, Sikkerhet, Audit Log og Økonomiverktøy
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class UserContext(BaseModel):
    user_id: str = Field(..., description="Unik bruker-ID for saksbehandler/leder.")
    role: str = Field(
        ...,
        description="Rolle: 'enhetsleder', 'kommunalsjef', 'direktor', eller 'revisor'.",
    )
    assigned_ansvar: Optional[str] = Field(
        default=None,
        description="Tildelt ansvarsområde for enhetsleder (f.eks. '2530').",
    )
    tillatte_ansvar: List[str] = Field(
        default=[],
        description="Liste over ansvarsnumre brukeren har tilgang til (tom = alt for direktør).",
    )


class AuditLogEntry(BaseModel):
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Tidsstempel for handlingen.",
    )
    user_id: str = Field(..., description="Bruker-ID.")
    role: str = Field(..., description="Brukerrolle.")
    action_type: str = Field(
        ...,
        description="Handlingstype (f.eks. 'SQL_QUERY', 'REALLOCATION_PROPOSAL', 'LOGIN').",
    )
    prompt_or_query: str = Field(..., description="Spørring eller prompt som ble kjørt.")
    result_summary: str = Field(..., description="Sammendrag av utført handling.")
    ip_address: Optional[str] = Field(default="127.0.0.1", description="IP-adresse.")


class ERPSQLQueryInput(BaseModel):
    query: str = Field(
        ...,
        description=(
            "SELECT-spørring mot SQLite (stg_erp_transactions, Fact_Regnskap, Fact_Budsjett, "
            "Fact_Prognose_Logg, Dim_Ansvar, Dim_Funksjon, Dim_Art, stg_kostra_stats_krs_km, stg_kostra_kontoplan)."
        ),
    )
    user_context: Optional[UserContext] = Field(
        default=None, description="Brukerkontekst for RBAC-filtrering."
    )


class KnowledgeSearchInput(BaseModel):
    query: str = Field(
        ...,
        description="Søk i ustrukturerte kilder (tertialrapporter, økonomiplaner, vedtekter, reglement).",
    )
    max_results: int = Field(default=3, ge=1, le=5)


class SerperSearchInput(BaseModel):
    query: str = Field(
        ...,
        description="Nettsøk via Serper API for eksterne veiledere og statlige sirkulærer.",
    )


class MonthlyUnitReportInput(BaseModel):
    ansvar_id: str = Field(
        ...,
        description="Ansvarskode eller enhetsnavn, f.eks. '2530 - Randesund Omsorgssenter' eller '2530'.",
    )
    periode_mnd: int = Field(
        default=8, ge=1, le=12, description="Rapporteringsmåned (1-12)."
    )


class EOYPrescriptiveForecastInput(BaseModel):
    ansvar_id: str = Field(
        ..., description="Ansvarskode eller enhetsnavn for enheten som analyseres."
    )
    hittil_forbruk: float = Field(
        ..., description="Akkumulert regnskapsført forbruk hittil i år (kr)."
    )
    arsbudsjett: float = Field(
        ..., description="Vedtatt årsbudsjett for enheten (kr)."
    )
    sykefravaer_prosent: Optional[float] = Field(
        default=None, description="Sykefraværsprosent for enheten (valgfritt)."
    )


class SalaryBudgetingInput(BaseModel):
    ansvar_id: str = Field(..., description="Ansvarskode eller enhetsnavn.")
    antall_fte: float = Field(
        ..., description="Antall årsverk / stillingshjemler (FTE)."
    )
    deflator_prosent: float = Field(
        default=4.1, description="Forventet lønns- og prisvekst / deflator i prosent."
    )
    ubekvemstillegg_prosent: float = Field(
        default=18.0, description="Ulempe- og turnustillegg i prosent av grunnlønn."
    )


class BudgetDrillDownInput(BaseModel):
    sektor: Optional[str] = Field(
        default="Helse og Mestring",
        description="Sektor (Nivå 1), f.eks. 'Helse og Mestring'.",
    )
    kommunalsjef_omrade: Optional[str] = Field(
        default=None,
        description="Kommunalsjefområde (Nivå 2), f.eks. 'Heldøgns omsorg', 'Hjemmebaserte tjenester', 'Mestring og helse'.",
    )
    ansvar_id: Optional[str] = Field(
        default=None,
        description="Ansvarskode (Nivå 3), f.eks. '2530', '2580', '2540', '2330'.",
    )
    funksjon_id: Optional[str] = Field(
        default=None,
        description="KOSTRA-funksjon (Nivå 4), f.eks. '253', '254', '258'.",
    )
    art_id: Optional[str] = Field(
        default=None,
        description="KOSTRA-artskonto (Nivå 5), f.eks. '101000', '109000', '110000', '169000'.",
    )
    periode_mnd: int = Field(
        default=8, ge=1, le=12, description="Rapporteringsmåned (1-12)."
    )


class BudgetReallocationInput(BaseModel):
    fra_ansvar: str = Field(..., description="Ansvarsnummer med mindreforbruk.")
    til_ansvar: str = Field(..., description="Ansvarsnummer med merforbruk.")
    belop_kr: float = Field(..., description="Beløp som foreslås omdisponert (kr).")
    begrunnelse: str = Field(..., description="Faglig og økonomisk begrunnelse.")
    user_context: Optional[UserContext] = Field(
        default=None, description="Brukerkontekst for tilgangskontroll."
    )
