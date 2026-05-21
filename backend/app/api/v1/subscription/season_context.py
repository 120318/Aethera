from __future__ import annotations

from app.api.deps import require_tv_season
from app.schemas.media_id import MediaID


def require_subscription_season(media_id: MediaID, season_number: int | None) -> int | None:
    return require_tv_season(media_id, season_number)
