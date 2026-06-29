"""Composition root: único lugar que instancia e conecta todas as camadas.

Nenhuma outra camada importa de outra diretamente — tudo é injetado aqui.
"""

import asyncio
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Config
from src.config.settings import settings

# Infrastructure — implementações concretas
from src.infrastructure.ai.agent.pharma_agent import PharmaAnalysisAgent
from src.infrastructure.messaging.rabbitmq_broker import broker
from src.infrastructure.persistence.job_repository import job_repository

# Application — serviços de negócio
from src.application.services.analysis_service import AnalysisService
from src.application.services.auth_service import auth_service

# Presentation — routers e middleware
from src.presentation.api.routers import auth_router, analysis_router, jobs_router
from src.presentation.api.middleware.timing import TimingMiddleware, metrics

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "dist")


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    await _agent.start()

    try:
        await broker.connect()
        if settings.embedded_worker:
            from src.presentation.worker.consumer import run_worker_background
            asyncio.create_task(run_worker_background())
    except Exception as e:
        print(f"[WARN] RabbitMQ indisponível — modo síncrono: {e}")

    yield  # app rodando

    # ── Shutdown ─────────────────────────────────────────────────────────────
    await broker.disconnect()
    await _agent.stop()


# ── Composição ───────────────────────────────────────────────────────────────
# Instancia o agente e injeta dependências nos serviços e routers
_agent = PharmaAnalysisAgent()
_analysis_service = AnalysisService(agent=_agent, job_repo=job_repository, broker=broker)

analysis_router.init_router(_analysis_service)
jobs_router.init_router(job_repository, broker)


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    description="Análise farmacêutica com IA — MCP + LangGraph + RabbitMQ",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(TimingMiddleware)

app.include_router(auth_router.router)
app.include_router(analysis_router.router)
app.include_router(jobs_router.router)

_FRONTEND_ASSETS = os.path.join(FRONTEND_DIR, "assets")
if os.path.exists(_FRONTEND_ASSETS):
    # Build do frontend (frontend/npm run build) — assets com hash em /assets, index.html servido em "/".
    app.mount("/assets", StaticFiles(directory=_FRONTEND_ASSETS), name="frontend-assets")


# ── Endpoints de sistema ──────────────────────────────────────────────────────
@app.get("/", tags=["Sistema"])
async def root():
    index = os.path.join(FRONTEND_DIR, "index.html")
    return FileResponse(index) if os.path.exists(index) else {
        "service": settings.app_name, "version": settings.app_version, "docs": "/docs"
    }


@app.get("/health", tags=["Sistema"])
async def health():
    return {"status": "healthy", "version": settings.app_version, "broker": "connected" if broker._conn else "disconnected"}


@app.get("/metrics", tags=["Sistema"])
async def get_metrics():
    return metrics.summary()


# Fallback de SPA: rotas client-side do TanStack Router (/login, /drug, /interactions, ...)
# não existem no backend — devolve index.html e deixa o roteamento acontecer no browser.
# Registrado por último para não sombrear nenhuma rota de API.
@app.get("/{full_path:path}", tags=["Sistema"], include_in_schema=False)
async def spa_fallback(full_path: str):
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not Found")


if __name__ == "__main__":
    uvicorn.run("src.presentation.api.app:app", host=settings.host, port=settings.port, reload=True)
