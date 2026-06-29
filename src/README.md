# src

Arquitetura em camadas (Clean Architecture). As dependências fluem em uma única direção: `domain ← application ← infrastructure ← presentation`. `presentation` é a única camada que pode importar de todas as outras e é onde a injeção de dependências acontece (composition root).

```
src/
├── domain/          → regras de negócio e contratos (núcleo, sem dependências externas)
├── application/     → casos de uso, orquestração
├── infrastructure/  → implementações concretas (DB, mensageria, IA)
├── presentation/    → HTTP, SSE, filas, frontend
└── config/          → configuração centralizada
```

## domain

Camada de domínio — o núcleo do sistema. Contém as regras de negócio farmacêutico e os contratos que as outras camadas devem respeitar.

**Regra fundamental:** este diretório não importa nada de `application`, `infrastructure` ou `presentation`. Nenhuma dependência de FastAPI, SQLAlchemy, aio-pika ou qualquer framework externo.

```
domain/
├── entities/       → modelos de negócio (Pydantic, dataclasses)
└── repositories/   → interfaces abstratas (ABCs)
```

### entities/

Representam os conceitos do negócio farmacêutico.

| Arquivo | O que define |
|---|---|
| `pharma.py` | `DrugAnalysisResult`, `DrugInteraction`, `InteractionSeverity`, `PrescriptionReviewResult`, `PrescriptionAlert`, `PatientInfo`, `PrescriptionItem` |
| `job.py` | `Job`, `JobStatus`, `JobType` |

As entidades de domínio são intencionalmente separadas dos DTOs da API (`application/use_cases/dtos.py`). Um `DrugAnalysisResult` representa o resultado de negócio; o DTO representa o contrato HTTP — os dois podem divergir sem afetar um ao outro.

### repositories/

Define contratos (ABCs) que as implementações de infraestrutura precisam satisfazer.

| Interface | Implementada por |
|---|---|
| `IJobRepository` | `infrastructure/persistence/job_repository.py` |
| `IMessageBroker` | `infrastructure/messaging/rabbitmq_broker.py` |

Para trocar a persistência de memória por Redis, basta criar `RedisJobRepository(IJobRepository)` sem tocar nenhum outro arquivo.

**O que pertence aqui:** modelos Pydantic / dataclasses do negócio, enums de domínio (`JobStatus`, `InteractionSeverity`), interfaces abstratas (ABCs), regras de validação intrínsecas ao negócio.

**O que não pertence aqui:** lógica de banco de dados ou mensageria, schemas HTTP, configuração de framework, qualquer `import fastapi`, `import aio_pika`, `import sqlalchemy`.

## application

Camada de aplicação — orquestra os casos de uso do sistema. Coordena entidades de domínio, serviços de infraestrutura e regras de negócio de mais alto nível.

Pode importar de `domain`. Não importa de `infrastructure` diretamente — depende das interfaces (`IJobRepository`, `IMessageBroker`), que são injetadas pelo composition root (`presentation/api/app.py`).

```
application/
├── services/      → lógica de negócio aplicacional
└── use_cases/     → DTOs de entrada e saída da API
```

### services/

| Arquivo | Responsabilidade |
|---|---|
| `analysis_service.py` | Recebe um DTO de request, decide se processa de forma síncrona (chama o agente) ou assíncrona (cria job + publica na fila), retorna o resultado ou um `202 Accepted` com `job_id` |
| `auth_service.py` | Hashing de senha, criação e validação de tokens JWT, registro e autenticação de usuários |

**Como `analysis_service.py` decide o modo:**

```python
# Threshold configurável em src/config/settings.py
if len(dto.prescription) > settings.async_threshold_prescription:
    return await self._enqueue(...)   # 202 + job_id
return await self._agent.review_prescription(...)  # resposta direta
```

Para mudar o threshold basta ajustar a variável de ambiente `ASYNC_THRESHOLD_PRESCRIPTION` — sem alterar código.

### use_cases/

| Arquivo | O que contém |
|---|---|
| `dtos.py` | `DrugAnalysisRequestDTO`, `InteractionCheckRequestDTO`, `PrescriptionReviewRequestDTO`, `UserCreateDTO`, `UserLoginDTO`, `TokenResponseDTO` e demais schemas de request/response |

Os DTOs validam e transportam dados entre a apresentação e a aplicação. São deliberadamente separados das entidades de domínio: o contrato HTTP pode mudar (adicionar campos, renomear) sem impactar a lógica de negócio.

**O que pertence aqui:** serviços que orquestram casos de uso complexos, lógica de decisão que não é regra de domínio pura (ex: threshold sync/async), DTOs de entrada e saída da API, transformações entre DTOs e entidades de domínio.

**O que não pertence aqui:** código de banco de dados, mensageria ou HTTP, detalhes de implementação de infra (como conectar ao RabbitMQ), routers FastAPI ou middlewares.

## infrastructure

Camada de infraestrutura — implementações concretas de tudo que toca o mundo externo: banco de dados, mensageria, IA e protocolos de terceiros.

Implementa as interfaces definidas em `domain/repositories/interfaces.py`. É a única camada que pode importar drivers externos (`aio_pika`, `langchain`, `mcp`, etc.).

```
infrastructure/
├── messaging/     → broker de mensagens (RabbitMQ)
├── persistence/   → armazenamento de estado (job store)
└── ai/
    ├── agent/     → agente LangGraph multi-etapa
    └── mcp/       → servidor MCP com ferramentas farmacêuticas
```

### messaging/

| Arquivo | Responsabilidade |
|---|---|
| `rabbitmq_broker.py` | Implementa `IMessageBroker`. Gerencia conexão robusta com RabbitMQ via `aio-pika`, declara exchanges (`pharma.direct`, `pharma.events`) e filas duráveis com dead-letter. |

**Filas declaradas:**

| Fila | Conteúdo | Prefetch |
|---|---|---|
| `pharma.analyze` | Jobs de análise de medicamento | 2 |
| `pharma.interactions` | Jobs de verificação de interações | 1 |
| `pharma.prescription` | Jobs de revisão de prescrição | 1 |
| `pharma.results` | Eventos de conclusão (fanout) | — |

Para trocar por SQS ou Kafka: implemente `IMessageBroker` em um novo arquivo e atualize a injeção em `presentation/api/app.py`.

### persistence/

| Arquivo | Responsabilidade |
|---|---|
| `job_repository.py` | Implementa `IJobRepository`. Armazena jobs em memória com suporte a SSE via `asyncio.Queue`. Cada subscriber do job recebe updates em tempo real sem polling. |

Em produção, substitua por `RedisJobRepository` ou `PostgresJobRepository` implementando a mesma interface — zero impacto nas camadas acima.

### ai/agent/

| Arquivo | Responsabilidade |
|---|---|
| `pharma_agent.py` | Agente LangGraph com grafo `agent → tools → agent → END`. Expõe `analyze_drug()`, `check_interactions()`, `review_prescription()` e `stream_analysis()`. Conecta às ferramentas MCP reais via `langchain-mcp-adapters`. |
| `schemas.py` | Modelos Pydantic "LLM-facing" (`DrugAnalysisLLM`, `InteractionCheckLLM`, `PrescriptionReviewLLM`) usados com `with_structured_output()` para obter a resposta final do modelo já tipada — sem parsing de texto. |

**Grafo LangGraph:**

```
START → agent_node ──── tem tool_calls? ──→ tool_node → agent_node
                    └── não → END
```

O agente usa `claude-sonnet-4-6` com `temperature=0` para respostas determinísticas.

**Ciclo de vida:** `PharmaAnalysisAgent.start()` conecta ao MCP server (`MultiServerMCPClient`) e compila o grafo **uma única vez**, chamado no `lifespan` da API (`presentation/api/app.py`). Se o MCP server estiver indisponível, cai para um conjunto de ferramentas mock com `logging.warning` explícito — nunca silenciosamente. `stop()` é chamado no shutdown.

**Execução:** todo o fluxo é assíncrono nativo (`graph.ainvoke`, `graph.astream`) — sem `asyncio.to_thread`. Após o loop ReAct (`agent ⇄ tools`) terminar, cada método público faz uma chamada extra com `self.llm.with_structured_output(Schema)` sobre o histórico de mensagens (+ uma `HumanMessage` de fechamento, exigida pela API da Anthropic) para obter o resultado final já estruturado, combinado com os `agent_steps` calculados pelo grafo. `stream_analysis()` usa `graph.astream(stream_mode="updates")` nativo, mapeando os eventos do LangGraph para o formato SSE já consumido pelo frontend.

### ai/mcp/

| Arquivo | Responsabilidade |
|---|---|
| `pharma_tools.py` | Servidor MCP com 6 ferramentas farmacêuticas, implementado com `FastMCP` (decorators + type hints geram o schema automaticamente). Roda como processo stdio (`python -m src.infrastructure.ai.mcp.pharma_tools`) e é consumido pelo agente via `MultiServerMCPClient`. |

**Ferramentas disponíveis:**

| Tool | Descrição |
|---|---|
| `get_drug_info` | Perfil completo do medicamento (mecanismo, indicações, contraindicações, efeitos adversos) |
| `check_drug_interaction` | Interação entre dois fármacos: severidade, mecanismo e manejo clínico |
| `calculate_dose_adjustment` | Ajuste posológico para disfunção renal ou hepática |
| `check_pregnancy_safety` | Categoria gestacional FDA/ANVISA |
| `search_therapeutic_alternatives` | Alternativas terapêuticas por classe farmacológica |
| `calculate_creatinine_clearance` | Fórmula de Cockcroft-Gault |

**Expandindo a base farmacológica:**

```python
# pharma_tools.py — adicionar medicamento
DRUG_DATABASE["novo_farmaco"] = {
    "class": "Classe terapêutica",
    "mechanism": "Mecanismo de ação",
    "indications": ["indicação 1", "indicação 2"],
    "contraindications": [...],
    "adverse_effects": [...],
    "pregnancy_category": "B",
    "renal_adjustment": "...",
    "interactions": [...],
}
```

Para integrar APIs externas (DrugBank, Micromedex, OpenFDA), substitua a lógica de busca dentro da função decorada com `@mcp.tool()` correspondente — a assinatura e o schema MCP permanecem inalterados.

## presentation

Camada de apresentação — interface do sistema com o mundo externo. Contém tudo que lida com HTTP, SSE, filas e o frontend.

É a única camada que pode importar de todas as outras. É também o único lugar onde as dependências concretas de infraestrutura são instanciadas e injetadas.

```
presentation/
├── api/
│   ├── app.py          → composition root
│   ├── middleware/     → timing, autenticação
│   └── routers/        → endpoints HTTP
└── worker/
    └── consumer.py     → consumidor de filas RabbitMQ
```

### api/app.py — Composition Root

O único arquivo do projeto que instancia implementações concretas e as injeta nos serviços e routers:

```python
_agent            = PharmaAnalysisAgent()
_analysis_service = AnalysisService(agent=_agent, job_repo=job_repository, broker=broker)

analysis_router.init_router(_analysis_service)
jobs_router.init_router(job_repository, broker)
```

Também gerencia o ciclo de vida da aplicação via `lifespan`: conecta o agente ao MCP server e o broker no startup (desconecta ambos no shutdown) e opcionalmente sobe o worker embutido.

### api/middleware/

| Arquivo | Responsabilidade |
|---|---|
| `timing.py` | Atribui `X-Request-ID` único a cada request, mede duração e adiciona `X-Process-Time-Ms` na response. Emite log JSON estruturado por request. Expõe `MetricsStore` com percentis p50/p95/p99 consumidos em `GET /metrics`. |
| `auth_dependency.py` | `Depends(get_current_user)` — decodifica o Bearer JWT e retorna o usuário autenticado para injeção nos handlers. |

**Headers adicionados pelo `TimingMiddleware`:**

```
X-Request-ID:      req_a3f9c2b1...   (rastreamento fim-a-fim)
X-Process-Time-Ms: 42.17             (duração do request)
X-Slow-Request:    true              (presente apenas se > 5 s)
```

### api/routers/

| Arquivo | Prefixo | Endpoints |
|---|---|---|
| `auth_router.py` | `/auth` | `POST /register`, `/login`, `/refresh`, `/logout` · `GET /me` |
| `analysis_router.py` | — | `POST /analyze`, `/interactions`, `/prescription-review`, `/stream-analysis` |
| `jobs_router.py` | `/jobs` | `POST /analyze`, `/interactions`, `/prescription` · `GET /`, `/{id}`, `/{id}/events`, `/{id}/result` · `DELETE /{id}` |

Os routers não instanciam dependências — recebem os serviços via `init_router()` chamado em `app.py`.

**Roteamento automático sync/async em `analysis_router.py`:**

```
POST /interactions  { "drugs": ["A","B","C"] }      → síncrono (≤ 3)
POST /interactions  { "drugs": ["A","B","C","D"] }  → 202 + job_id (> 3)
```

**SSE de progresso em `jobs_router.py`:**

```
GET /jobs/{id}/events
→ Content-Type: text/event-stream
→ data: {"status":"running","progress":0.3,"progress_msg":"Verificando interações..."}
→ data: {"status":"completed","progress":1.0,"duration_ms":28430}
→ data: [DONE]
```

### worker/consumer.py

Consome as três filas farmacêuticas em paralelo e atualiza o `JobRepository` a cada etapa:

```
pharma.analyze      → handle_drug_analysis()    (prefetch 2)
pharma.interactions → handle_interactions()      (prefetch 1)
pharma.prescription → handle_prescription()      (prefetch 1)
```

Cada handler segue o padrão:

1. `mark_running()` → notifica subscribers SSE
2. `update_progress()` em etapas granulares
3. Chama o agente LangGraph
4. `mark_completed()` ou `mark_failed()`
5. Publica evento no exchange fanout `pharma.events`

Pode rodar embutido no processo da API (`EMBEDDED_WORKER=true`) ou como processo separado escalável:

```bash
python -m src.presentation.worker.consumer
```

## config

Configuração centralizada da aplicação via `pydantic-settings`.

### settings.py

Único ponto de verdade para todas as variáveis de ambiente. Lido uma vez e cacheado via `@lru_cache`.

```python
from src.config.settings import settings

settings.rabbitmq_url                    # "amqp://guest:guest@localhost:5672/"
settings.async_threshold_prescription    # 3
settings.embedded_worker                 # True
```

**Variáveis disponíveis:**

| Variável de ambiente | Atributo | Padrão | Descrição |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | `anthropic_api_key` | `""` | Chave da API Anthropic — obrigatória |
| `SECRET_KEY` | `secret_key` | `pharma-super-secret-...` | Segredo HMAC para JWT — troque em produção |
| `ALGORITHM` | `algorithm` | `HS256` | Algoritmo JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `access_token_expire_minutes` | `60` | Expiração do access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `refresh_token_expire_days` | `7` | Expiração do refresh token |
| `RABBITMQ_URL` | `rabbitmq_url` | `amqp://guest:guest@localhost:5672/` | URL de conexão AMQP |
| `EMBEDDED_WORKER` | `embedded_worker` | `true` | Worker no mesmo processo (dev) ou separado (prod) |
| `ASYNC_THRESHOLD_INTERACTIONS` | `async_threshold_interactions` | `3` | Acima desse número de fármacos, vai para a fila |
| `ASYNC_THRESHOLD_PRESCRIPTION` | `async_threshold_prescription` | `3` | Acima desse número de itens, vai para a fila |
| `HOST` | `host` | `0.0.0.0` | Host do servidor uvicorn |
| `PORT` | `port` | `8000` | Porta do servidor uvicorn |
| `DEBUG` | `debug` | `false` | Modo debug |

**Como usar:**

Qualquer arquivo do projeto importa diretamente o singleton:

```python
from src.config.settings import settings
```

Nunca leia `os.getenv()` diretamente fora deste módulo.

**.env:**

Copie `.env.example` para `.env` na raiz e preencha os valores:

```bash
cp .env.example .env
```

O arquivo `.env` nunca deve ser commitado. O `.env.example` documenta todas as variáveis com valores seguros para desenvolvimento.
