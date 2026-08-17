"""Configurações centralizadas — lê variáveis de ambiente e .env via Pydantic Settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # API
    app_name: str = "Pharma Analysis API"
    app_version: str = "3.0.0"
    debug: bool = False

    # Auth
    secret_key: str = "pharma-super-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    embedded_worker: bool = True

    # Async thresholds
    async_threshold_interactions: int = 3
    async_threshold_prescription: int = 3

    # Anthropic
    anthropic_api_key: str = ""

    # Servidor
    host: str = "0.0.0.0"
    port: int = 8000

    # Observabilidade
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Plataformas de deploy (Railway, etc.) injetam muitas variáveis próprias —
        # e o .env local tem chaves não declaradas aqui. Ignorar em vez de falhar.
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
