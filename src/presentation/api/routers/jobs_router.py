"""Endpoints para gerenciar jobs assíncronos: enfileirar, consultar, SSE, resultado."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.application.use_cases.dtos import (
    DrugAnalysisRequestDTO,
    InteractionCheckRequestDTO,
    PrescriptionReviewRequestDTO,
)
from src.domain.entities.job import JobStatus, JobType
from src.presentation.api.middleware.auth_dependency import get_current_user

router = APIRouter(prefix="/jobs", tags=["Jobs Assíncronos"])

_job_repo = None
_broker   = None


def init_router(job_repo, broker):
    global _job_repo, _broker
    _job_repo = job_repo
    _broker   = broker


# ── Enfileirar ────────────────────────────────────────────────────────────────

@router.post("/analyze", status_code=202)
async def enqueue_drug_analysis(body: DrugAnalysisRequestDTO, current_user: dict = Depends(get_current_user)):
    job = _job_repo.create(JobType.DRUG_ANALYSIS, current_user["id"], {
        "drug_name": body.drug_name, "context": body.context,
        "patient_info": body.patient_info.model_dump() if body.patient_info else None,
    })
    await _broker.publish("pharma.analyze", {"job_id": job.id, "user_id": current_user["id"], **job.payload})
    return {"job_id": job.id, "status": "pending", "stream_url": f"/jobs/{job.id}/events", "result_url": f"/jobs/{job.id}/result"}


@router.post("/interactions", status_code=202)
async def enqueue_interactions(body: InteractionCheckRequestDTO, current_user: dict = Depends(get_current_user)):
    if len(body.drugs) < 2:
        raise HTTPException(status_code=400, detail="Informe pelo menos 2 medicamentos.")
    job = _job_repo.create(JobType.INTERACTIONS, current_user["id"], {
        "drugs": body.drugs,
        "patient_info": body.patient_info.model_dump() if body.patient_info else None,
    })
    await _broker.publish("pharma.interactions", {"job_id": job.id, "user_id": current_user["id"], **job.payload})
    return {"job_id": job.id, "status": "pending", "pairs": len(body.drugs)*(len(body.drugs)-1)//2,
            "stream_url": f"/jobs/{job.id}/events", "result_url": f"/jobs/{job.id}/result"}


@router.post("/prescription", status_code=202)
async def enqueue_prescription(body: PrescriptionReviewRequestDTO, current_user: dict = Depends(get_current_user)):
    job = _job_repo.create(JobType.PRESCRIPTION, current_user["id"], {
        "prescription": [i.model_dump() for i in body.prescription],
        "patient_info": body.patient_info.model_dump() if body.patient_info else None,
        "clinical_context": body.clinical_context,
    })
    await _broker.publish("pharma.prescription", {"job_id": job.id, "user_id": current_user["id"], **job.payload},
                          priority=1 if len(body.prescription) >= 5 else 0)
    return {"job_id": job.id, "status": "pending", "items": len(body.prescription),
            "stream_url": f"/jobs/{job.id}/events", "result_url": f"/jobs/{job.id}/result"}


# ── Consultar ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_jobs(current_user: dict = Depends(get_current_user)):
    jobs = _job_repo.list_by_user(current_user["id"])
    return {"total": len(jobs), "jobs": [j.to_status_dict() for j in sorted(jobs, key=lambda x: x.created_at, reverse=True)]}


@router.get("/{job_id}")
async def get_job(job_id: str, current_user: dict = Depends(get_current_user)):
    return _owned(job_id, current_user).to_status_dict()


@router.get("/{job_id}/result")
async def get_result(job_id: str, current_user: dict = Depends(get_current_user)):
    job = _owned(job_id, current_user)
    if job.status == JobStatus.PENDING:
        raise HTTPException(status_code=202, detail="Job ainda na fila.")
    if job.status == JobStatus.RUNNING:
        raise HTTPException(status_code=202, detail=f"Progresso: {int(job.progress*100)}%")
    if job.status == JobStatus.FAILED:
        raise HTTPException(status_code=500, detail=f"Falhou: {job.error}")
    return {"job_id": job.id, "type": job.type, "duration_ms": job.duration_ms,
            "completed_at": job.completed_at, "result": job.result}


@router.get("/{job_id}/events")
async def job_events(job_id: str, current_user: dict = Depends(get_current_user)):
    _owned(job_id, current_user)
    return StreamingResponse(
        _job_repo.sse_generator(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/{job_id}")
async def cancel_job(job_id: str, current_user: dict = Depends(get_current_user)):
    job = _owned(job_id, current_user)
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Job já finalizado: {job.status}")
    job.status = JobStatus.CANCELLED
    return {"job_id": job_id, "status": "cancelled"}


def _owned(job_id: str, user: dict):
    job = _job_repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' não encontrado.")
    if job.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    return job
