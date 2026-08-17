# PharmaAI

Sistema de análise farmacêutica com IA — FastAPI + LangGraph + MCP + RabbitMQ.

## O que faz

Três capacidades principais via API REST:

| Endpoint | O que analisa | Modo |
|---|---|---|
| `POST /analyze` | Um medicamento (mecanismo, indicações, contraindicações, interações) | Sempre síncrono |
| `POST /interactions` | Interações entre N fármacos | Sync ≤ 3 · Async > 3 |
| `POST /prescription-review` | Revisão completa de prescrição médica | Sync ≤ 3 itens · Async > 3 |

Requisições pesadas são roteadas automaticamente para o RabbitMQ. O cliente recebe um `job_id` e acompanha o progresso via polling (`GET /jobs/{id}`) ou SSE em tempo real (`GET /jobs/{id}/events`).

## Estrutura do projeto

```
pharma_v2/
├── src/
│   ├── domain/          → entidades e interfaces — zero dependências de framework
│   ├── application/     → serviços e DTOs — regras de negócio e orquestração
│   ├── infrastructure/  → implementações concretas (RabbitMQ, Redis, LangGraph, MCP)
│   ├── presentation/    → FastAPI, routers, middleware, worker
│   └── config/          → variáveis de ambiente centralizadas
├── frontend/            → SPA servida em /
├── tests/
│   ├── unit/            → domínio puro, sem I/O
│   ├── integration/     → repositórios e broker com asyncio real
│   └── e2e/             → fluxos HTTP completos
├── .env.example
├── docker-compose.yml
├── Dockerfile           → multi-stage: build do frontend + runtime Python
├── railway.json         → builder, healthcheck e restart policy do Railway
└── pyproject.toml
```

Cada camada tem seu próprio `README.md` com responsabilidades, arquivos e exemplos.

## Pré-requisitos

- Python 3.12+
- RabbitMQ 3.13+ (ou via Docker)
- `ANTHROPIC_API_KEY`

## Instalação rápida

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # preencha ANTHROPIC_API_KEY
```

## Rodando

**Desenvolvimento** (worker embutido no mesmo processo):

```bash
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3.13-management-alpine
EMBEDDED_WORKER=true uvicorn src.presentation.api.app:app --reload
```

**Frontend em dev** (Vite com hot-reload, proxy para a API em `:8000`):

```bash
npm install                  # instala concurrently na raiz (uma vez)
npm run install:frontend     # instala dependências do frontend (uma vez)
npm run dev                  # backend (uvicorn --reload) + frontend (vite) juntos
```

Acesse http://localhost:5173. Em produção, não é necessário rodar o Vite — o backend serve o build estático (`npm run build:frontend`) em `frontend/dist`.

**Produção** (worker como processo separado, escalável):

```bash
# Terminal 1
EMBEDDED_WORKER=false uvicorn src.presentation.api.app:app --workers 4

# Terminal 2 (pode rodar N instâncias)
python -m src.presentation.worker.consumer
```

**Docker Compose** (tudo junto):

```bash
docker-compose up --build
docker-compose up --scale worker=4   # escalar workers
```

Serviços sobem em:

| Serviço | URL |
|---|---|
| API + frontend | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| RabbitMQ management | http://localhost:15672 (guest/guest) |

## Deploy no Railway

O `Dockerfile` é multi-stage: compila o frontend (Node) e serve o build estático pelo próprio FastAPI, então **um único serviço** entrega API + SPA. O `railway.json` já aponta o builder para o Dockerfile e o healthcheck para `/health`.

**1. Criar o projeto**

```bash
railway login
railway init
railway up          # ou conecte o repo do GitHub pelo dashboard
```

**2. Definir as variáveis** (Settings → Variables):

| Variável | Valor |
|---|---|
| `ANTHROPIC_API_KEY` | sua chave |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `EMBEDDED_WORKER` | `true` |

Não defina `PORT` — o Railway injeta a porta e o `CMD` já a usa.

**3. Gerar o domínio** (Settings → Networking → Generate Domain). A SPA responde em `/`, o Swagger em `/docs`.

### RabbitMQ é opcional

Sem `RABBITMQ_URL` acessível, o broker degrada para despacho **in-process**: os jobs assíncronos continuam funcionando (o worker embutido processa em background), só não há fila durável — jobs em andamento são perdidos num redeploy. Para ter fila de verdade, adicione o template RabbitMQ ao projeto e aponte `RABBITMQ_URL` para a variável de conexão dele.

`GET /health` mostra qual modo está ativo:

```json
{"status": "healthy", "version": "3.0.0", "broker": "in-process"}
```

### Limites desta configuração

- **`--workers 1` e `numReplicas: 1`** são obrigatórios: o job store e os subscribers SSE vivem em memória (`InMemoryJobRepository`), então réplicas não veriam os mesmos jobs. Para escalar horizontalmente, implemente `IJobRepository` sobre Redis/Postgres.
- **Usuários também são em memória** (`USERS_DB` em `auth_service.py`): contas criadas via `/auth/register` desaparecem no redeploy. As contas demo continuam disponíveis.
- **`EMBEDDED_WORKER=false` com worker separado** só funciona quando o job store for compartilhado (Redis/Postgres) — hoje o worker marcaria o progresso no próprio processo e a API nunca veria. Vale também para o serviço `worker` do `docker-compose.yml`.

## Contas demo

| E-mail | Senha | Perfil |
|---|---|---|
| `demo@pharma.com` | `demo123` | Farmacêutico |
| `medico@pharma.com` | `medico123` | Médico |

## Variáveis de ambiente

| Variável | Padrão | Obrigatória |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Sim |
| `SECRET_KEY` | `pharma-super-secret-...` | Em produção |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/` | Não |
| `EMBEDDED_WORKER` | `true` | Não |
| `ASYNC_THRESHOLD_INTERACTIONS` | `3` | Não |
| `ASYNC_THRESHOLD_PRESCRIPTION` | `3` | Não |
| `PORT` | `8000` | Não (injetada pela plataforma) |
| `LOG_LEVEL` | `INFO` | Não |

Todas as configurações ficam em `src/config/settings.py`.

## Testes

```bash
pip install pytest pytest-asyncio pytest-cov

pytest                              # todos
pytest tests/unit/                  # só domínio (ultrarrápidos, sem I/O)
pytest tests/integration/           # repositórios com asyncio real
pytest --cov=src --cov-report=term-missing
```

## Regra de dependência

```
presentation → application → domain ← infrastructure
```

O domínio não importa nada de fora. Para trocar RabbitMQ por SQS ou o store em memória por Redis, basta implementar as interfaces em `src/domain/repositories/interfaces.py` — nenhuma outra camada muda.
