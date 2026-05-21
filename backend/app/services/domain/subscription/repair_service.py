from __future__ import annotations

import logging

from app.schemas.exception.base import AppException
from app.services.domain.media import media_service
from app.services.domain.subscription.store import SubscriptionStore, subscription_store

logger = logging.getLogger("app.services.subscription.repair")


class SubscriptionRepairService:
    def __init__(self, store: SubscriptionStore | None = None) -> None:
        self.store = store or subscription_store

    async def repair_missing_media_snapshots(self) -> int:
        repaired = 0
        aggregates = await self.store.list_all()
        for aggregate in aggregates:
            state = aggregate.state
            settings = aggregate.settings
            if state is None or settings is None or state.media is not None:
                continue
            if not state.active and not state.followed:
                continue
            try:
                media = await media_service.resolve_execution_snapshot(
                    state.media_id,
                    season_number=state.season_number,
                    require_tv_season=state.media_id.media_type.value == "tv",
                )
                updated = await self.store.settings_repo.update_media_snapshot(
                    state.media_id,
                    state.season_number,
                    media,
                )
            except AppException as exc:
                logger.warning(
                    "Subscription media snapshot repair skipped: media=%s season=%s error=%s",
                    state.media_id,
                    state.season_number,
                    exc,
                )
                continue
            if updated:
                repaired += 1
        if repaired:
            logger.info("Subscription media snapshot repair completed: repaired=%d", repaired)
        return repaired


subscription_repair_service = SubscriptionRepairService()
