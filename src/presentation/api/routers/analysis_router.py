"""Endpoints de análise farmacêutica — delega ao AnalysisService."""

import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.application.use_cases.dtos import (
    DrugAnalysisRequestDTO,
    InteractionCheckRequestDTO,
    PrescriptionReviewRequestDTO,
)
from src.presentation.api.middleware.auth_dependency import get_current_user

router = APIRouter(tags=["Análise"])

_analysis_service = None


def init_router(analysis_service):
    """Injeta o AnalysisService após o app ser criado (evita import circular)."""
    global _analysis_service
    _analysis_service = analysis_service


@router.post("/analyze", summary="Análise de medicamento (síncrona)")
async def analyze_drug(
    body: DrugAnalysisRequestDTO,
    current_user: dict = Depends(get_current_user),
):
    """Sempre síncrono — 1 fármaco, resposta direta."""
    try:
        return await _analysis_service.analyze_drug(body, current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interactions", summary="Interações (auto sync/async)")
async def check_interactions(
    body: InteractionCheckRequestDTO,
    current_user: dict = Depends(get_current_user),
):
    """≤3 fármacos → síncrono. >3 → retorna job_id (202)."""
    if len(body.drugs) < 2:
        raise HTTPException(status_code=400, detail="Informe pelo menos 2 medicamentos.")
    try:
        return await _analysis_service.check_interactions(body, current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prescription-review", summary="Revisão de prescrição (auto sync/async)")
async def review_prescription(
    body: PrescriptionReviewRequestDTO,
    current_user: dict = Depends(get_current_user),
):
    """≤3 itens → síncrono. >3 → retorna job_id (202)."""
    if not body.prescription:
        raise HTTPException(status_code=400, detail="Prescrição vazia.")
    try:
        return await _analysis_service.review_prescription(body, current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream-analysis", summary="Análise com SSE (síncrona, streaming)")
async def stream_analysis(
    body: DrugAnalysisRequestDTO,
    current_user: dict = Depends(get_current_user),
):
    async def gen():
        try:
            async for chunk in _analysis_service._agent.stream_analysis(
                drug_name=body.drug_name, context=body.context, patient_info=body.patient_info
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
