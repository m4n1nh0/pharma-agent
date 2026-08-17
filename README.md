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
├── docker-compose.yml   → stack completa: frontend, api, worker, mcp, redis, rabbitmq
├── Dockerfile           → monolito (frontend + api num processo só)
├── Dockerfile.api       → serviço da API
├── Dockerfile.worker    → serviço do worker
├── Dockerfile.mcp       → serviço do MCP
├── Dockerfile.frontend  → SPA servida por Caddy
├── railway.*.json       → config as code, uma por serviço
└── pyproject.toml
```

Cada camada tem seu próprio `README.md` com responsabilidades, arquivos e exemplos.

## Pré-requisitos

- Python 3.12+
- Docker (a stack completa sobe via `docker compose`)
- RabbitMQ 3.13+ e Redis 7+ — só se for rodar fora do compose
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

**Stack completa em serviços separados** (espelha o deploy):

```bash
cp .env.example .env             # preencha ANTHROPIC_API_KEY e SECRET_KEY
docker compose up --build
docker compose up -d --scale worker=3   # escalar só o worker
```

| Serviço | URL | Papel |
|---|---|---|
| frontend | http://localhost:3000 | SPA estática (Caddy) |
| api | http://localhost:8000 | REST + SSE · [/docs](http://localhost:8000/docs) |
| mcp | http://localhost:8080/mcp | ferramentas farmacêuticas (FastMCP) |
| rabbitmq | http://localhost:15672 | management UI (guest/guest) |
| redis | localhost:6379 | job store + pub/sub |
| worker | — | consome as filas, sem porta |

## Arquitetura em serviços

```
                    ┌──────────────┐
   browser ────────▶│   frontend   │  Caddy: estáticos + fallback de SPA
                    │  Dockerfile. │  VITE_API_URL embutida no build
                    │   frontend   │
                    └──────┬───────┘
                           │ HTTP (CORS)
                    ┌──────▼───────┐        ┌──────────────┐
                    │     api      │───────▶│     mcp      │  FastMCP
                    │  Dockerfile. │        │  Dockerfile. │  streamable-http
                    │     api      │        │     mcp      │
                    └───┬──────┬───┘        └──────▲───────┘
                publica │      │ lê estado         │
                    ┌───▼────┐ │  ┌──────────┐     │
                    │rabbitmq│ └─▶│  redis   │     │
                    └───┬────┘    └────▲─────┘     │
                consome │              │ escreve   │
                    ┌───▼──────────┐   │           │
                    │    worker    │───┴───────────┘
                    │  Dockerfile. │
                    │    worker    │
                    └──────────────┘
```

Três decisões sustentam essa separação:

- **Redis como job store** (`RedisJobRepository`) — a API cria o job, o worker escreve progresso e resultado, e ambos leem o mesmo estado. Com o store em memória cada processo teria o seu, e a API veria `pending` para sempre.
- **Pub/sub para o SSE** — `GET /jobs/{id}/events` é servido pela API, mas os eventos são publicados pelo worker. Sem pub/sub o evento não cruzaria o limite do processo.
- **MCP por HTTP** — antes cada processo do agente subia o servidor MCP como subprocesso stdio. Como serviço, API e worker compartilham uma instância só de ferramentas.

## Deploy no Railway

Seis serviços: quatro construídos deste repo, dois de template.

**1. Redis e RabbitMQ** — adicione pelos templates do Railway. Cada um expõe uma URL de conexão nas variáveis.

**2. Para cada serviço do repo**, crie um serviço apontando para este repositório e defina o arquivo de config em Settings → Config as code:

| Serviço | Config as code | Dockerfile |
|---|---|---|
| `api` | `railway.api.json` | `Dockerfile.api` |
| `worker` | `railway.worker.json` | `Dockerfile.worker` |
| `mcp` | `railway.mcp.json` | `Dockerfile.mcp` |
| `frontend` | `railway.frontend.json` | `Dockerfile.frontend` |

Sem apontar o config, o Railway tenta detectar o build sozinho e erra o serviço. Se preferir não usar config as code, defina o Dockerfile Path na mão em cada serviço.

**3. Variáveis por serviço:**

| Serviço | Variáveis |
|---|---|
| `api` | `ANTHROPIC_API_KEY`, `SECRET_KEY`, `REDIS_URL`, `RABBITMQ_URL`, `MCP_URL`, `EMBEDDED_WORKER=false`, `CORS_ORIGINS=https://<dominio-do-frontend>` |
| `worker` | `ANTHROPIC_API_KEY`, `REDIS_URL`, `RABBITMQ_URL`, `MCP_URL` |
| `mcp` | `MCP_TRANSPORT=streamable-http`, `MCP_HOST=::`, `PORT=8080` |
| `frontend` | `VITE_API_URL=https://<dominio-da-api>` |

`MCP_URL` aponta para a rede privada: `http://mcp.railway.internal:8080/mcp`.

**4. Domínios públicos** só para `frontend` e `api` (Settings → Networking → Generate Domain). `worker`, `mcp`, Redis e RabbitMQ ficam só na rede privada.

Dois detalhes que costumam custar tempo:

- **A rede privada do Railway é IPv6.** Por isso `MCP_HOST=::` no serviço MCP — escutando só em `0.0.0.0` ele não recebe o tráfego interno de `api` e `worker`.
- **`VITE_API_URL` é build-time.** O Vite embute o valor no bundle; trocar o domínio da API exige redeploy do `frontend`, não só mudar a variável.

### O worker não pode dormir

Se você usar app sleeping (scale-to-zero) no projeto, deixe-o **desligado no worker**. Ele não recebe requisição HTTP — fica com uma conexão AMQP aberta consumindo fila. Dormindo, ninguém o acorda e as mensagens ficam paradas. A `api` pode dormir; o `worker`, não. Redis e RabbitMQ são serviços com estado e ficam sempre ativos.

### Ainda em memória

**Usuários** (`USERS_DB` em `auth_service.py`) continuam em memória, por processo. Contas criadas via `/auth/register` valem só para a réplica que atendeu o request e desaparecem no redeploy; as contas demo existem em todas. Login funciona porque o JWT é validado com `SECRET_KEY` — que precisa ser **a mesma** em `api` e em qualquer réplica.

### Deploy monolítico (alternativa)

O `Dockerfile` da raiz continua funcionando: compila o frontend, serve tudo num processo só com `EMBEDDED_WORKER=true`, sem Redis nem serviço MCP. Serve como rollback rápido — um serviço, uma variável (`ANTHROPIC_API_KEY`) e pronto.

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
| `REDIS_URL` | — (vazio = em memória) | Com worker separado |
| `MCP_URL` | — (vazio = subprocesso stdio) | Com serviço MCP |
| `CORS_ORIGINS` | `*` | Com frontend em domínio próprio |
| `VITE_API_URL` | — (vazio = mesma origem) | Com frontend em domínio próprio |
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
