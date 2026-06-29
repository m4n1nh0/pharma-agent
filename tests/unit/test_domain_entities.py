"""
Unit Tests — Domain Entities
Testa lógica pura sem dependência de infra.
"""

import pytest
from src.domain.entities.job import Job, JobStatus, JobType
from src.domain.entities.pharma import DrugAnalysisResult, InteractionSeverity, DrugInteraction


def test_job_creation():
    job = Job(id="job_abc", type=JobType.DRUG_ANALYSIS, user_id="usr_1", payload={"drug_name": "Warfarina"})
    assert job.status == JobStatus.PENDING
    assert job.progress == 0.0
    assert job.result is None


def test_job_status_dict():
    job = Job(id="job_xyz", type=JobType.PRESCRIPTION, user_id="usr_2", payload={})
    d = job.to_status_dict()
    assert d["job_id"] == "job_xyz"
    assert d["has_result"] is False
    assert d["status"] == "pending"


def test_drug_analysis_result_defaults():
    result = DrugAnalysisResult(
        drug_name="Amoxicilina",
        mechanism_of_action="Inibe PBPs",
        indications=["ITU"],
        contraindications=["Alergia"],
        adverse_effects=["Diarreia"],
        known_interactions=[],
        clinical_alerts=[],
        summary="OK",
        confidence_score=0.9,
    )
    assert result.agent_steps == []
    assert result.confidence_score == 0.9


def test_interaction_severity_enum():
    assert InteractionSeverity.MAJOR == "maior"
    assert InteractionSeverity.CONTRAINDICATED == "contraindicada"


def test_drug_interaction_fields():
    ix = DrugInteraction(
        drug_a="Warfarina", drug_b="Aspirina",
        severity=InteractionSeverity.MAJOR,
        mechanism="Sinergismo", clinical_effect="Sangramento", management="Evitar",
        evidence_level="A",
    )
    assert ix.severity == "maior"
