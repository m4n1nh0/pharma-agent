# tests

Suíte de testes organizada em três níveis de escopo, seguindo a pirâmide de testes.

## Estrutura

```
tests/
├── unit/          → domínio puro — sem I/O, sem banco, sem rede
├── integration/   → componentes de infra com asyncio real
└── e2e/           → fluxos HTTP completos contra a API rodando
```

## Rodando

```bash
pip install pytest pytest-asyncio pytest-cov

# Todos os testes
pytest

# Por camada
pytest tests/unit/          # rápidos, sem dependências externas
pytest tests/integration/   # requerem asyncio, sem rede externa
pytest tests/e2e/           # requerem a API e RabbitMQ rodando

# Com cobertura
pytest --cov=src --cov-report=term-missing
```

## unit/

Testam as entidades e regras de domínio em isolamento total. Sem banco, sem rede, sem broker. Devem ser instantâneos.

| Arquivo | O que testa |
|---|---|
| `test_domain_entities.py` | `Job`, `DrugAnalysisResult`, `DrugInteraction`, enums de domínio |

Padrão: instancia entidades diretamente, afirma valores, sem mocks.

## integration/

Testam implementações concretas de infraestrutura com dependências reais (asyncio, memória), mas sem serviços externos (sem RabbitMQ, sem Anthropic API).

| Arquivo | O que testa |
|---|---|
| `test_job_repository.py` | `InMemoryJobRepository`: criação, transições de status, SSE via `asyncio.Queue` |
| `test_redis_job_repository.py` | `RedisJobRepository`: round-trip Job ↔ JSON e nomes de chave (sem Redis rodando) |

Requerem `@pytest.mark.asyncio`. Configure em `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

## e2e/

Testam o sistema completo via HTTP. Requerem a API rodando e o RabbitMQ disponível.

```bash
# Suba a infra antes
docker-compose up -d rabbitmq
uvicorn src.presentation.api.app:app &

pytest tests/e2e/
```

A implementar: `test_auth_flow.py`, `test_sync_analysis.py`, `test_async_job_lifecycle.py`.

## Convenções

- Fixtures de dados ficam em `conftest.py` no diretório correspondente
- Nomes de teste descrevem o comportamento: `test_mark_completed_sets_result`
- Testes de domínio nunca importam de `infrastructure` ou `presentation`
- Testes de integração nunca fazem chamadas HTTP reais
- Mocks apenas quando não há alternativa (ex: chamar a API da Anthropic em testes)
