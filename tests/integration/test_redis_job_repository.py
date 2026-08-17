"""
Integration Tests — RedisJobRepository (serialização)
Cobre o round-trip Job ↔ JSON sem depender de um Redis rodando; o fluxo com
Redis real é exercitado pelo docker-compose (API + worker separados).
"""

import pytest
from src.domain.entities.job import Job, JobStatus, JobType
from src.infrastructure.persistence.redis_job_repository import RedisJobRepository


def _job() -> Job:
    return Job(
        id="job_abc123",
        type=JobType.INTERACTIONS,
        user_id="usr_1",
        payload={"drugs": ["warfarina", "aspirina"]},
    )


def test_round_trip_preserva_campos_e_enums():
    original = _job()
    restored = RedisJobRepository._loads(RedisJobRepository._dumps(original))

    assert restored == original
    # Enums precisam voltar como enum, não string: o resto do código compara
    # com JobStatus.X / JobType.X por identidade.
    assert restored.status is JobStatus.PENDING
    assert restored.type is JobType.INTERACTIONS
    assert restored.payload == {"drugs": ["warfarina", "aspirina"]}


def test_round_trip_com_resultado_e_metricas():
    original = _job()
    original.status = JobStatus.COMPLETED
    original.progress = 1.0
    original.result = {"overall_risk": "alto", "score": 4.5}
    original.duration_ms = 1234.56

    restored = RedisJobRepository._loads(RedisJobRepository._dumps(original))

    assert restored.status is JobStatus.COMPLETED
    assert restored.result == {"overall_risk": "alto", "score": 4.5}
    assert restored.duration_ms == 1234.56
    assert restored.to_status_dict()["has_result"] is True


def test_chaves_isolam_job_usuario_e_canal():
    assert RedisJobRepository._job_key("job_1") == "pharma:job:job_1"
    assert RedisJobRepository._user_key("usr_1") == "pharma:user_jobs:usr_1"
    assert RedisJobRepository._channel("job_1") == "pharma:job_events:job_1"


@pytest.mark.parametrize("status", list(JobStatus))
def test_todos_os_status_sobrevivem_ao_round_trip(status: JobStatus):
    original = _job()
    original.status = status
    assert RedisJobRepository._loads(RedisJobRepository._dumps(original)).status is status
