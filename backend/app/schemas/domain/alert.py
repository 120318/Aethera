from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.media_id import MediaID
from app.schemas.domain.action import ActionRecord
from app.schemas.domain.media import MediaIdentity


class AlertStatus(str, Enum):
    active = "active"
    resolved = "resolved"


class AlertSeverity(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"


class AlertCategory(str, Enum):
    task_transfer = "task_transfer"
    danmu_generate = "danmu_generate"
    media_server_sync = "media_server_sync"
    notification_send = "notification_send"


class AlertTargetType(str, Enum):
    task = "task"
    library_file = "library_file"
    notification_channel = "notification_channel"
    danmu_sidecar = "danmu_sidecar"


class AlertBellState(str, Enum):
    idle = "idle"
    running = "running"
    error = "error"


class AlertRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fingerprint: str
    status: AlertStatus = AlertStatus.active
    severity: AlertSeverity
    category: AlertCategory
    message_key: str
    message_params: dict[str, str] = Field(default_factory=dict)
    target_type: AlertTargetType | None = None
    target_id: str | None = None
    media: MediaIdentity | None = None
    media_id: MediaID | None = None
    task_id: str | None = None
    action_id: str | None = None
    occurrence_count: int = 1
    first_seen_at: datetime = Field(default_factory=datetime.now)
    last_seen_at: datetime = Field(default_factory=datetime.now)
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AlertRaiseRequest(BaseModel):
    fingerprint: str
    severity: AlertSeverity
    category: AlertCategory
    message_key: str
    message_params: dict[str, str] = Field(default_factory=dict)
    target_type: AlertTargetType | None = None
    target_id: str | None = None
    media: MediaIdentity | None = None
    media_id: MediaID | None = None
    task_id: str | None = None
    action_id: str | None = None


class AlertResolveRequest(BaseModel):
    fingerprint: str


class AlertSummary(BaseModel):
    active_count: int = 0
    active_action_count: int = 0
    unacknowledged_error_count: int = 0
    unacknowledged_warning_count: int = 0
    bell_state: AlertBellState = AlertBellState.idle


class AlertCenterResponse(BaseModel):
    summary: AlertSummary
    active_actions: list[ActionRecord] = Field(default_factory=list)
    alerts: list[AlertRecord] = Field(default_factory=list)
