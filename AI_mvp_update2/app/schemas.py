from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class UserRole(BaseModel):
    user_id: str
    role: str = Field(..., description="enhetsleder, kommunalsjef, okonomidirektor, revisor")
    ansvar_access: List[str]

class AuditEntry(BaseModel):
    user_id: str
    role: str
    action_category: str
    ansvar_spurt_om: Optional[str] = None
    query_text: str
    ai_summary: Optional[str] = None

class ReallocationRequest(BaseModel):
    fra_ansvar: str
    til_ansvar: str
    belop: float
    begrunnelse: str
    requires_political_approval: bool = False
