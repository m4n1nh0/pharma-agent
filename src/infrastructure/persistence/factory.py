"""Escolhe a implementação de IJobRepository conforme o ambiente.

Único ponto que decide entre store local e compartilhado — API e worker chamam
`get_job_repository()` e recebem a mesma implementação, sem saber qual é.

    REDIS_URL definida  → RedisJobRepository (obrigatório com serviços separados)
    REDIS_URL vazia     → InMemoryJobRepository (dev/single-service)
"""

import logging
from functools import lru_cache

from src.config.settings import settings
from src.domain.repositories.interfaces import IJobRepository

logger = logging.getLogger("pharma.infrastructure.persistence")


@lru_cache
def get_job_repository() -> IJobRepository:
    if settings.redis_url:
        from src.infrastructure.persistence.redis_job_repository import RedisJobRepository

        logger.info("Job store: Redis (%s)", settings.redis_url.split("@")[-1])
        return RedisJobRepository(settings.redis_url)

    from src.infrastructure.persistence.job_repository import InMemoryJobRepository

    if not settings.embedded_worker:
        # Worker separado sem store compartilhado: cada processo teria o seu dict,
        # e a API veria o job em "pending" para sempre.
        logger.error(
            "EMBEDDED_WORKER=false sem REDIS_URL — API e worker não vão "
            "compartilhar os jobs. Defina REDIS_URL."
        )
    logger.info("Job store: em memória (processo único)")
    return InMemoryJobRepository()
