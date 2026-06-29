"""Contratos (ABCs) que as camadas de infra devem implementar — o domínio nunca depende de implementações concretas."""

from abc import ABC, abstractmethod
from typing import Optional, List, AsyncGenerator
from src.domain.entities.job import Job, JobStatus, JobType


class IJobRepository(ABC):
    """Contrato para persistência e notificação de jobs."""

    @abstractmethod
    def create(self, job_type: JobType, user_id: str, payload: dict) -> Job: ...

    @abstractmethod
    def get(self, job_id: str) -> Optional[Job]: ...

    @abstractmethod
    def list_by_user(self, user_id: str) -> List[Job]: ...

    @abstractmethod
    async def mark_running(self, job_id: str, msg: str) -> None: ...

    @abstractmethod
    async def update_progress(self, job_id: str, progress: float, msg: str) -> None: ...

    @abstractmethod
    async def mark_completed(self, job_id: str, result: dict) -> None: ...

    @abstractmethod
    async def mark_failed(self, job_id: str, error: str) -> None: ...

    @abstractmethod
    async def sse_generator(self, job_id: str, timeout: float) -> AsyncGenerator[str, None]: ...


class IMessageBroker(ABC):
    """Contrato para publicação de mensagens."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def publish(self, queue: str, payload: dict, priority: int) -> None: ...

    @abstractmethod
    async def publish_event(self, event: dict) -> None: ...
