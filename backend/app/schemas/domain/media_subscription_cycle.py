from __future__ import annotations

import time
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.domain.media_subscription_state import (
    SubscriptionEndReason,
    SubscriptionEndTrigger,
    UpgradeCompletionSnapshot,
)
from app.schemas.domain.subscription import SubscriptionSearchWarning
from app.schemas.media_id import MediaID


class SubscriptionCycleStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MediaSubscriptionCycle(BaseModel):
    cycle_id: str = Field(default_factory=lambda: uuid4().hex)
    media_id: MediaID
    season_number: int | None = None
    sub_id: str
    status: SubscriptionCycleStatus = SubscriptionCycleStatus.ACTIVE
    started_at: float = Field(default_factory=lambda: time.time())
    last_checked_at: float | None = None
    ended_at: float | None = None
    ended_reason: SubscriptionEndReason | None = None
    ended_trigger: SubscriptionEndTrigger | None = None
    warnings: list[SubscriptionSearchWarning] = Field(default_factory=list)
    completion_snapshot: UpgradeCompletionSnapshot | None = None
    config_fingerprint: str | None = None
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class MediaSubscriptionCyclePatch(BaseModel):
    last_checked_at: float | None = None
    ended_at: float | None = None
    ended_reason: SubscriptionEndReason | None = None
    ended_trigger: SubscriptionEndTrigger | None = None
    warnings: list[SubscriptionSearchWarning] | None = None
    completion_snapshot: UpgradeCompletionSnapshot | None = None
    config_fingerprint: str | None = None
