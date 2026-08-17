# ── Stage 1: build do frontend ────────────────────────────────────────────────
# frontend/dist não é versionado (.gitignore), então o build acontece aqui.
FROM node:20-alpine AS frontend

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ── Stage 2: runtime Python ───────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código
COPY . .

# Frontend compilado — servido pelo FastAPI em "/" (ver src/presentation/api/app.py)
COPY --from=frontend /build/dist ./frontend/dist

# Cria usuário não-root
RUN useradd -m pharma && chown -R pharma:pharma /app
USER pharma

EXPOSE 8000

# `sh -c` para expandir $PORT (injetada pelo Railway em runtime) e `exec` para o
# uvicorn assumir o PID 1 — sem isso o SIGTERM do deploy não chega ao processo e
# o shutdown gracioso não acontece.
# --workers 1 é obrigatório: o job store e os subscribers SSE são em memória,
# então dois workers não veriam os mesmos jobs.
CMD ["sh", "-c", "exec uvicorn src.presentation.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
