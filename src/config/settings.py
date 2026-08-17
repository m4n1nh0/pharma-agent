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

    # Redis — job store compartilhado. Vazio = store em memória (processo único).
    # Obrigatório quando API e worker rodam em serviços separados.
    redis_url: str = ""

    # Async thresholds
    async_threshold_interactions: int = 3
    async_threshold_prescription: int = 3

    # Anthropic
    anthropic_api_key: str = ""

    # MCP — vazio: cada processo sobe o servidor como subprocesso stdio (dev).
    # Definido: consome o serviço MCP por HTTP (ex. http://mcp:8080/mcp).
    mcp_url: str = ""
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8080

    # CORS — origens do frontend quando ele roda em domínio próprio.
    # Lista separada por vírgula; "*" libera todas.
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

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
