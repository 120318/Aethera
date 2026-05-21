from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EventDispatchStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EventDispatchRecord(BaseModel):
    id: str
    event_id: str
    consumer_name: str
    status: EventDispatchStatus = EventDispatchStatus.QUEUED
    attempts: int = 0
    max_attempts: int = 3
    available_at: datetime = Field(default_factory=datetime.now)
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
