"""Implementação de IJobRepository em memória — em produção, substitua por RedisJobRepository ou PostgresJobRepository."""

import uuid
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional, List, AsyncGenerator

from src.domain.entities.job import Job, JobStatus, JobType
from src.domain.repositories.interfaces import IJobRepository


class InMemoryJobRepository(IJobRepository):
    """Job store em memória com notificação SSE via asyncio.Queue."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    # ── CRUD ──────────────────────────────────────────────────────────────────
    async def create(self, job_type: JobType, user_id: str, payload: dict) -> Job:
        job = Job(
            id=f"job_{uuid.uuid4().hex[:12]}",
            type=job_type,
            user_id=user_id,
            payload=payload,
        )
        self._jobs[job.id] = job
        return job

    async def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    async def list_by_user(self, user_id: str) -> List[Job]:
        return [j for j in self._jobs.values() if j.user_id == user_id]

    async def close(self) -> None:
        """Nada a liberar — o store é um dict local."""

    # ── Transitions ───────────────────────────────────────────────────────────
    async def mark_running(self, job_id: str, msg: str = "Processando...") -> None:
        job = self._require(job_id)
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc).isoformat()
        job.progress = 0.05
        job.progress_msg = msg
        await self._notify(job)

    async def update_progress(self, job_id: str, progress: float, msg: str = "") -> None:
        job = self._require(job_id)
        job.progress = min(max(progress, 0.0), 0.99)
        if msg:
            job.progress_msg = msg
        await self._notify(job)

    async def mark_completed(self, job_id: str, result: dict) -> None:
        job = self._require(job_id)
        now = datetime.now(timezone.utc)
        job.status = JobStatus.COMPLETED
        job.progress = 1.0
        job.progress_msg = "Concluído"
        job.result = result
        job.completed_at = now.isoformat()
        if job.started_at:
            job.duration_ms = round(
                (now - datetime.fromisoformat(job.started_at)).total_seconds() * 1000, 2
            )
        await self._notify(job)

    async def mark_failed(self, job_id: str, error: str) -> None:
        job = self._require(job_id)
        now = datetime.now(timezone.utc)
        job.status = JobStatus.FAILED
        job.error = error
        job.progress_msg = "Falhou"
        job.completed_at = now.isoformat()
        if job.started_at:
            job.duration_ms = round(
                (now - datetime.fromisoformat(job.started_at)).total_seconds() * 1000, 2
            )
        await self._notify(job)

    async def mark_cancelled(self, job_id: str) -> None:
        job = self._require(job_id)
        job.status = JobStatus.CANCELLED
        job.progress_msg = "Cancelado"
        job.completed_at = datetime.now(timezone.utc).isoformat()
        await self._notify(job)

    # ── SSE ───────────────────────────────────────────────────────────────────
    def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._subscribers.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(job_id, [])
        if q in subs:
            subs.remove(q)

    async def sse_generator(self, job_id: str, timeout: float = 300.0) -> AsyncGenerator[str, None]:
        job = await self.get(job_id)
        if not job:
            yield 'data: {"error": "job não encontrado"}\n\n'
            return

        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            yield f"data: {json.dumps(job.to_status_dict(), default=str)}\n\n"
            yield "data: [DONE]\n\n"
            return

        q = self.subscribe(job_id)
        try:
            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    yield 'data: {"error": "timeout"}\n\n'
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=min(remaining, 30))
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                    if event.get("status") in ("completed", "failed", "cancelled"):
                        yield "data: [DONE]\n\n"
                        break
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            self.unsubscribe(job_id, q)

    # ── Internals ─────────────────────────────────────────────────────────────
    def _require(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} não encontrado")
        return job

    async def _notify(self, job: Job) -> None:
        event = job.to_status_dict()
        for q in list(self._subscribers.get(job.id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass


job_repository = InMemoryJobRepository()
