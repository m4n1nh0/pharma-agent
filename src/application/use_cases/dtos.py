"""Schemas de entrada/saída da API — separados das entidades de domínio porque o contrato HTTP pode divergir do modelo de negócio."""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from src.domain.entities.pharma import PatientInfo, PrescriptionItem


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserCreateDTO(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field(default="farmaceutico", pattern="^(farmaceutico|medico|admin)$")
    crm_crf: Optional[str] = None


class UserLoginDTO(BaseModel):
    email: EmailStr
    password: str


class UserResponseDTO(BaseModel):
    id: str
    name: str
    email: str
    role: str
    crm_crf: Optional[str]
    created_at: str


class TokenResponseDTO(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserResponseDTO


class RefreshRequestDTO(BaseModel):
    refresh_token: str


# ── Análise de Medicamento ────────────────────────────────────────────────────

class DrugAnalysisRequestDTO(BaseModel):
    drug_name: str = Field(..., description="Nome do medicamento")
    context: Optional[str] = None
    patient_info: Optional[PatientInfo] = None

    class Config:
        json_schema_extra = {
            "example": {
                "drug_name": "Amoxicilina",
                "context": "Infecção urinária",
                "patient_info": {"age": 45, "weight_kg": 70},
            }
        }


# ── Interações ────────────────────────────────────────────────────────────────

class InteractionCheckRequestDTO(BaseModel):
    drugs: List[str] = Field(..., min_length=2)
    patient_info: Optional[PatientInfo] = None

    class Config:
        json_schema_extra = {
            "example": {
                "drugs": ["Warfarina", "Aspirina", "Omeprazol"],
                "patient_info": {"age": 65},
            }
        }


# ── Prescrição ────────────────────────────────────────────────────────────────

class PrescriptionReviewRequestDTO(BaseModel):
    prescription: List[PrescriptionItem]
    patient_info: Optional[PatientInfo] = None
    clinical_context: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "prescription": [
                    {"drug_name": "Metformina", "dose": "850mg", "frequency": "2x/dia"},
                    {"drug_name": "Enalapril",  "dose": "10mg",  "frequency": "1x/dia"},
                ],
                "patient_info": {"age": 58, "weight_kg": 85},
            }
        }
