from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.domain.quality_ranking import QualityRankingConfig


class QualityProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    is_default: bool = False
    active_default: bool = False
    ranking: QualityRankingConfig = Field(default_factory=QualityRankingConfig)
    min_score: int | None = None
    tag_scores: dict[str, int] = Field(default_factory=dict)
