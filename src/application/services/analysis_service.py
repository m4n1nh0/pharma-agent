"""Orquestra os casos de uso de análise farmacêutica: decide sync vs async, delega ao agente ou à fila."""

from fastapi.responses import JSONResponse

from src.config.settings import settings
from src.domain.entities.job import JobType
from src.application.use_cases.dtos import (
    DrugAnalysisRequestDTO,
    InteractionCheckRequestDTO,
    PrescriptionReviewRequestDTO,
)


class AnalysisService:
    """
    Ponto único de entrada para as análises.
    Decide se processa de forma síncrona ou enfileira no RabbitMQ.
    """

    def __init__(self, agent, job_repo, broker):
        self._agent    = agent
        self._job_repo = job_repo
        self._broker   = broker

    # ── Drug Analysis (sempre síncrono) ──────────────────────────────────────
    async def analyze_drug(self, dto: DrugAnalysisRequestDTO, user_id: str):
        return await self._agent.analyze_drug(
            drug_name=dto.drug_name,
            context=dto.context,
            patient_info=dto.patient_info,
        )

    # ── Interactions (threshold) ──────────────────────────────────────────────
    async def check_interactions(self, dto: InteractionCheckRequestDTO, user_id: str):
        if len(dto.drugs) > settings.async_threshold_interactions:
            return await self._enqueue(
                job_type=JobType.INTERACTIONS,
                user_id=user_id,
                queue="pharma.interactions",
                payload={"drugs": dto.drugs, "patient_info": dto.patient_info.model_dump() if dto.patient_info else None},
                reason=f"{len(dto.drugs)} fármacos → processamento assíncrono",
                extra={"pairs_to_check": len(dto.drugs) * (len(dto.drugs) - 1) // 2},
            )
        return await self._agent.check_interactions(
            drugs=dto.drugs,
            patient_info=dto.patient_info,
        )

    # ── Prescription Review (threshold) ──────────────────────────────────────
    async def review_prescription(self, dto: PrescriptionReviewRequestDTO, user_id: str):
        if len(dto.prescription) > settings.async_threshold_prescription:
            return await self._enqueue(
                job_type=JobType.PRESCRIPTION,
                user_id=user_id,
                queue="pharma.prescription",
                payload={
                    "prescription": [i.model_dump() for i in dto.prescription],
                    "patient_info": dto.patient_info.model_dump() if dto.patient_info else None,
                    "clinical_context": dto.clinical_context,
                },
                reason=f"{len(dto.prescription)} itens → processamento assíncrono",
                extra={"items_count": len(dto.prescription)},
                priority=1 if len(dto.prescription) >= 6 else 0,
            )
        return await self._agent.review_prescription(
            prescription=dto.prescription,
            patient_info=dto.patient_info,
            clinical_context=dto.clinical_context,
        )

    # ── helper ────────────────────────────────────────────────────────────────
    async def _enqueue(
        self,
        job_type: JobType,
        user_id: str,
        queue: str,
        payload: dict,
        reason: str,
        extra: dict = None,
        priority: int = 0,
    ) -> JSONResponse:
        job = await self._job_repo.create(job_type=job_type, user_id=user_id, payload=payload)
        await self._broker.publish(queue, {"job_id": job.id, "user_id": user_id, **payload}, priority)
        return JSONResponse(
            status_code=202,
            content={
                "mode":       "async",
                "job_id":     job.id,
                "status":     "pending",
                "reason":     reason,
                "poll_url":   f"/jobs/{job.id}",
                "stream_url": f"/jobs/{job.id}/events",
                "result_url": f"/jobs/{job.id}/result",
                **(extra or {}),
            },
        )
