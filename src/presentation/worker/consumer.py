"""Consome filas RabbitMQ e delega o processamento ao agente.

Pode rodar como processo separado: python -m src.presentation.worker.consumer
"""

import asyncio
import logging
import os
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from datetime import datetime, timezone
from src.infrastructure.messaging.rabbitmq_broker import broker, QUEUE_ANALYZE, QUEUE_INTERACTIONS, QUEUE_PRESCRIPTION
from src.infrastructure.persistence.factory import get_job_repository
from src.infrastructure.ai.agent.pharma_agent import PharmaAnalysisAgent

logger = logging.getLogger("pharma.worker")
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')

_agent = PharmaAnalysisAgent()

# Mesma fábrica usada pela API: com REDIS_URL definida, os dois processos
# enxergam o mesmo job store (get_job_repository é cacheada por processo).
job_repository = get_job_repository()


def set_agent(agent: PharmaAnalysisAgent) -> None:
    """Injeta um agente já iniciado (modo embutido).

    Evita que o worker suba um segundo MCP server no mesmo processo do FastAPI —
    e garante que `start()` já foi chamado, sem o qual o grafo é None.
    """
    global _agent
    _agent = agent


async def handle_drug_analysis(payload: dict) -> None:
    job_id = payload["job_id"]
    await job_repository.mark_running(job_id, "Consultando base farmacológica...")
    try:
        from src.domain.entities.pharma import PatientInfo
        patient = PatientInfo(**payload["patient_info"]) if payload.get("patient_info") else None
        await job_repository.update_progress(job_id, 0.30, "Agente LangGraph analisando...")
        result = await _agent.analyze_drug(drug_name=payload["drug_name"], context=payload.get("context"), patient_info=patient)
        await job_repository.mark_completed(job_id, result.model_dump())
        await broker.publish_event({"event": "job.completed", "job_id": job_id, "type": "drug_analysis"})
    except Exception as exc:
        await job_repository.mark_failed(job_id, str(exc))
        raise


async def handle_interactions(payload: dict) -> None:
    job_id = payload["job_id"]
    drugs = payload.get("drugs", [])
    await job_repository.mark_running(job_id, f"Verificando {len(drugs)} medicamentos...")
    try:
        from src.domain.entities.pharma import PatientInfo
        patient = PatientInfo(**payload["patient_info"]) if payload.get("patient_info") else None
        pairs = [(drugs[i], drugs[j]) for i in range(len(drugs)) for j in range(i+1, len(drugs))]
        for idx, (a, b) in enumerate(pairs):
            await job_repository.update_progress(job_id, 0.1 + (idx/max(len(pairs),1))*0.7, f"{a} × {b}...")
            await asyncio.sleep(0.05)
        result = await _agent.check_interactions(drugs=drugs, patient_info=patient)
        await job_repository.mark_completed(job_id, result.model_dump())
        await broker.publish_event({"event": "job.completed", "job_id": job_id, "type": "interactions"})
    except Exception as exc:
        await job_repository.mark_failed(job_id, str(exc))
        raise


async def handle_prescription(payload: dict) -> None:
    job_id = payload["job_id"]
    items = payload.get("prescription", [])
    await job_repository.mark_running(job_id, f"Revisando {len(items)} medicamento(s)...")
    try:
        from src.domain.entities.pharma import PatientInfo, PrescriptionItem
        patient = PatientInfo(**payload["patient_info"]) if payload.get("patient_info") else None
        prescription = [PrescriptionItem(**i) for i in items]
        for pct, msg in [(0.10,"Carregando perfil dos fármacos..."),(0.30,"Verificando interações..."),(0.55,"Analisando duplicidades..."),(0.70,"Avaliando posologia..."),(0.85,"Calculando score de segurança...")]:
            await job_repository.update_progress(job_id, pct, msg)
            await asyncio.sleep(0.15)
        result = await _agent.review_prescription(prescription=prescription, patient_info=patient, clinical_context=payload.get("clinical_context"))
        await job_repository.mark_completed(job_id, result.model_dump())
        await broker.publish_event({"event": "job.completed", "job_id": job_id, "type": "prescription_review"})
    except Exception as exc:
        await job_repository.mark_failed(job_id, str(exc))
        raise


async def run_worker() -> None:
    logger.info("Iniciando worker farmacêutico...")
    await _agent.start()  # compila o grafo LangGraph e conecta ao MCP server
    await broker.connect()
    await asyncio.gather(
        broker.consume(QUEUE_ANALYZE, handle_drug_analysis, prefetch=2),
        broker.consume(QUEUE_INTERACTIONS, handle_interactions, prefetch=1),
        broker.consume(QUEUE_PRESCRIPTION, handle_prescription, prefetch=1),
    )


async def run_worker_background() -> None:
    """Modo embutido: roda no mesmo processo que o FastAPI.

    Usado em dev e em deploy single-service (Railway), onde o job store em
    memória exige que API e worker compartilhem o processo. Sem RabbitMQ,
    `consume` apenas registra os handlers e retorna — o broker então despacha
    in-process (ver RabbitMQBroker._publish_local).
    """
    logger.info("Worker embutido iniciado (broker=%s)",
                "rabbitmq" if broker.is_connected else "in-process")
    try:
        await asyncio.gather(
            broker.consume(QUEUE_ANALYZE, handle_drug_analysis, prefetch=2),
            broker.consume(QUEUE_INTERACTIONS, handle_interactions, prefetch=1),
            broker.consume(QUEUE_PRESCRIPTION, handle_prescription, prefetch=1),
        )
    except Exception as e:
        logger.warning("Worker encerrado: %s", e)


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker encerrado")
