"""Implementação de IJobRepository sobre Redis — compartilhada entre processos.

Diferença essencial em relação ao InMemoryJobRepository: o estado do job vive
fora do processo, então API e worker podem rodar em serviços separados. As
notificações de progresso viajam por pub/sub, e não por asyncio.Queue local —
é isso que permite ao SSE da API acompanhar um job processado por outro
container.

Layout das chaves:
    pharma:job:{job_id}          → JSON do Job (TTL)
    pharma:user_jobs:{user_id}   → SET de job_ids do usuário (TTL)
    pharma:job_events:{job_id}   → canal pub/sub dos eventos de progresso
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional

import redis.asyncio as aioredis

from src.domain.entities.job import Job, JobStatus, JobType
from src.domain.repositories.interfaces import IJobRepository

logger = logging.getLogger("pharma.infrastructure.redis")

KEY_PREFIX = "pharma"
JOB_TTL_SECONDS = 24 * 60 * 60

TERMINAL_STATUSES = (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
TERMINAL_VALUES = tuple(s.value for s in TERMINAL_STATUSES)


class RedisJobRepository(IJobRepository):
    """Job store em Redis com notificação SSE via pub/sub."""

    def __init__(self, url: str) -> None:
        # decode_responses: trabalhamos com str, não bytes, em todo o repositório.
        self._redis = aioredis.from_url(url, decode_responses=True)

    # ── Chaves ────────────────────────────────────────────────────────────────
    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"{KEY_PREFIX}:job:{job_id}"

    @staticmethod
    def _user_key(user_id: str) -> str:
        return f"{KEY_PREFIX}:user_jobs:{user_id}"

    @staticmethod
    def _channel(job_id: str) -> str:
        return f"{KEY_PREFIX}:job_events:{job_id}"

    # ── Serialização ──────────────────────────────────────────────────────────
    @staticmethod
    def _dumps(job: Job) -> str:
        return json.dumps(job.to_dict(), default=str)

    @staticmethod
    def _loads(raw: str) -> Job:
        data = json.loads(raw)
        # Enums voltam como string do JSON — recoerção mantém comparações por
        # identidade de enum funcionando no resto do código.
        data["type"] = JobType(data["type"])
        data["status"] = JobStatus(data["status"])
        return Job(**data)

    async def _save(self, job: Job) -> None:
        await self._redis.set(self._job_key(job.id), self._dumps(job), ex=JOB_TTL_SECONDS)

    # ── CRUD ──────────────────────────────────────────────────────────────────
    async def create(self, job_type: JobType, user_id: str, payload: dict) -> Job:
        job = Job(
            id=f"job_{uuid.uuid4().hex[:12]}",
            type=job_type,
            user_id=user_id,
            payload=payload,
        )
        await self._save(job)
        await self._redis.sadd(self._user_key(user_id), job.id)
        await self._redis.expire(self._user_key(user_id), JOB_TTL_SECONDS)
        return job

    async def get(self, job_id: str) -> Optional[Job]:
        raw = await self._redis.get(self._job_key(job_id))
        return self._loads(raw) if raw else None

    async def list_by_user(self, user_id: str) -> List[Job]:
        job_ids = await self._redis.smembers(self._user_key(user_id))
        if not job_ids:
            return []
        # MGET numa tacada só — evita N round-trips para listar o histórico.
        ids = list(job_ids)
        raws = await self._redis.mget([self._job_key(i) for i in ids])
        jobs = [self._loads(r) for r in raws if r]
        # Jobs expirados continuam no SET do usuário: limpa o que já não existe.
        stale = [i for i, r in zip(ids, raws) if not r]
        if stale:
            await self._redis.srem(self._user_key(user_id), *stale)
        return jobs

    # ── Transitions ───────────────────────────────────────────────────────────
    async def mark_running(self, job_id: str, msg: str = "Processando...") -> None:
        job = await self._require(job_id)
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc).isoformat()
        job.progress = 0.05
        job.progress_msg = msg
        await self._persist_and_notify(job)

    async def update_progress(self, job_id: str, progress: float, msg: str = "") -> None:
        job = await self._require(job_id)
        job.progress = min(max(progress, 0.0), 0.99)
        if msg:
            job.progress_msg = msg
        await self._persist_and_notify(job)

    async def mark_completed(self, job_id: str, result: dict) -> None:
        job = await self._require(job_id)
        job.status = JobStatus.COMPLETED
        job.progress = 1.0
        job.progress_msg = "Concluído"
        job.result = result
        self._stamp_finish(job)
        await self._persist_and_notify(job)

    async def mark_failed(self, job_id: str, error: str) -> None:
        job = await self._require(job_id)
        job.status = JobStatus.FAILED
        job.error = error
        job.progress_msg = "Falhou"
        self._stamp_finish(job)
        await self._persist_and_notify(job)

    async def mark_cancelled(self, job_id: str) -> None:
        job = await self._require(job_id)
        job.status = JobStatus.CANCELLED
        job.progress_msg = "Cancelado"
        self._stamp_finish(job)
        await self._persist_and_notify(job)

    # ── SSE ───────────────────────────────────────────────────────────────────
    async def sse_generator(self, job_id: str, timeout: float = 300.0) -> AsyncGenerator[str, None]:
        if not await self.get(job_id):
            yield 'data: {"error": "job não encontrado"}\n\n'
            return

        channel = self._channel(job_id)
        async with self._redis.pubsub() as pubsub:
            await pubsub.subscribe(channel)

            # Relê o estado DEPOIS de assinar: se o job terminou na janela entre
            # o get() acima e o subscribe(), o evento final foi publicado sem
            # ninguém ouvindo e o stream ficaria pendurado até o timeout.
            job = await self.get(job_id)
            if job and job.status in TERMINAL_STATUSES:
                yield f"data: {json.dumps(job.to_status_dict(), default=str)}\n\n"
                yield "data: [DONE]\n\n"
                return

            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    yield 'data: {"error": "timeout"}\n\n'
                    break
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=min(remaining, 30)
                )
                if message is None:
                    yield ": ping\n\n"   # mantém a conexão viva atrás de proxy
                    continue
                event = json.loads(message["data"])
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("status") in TERMINAL_VALUES:
                    yield "data: [DONE]\n\n"
                    break

    async def close(self) -> None:
        await self._redis.aclose()

    # ── Internals ─────────────────────────────────────────────────────────────
    async def _require(self, job_id: str) -> Job:
        job = await self.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} não encontrado")
        return job

    @staticmethod
    def _stamp_finish(job: Job) -> None:
        now = datetime.now(timezone.utc)
        job.completed_at = now.isoformat()
        if job.started_at:
            job.duration_ms = round(
                (now - datetime.fromisoformat(job.started_at)).total_seconds() * 1000, 2
            )

    async def _persist_and_notify(self, job: Job) -> None:
        await self._save(job)
        await self._redis.publish(
            self._channel(job.id), json.dumps(job.to_status_dict(), default=str)
        )
