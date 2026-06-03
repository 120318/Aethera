from __future__ import annotations

from pydantic import BaseModel


class SubscriptionEnabledEventMeta(BaseModel):
    follow_auto_enabled: bool


class FollowReleasedEventMeta(BaseModel):
    air_date: str
    release_kind: str = "theatrical"


class FollowStateChangedEventMeta(BaseModel):
    season_number: int | None = None
