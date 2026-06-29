"""
Schemas de saída estruturada do LLM (vinculados via `with_structured_output`).
Espelham os campos de `domain/entities/pharma.py` que o modelo deve preencher —
excluem campos calculados pelo grafo (`agent_steps`) ou pela camada de aplicação.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from src.domain.entities.pharma import DrugInteraction, PrescriptionAlert


class DrugAnalysisLLM(BaseModel):
    generic_name: Optional[str] = None
    drug_class: Optional[str] = None
    mechanism_of_action: str
    indications: List[str]
    contraindications: List[str]
    adverse_effects: List[str]
    dosage_info: Optional[str] = None
    known_interactions: List[str]
    pregnancy_category: Optional[str] = None
    renal_adjustment: Optional[str] = None
    hepatic_adjustment: Optional[str] = None
    clinical_alerts: List[str]
    summary: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class InteractionCheckLLM(BaseModel):
    total_interactions: int
    interactions: List[DrugInteraction]
    critical_alerts: List[str]
    recommendations: List[str]
    overall_risk: Literal["baixo", "moderado", "alto", "crítico"]


class PrescriptionReviewLLM(BaseModel):
    alerts: List[PrescriptionAlert]
    interactions_found: List[DrugInteraction]
    therapeutic_duplications: List[str]
    dosage_issues: List[str]
    overall_safety_score: float = Field(..., ge=0.0, le=10.0)
    pharmacist_notes: str
    recommended_monitoring: List[str]
