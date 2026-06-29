"""Job assíncrono de análise farmacêutica — Python puro, sem dependência de infra."""

import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional, AsyncGenerator
from dataclasses import dataclass, field, asdict
from enum import Enum


class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    DRUG_ANALYSIS  = "drug_analysis"
    INTERACTIONS   = "interactions"
    PRESCRIPTION   = "prescription_review"


@dataclass
class Job:
    id: str
    type: JobType
    user_id: str
    payload: dict
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    progress_msg: str = "Na fila..."
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_status_dict(self) -> dict:
        return {
            "job_id":       self.id,
            "type":         self.type,
            "status":       self.status,
            "progress":     round(self.progress, 2),
            "progress_msg": self.progress_msg,
            "created_at":   self.created_at,
            "started_at":   self.started_at,
            "completed_at": self.completed_at,
            "duration_ms":  self.duration_ms,
            "error":        self.error,
            "has_result":   self.result is not None,
        }
