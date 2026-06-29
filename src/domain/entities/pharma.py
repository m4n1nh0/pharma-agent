"""Modelos de domínio do negócio farmacêutico — sem dependência de FastAPI, SQLAlchemy ou outra infra."""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum


class PatientInfo(BaseModel):
    age: Optional[int] = Field(None, description="Idade em anos")
    weight_kg: Optional[float] = Field(None, description="Peso em kg")
    renal_function: Optional[str] = Field(None, description="normal | leve | moderada | grave")
    hepatic_function: Optional[str] = Field(None, description="normal | comprometida")
    pregnancy: Optional[bool] = None
    allergies: Optional[List[str]] = Field(default_factory=list)
    comorbidities: Optional[List[str]] = Field(default_factory=list)


# ── Análise de Medicamento ────────────────────────────────────────────────────

class DrugAnalysisResult(BaseModel):
    drug_name: str
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
    agent_steps: List[str] = Field(default_factory=list)


# ── Interações ────────────────────────────────────────────────────────────────

class InteractionSeverity(str, Enum):
    CONTRAINDICATED = "contraindicada"
    MAJOR = "maior"
    MODERATE = "moderada"
    MINOR = "menor"
    UNKNOWN = "desconhecida"


class DrugInteraction(BaseModel):
    drug_a: str
    drug_b: str
    severity: InteractionSeverity
    mechanism: str
    clinical_effect: str
    management: str
    evidence_level: Optional[str]


class InteractionCheckResult(BaseModel):
    drugs_analyzed: List[str]
    total_interactions: int
    interactions: List[DrugInteraction]
    critical_alerts: List[str]
    recommendations: List[str]
    overall_risk: Literal["baixo", "moderado", "alto", "crítico"]
    agent_steps: List[str] = Field(default_factory=list)


# ── Prescrição ────────────────────────────────────────────────────────────────

class PrescriptionItem(BaseModel):
    drug_name: str
    dose: str
    frequency: str
    route: Optional[str] = "oral"
    duration: Optional[str] = None
    indication: Optional[str] = None


class PrescriptionAlert(BaseModel):
    type: Literal["interacao", "dose", "duplicidade", "contraindicacao", "monitoramento"]
    severity: Literal["informativo", "atencao", "alerta", "critico"]
    drug: str
    description: str
    recommendation: str


class PrescriptionReviewResult(BaseModel):
    total_items: int
    items_reviewed: List[str]
    alerts: List[PrescriptionAlert]
    interactions_found: List[DrugInteraction]
    therapeutic_duplications: List[str]
    dosage_issues: List[str]
    overall_safety_score: float = Field(..., ge=0.0, le=10.0)
    pharmacist_notes: str
    recommended_monitoring: List[str]
    agent_steps: List[str] = Field(default_factory=list)
