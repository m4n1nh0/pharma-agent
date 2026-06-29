"""
Integration Tests — InMemoryJobRepository
Testa o store com asyncio real.
"""

import asyncio
import pytest
from src.domain.entities.job import JobType, JobStatus
from src.infrastructure.persistence.job_repository import InMemoryJobRepository


@pytest.mark.asyncio
async def test_create_and_get():
    repo = InMemoryJobRepository()
    job = repo.create(JobType.DRUG_ANALYSIS, "usr_1", {"drug_name": "Test"})
    assert repo.get(job.id) is job
    assert job.status == JobStatus.PENDING


@pytest.mark.asyncio
async def test_mark_running_updates_status():
    repo = InMemoryJobRepository()
    job = repo.create(JobType.INTERACTIONS, "usr_1", {})
    await repo.mark_running(job.id, "Processando...")
    assert job.status == JobStatus.RUNNING
    assert job.started_at is not None
    assert job.progress > 0


@pytest.mark.asyncio
async def test_mark_completed_sets_result():
    repo = InMemoryJobRepository()
    job = repo.create(JobType.PRESCRIPTION, "usr_1", {})
    await repo.mark_running(job.id)
    await repo.mark_completed(job.id, {"score": 9.0})
    assert job.status == JobStatus.COMPLETED
    assert job.result == {"score": 9.0}
    assert job.duration_ms is not None
    assert job.progress == 1.0


@pytest.mark.asyncio
async def test_mark_failed():
    repo = InMemoryJobRepository()
    job = repo.create(JobType.DRUG_ANALYSIS, "usr_2", {})
    await repo.mark_running(job.id)
    await repo.mark_failed(job.id, "Timeout do agente")
    assert job.status == JobStatus.FAILED
    assert "Timeout" in job.error


@pytest.mark.asyncio
async def test_list_by_user():
    repo = InMemoryJobRepository()
    repo.create(JobType.DRUG_ANALYSIS, "usr_A", {})
    repo.create(JobType.DRUG_ANALYSIS, "usr_A", {})
    repo.create(JobType.DRUG_ANALYSIS, "usr_B", {})
    assert len(repo.list_by_user("usr_A")) == 2
    assert len(repo.list_by_user("usr_B")) == 1
    assert len(repo.list_by_user("usr_Z")) == 0


@pytest.mark.asyncio
async def test_sse_completed_job_delivers_immediately():
    repo = InMemoryJobRepository()
    job = repo.create(JobType.DRUG_ANALYSIS, "usr_1", {})
    await repo.mark_running(job.id)
    await repo.mark_completed(job.id, {"ok": True})

    frames = []
    async for frame in repo.sse_generator(job.id, timeout=2.0):
        frames.append(frame)

    assert any("completed" in f for f in frames)
    assert any("[DONE]" in f for f in frames)
