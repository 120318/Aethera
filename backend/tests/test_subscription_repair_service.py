from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.media_subscription_settings import MediaSubscriptionSettings
from app.schemas.domain.media_subscription_state import MediaSubscriptionState, SubscriptionMode
from app.schemas.media_id import MediaID
from app.services.domain.subscription.repair_service import SubscriptionRepairService


class FakeSettingsRepository:
    def __init__(self) -> None:
        self.updated: list[tuple[MediaID, int | None, MediaExecutionSnapshot]] = []

    async def update_media_snapshot(
        self,
        media_id: MediaID,
        season_number: int | None,
        media: MediaExecutionSnapshot,
    ) -> bool:
        self.updated.append((media_id, season_number, media))
        return True


class FakeStore:
    def __init__(self, aggregates) -> None:
        self._aggregates = aggregates
        self.settings_repo = FakeSettingsRepository()

    async def list_all(self):
        return self._aggregates


@pytest.mark.asyncio
async def test_repair_missing_media_snapshots_for_active_subscription(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    settings = MediaSubscriptionSettings(
        sub_id="sub-1",
        media_id=media_id,
        media=None,
        followed=False,
        subscription_mode=SubscriptionMode.FIRST_RELEASE,
    )
    state = MediaSubscriptionState(
        sub_id="sub-1",
        media_id=media_id,
        media=None,
        active=True,
        followed=False,
        subscription_mode=SubscriptionMode.FIRST_RELEASE,
    )
    recovered = MediaExecutionSnapshot(media_id=media_id, title="Sample", year=2024)
    store = FakeStore([SimpleNamespace(settings=settings, state=state)])
    service = SubscriptionRepairService(store=store)

    monkeypatch.setattr(
        "app.services.domain.subscription.repair_service.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=recovered),
    )

    repaired = await service.repair_missing_media_snapshots()

    assert repaired == 1
    assert store.settings_repo.updated == [(media_id, None, recovered)]


@pytest.mark.asyncio
async def test_repair_missing_media_snapshots_skips_inactive_unfollowed(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    settings = MediaSubscriptionSettings(
        sub_id="sub-1",
        media_id=media_id,
        media=None,
        followed=False,
        subscription_mode=SubscriptionMode.FIRST_RELEASE,
    )
    state = MediaSubscriptionState(
        sub_id="sub-1",
        media_id=media_id,
        media=None,
        active=False,
        followed=False,
        subscription_mode=SubscriptionMode.FIRST_RELEASE,
    )
    store = FakeStore([SimpleNamespace(settings=settings, state=state)])
    service = SubscriptionRepairService(store=store)
    resolve_snapshot = AsyncMock()

    monkeypatch.setattr(
        "app.services.domain.subscription.repair_service.media_service.resolve_execution_snapshot",
        resolve_snapshot,
    )

    repaired = await service.repair_missing_media_snapshots()

    assert repaired == 0
    assert store.settings_repo.updated == []
    resolve_snapshot.assert_not_awaited()
