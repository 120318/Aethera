import pytest

from app.schemas.domain.media import MediaExecutionSnapshot, MediaTarget
from app.schemas.domain.media_subscription_cycle import MediaSubscriptionCycle, SubscriptionCycleStatus
from app.schemas.domain.media_subscription_settings import MediaSubscriptionSettings
from app.schemas.domain.media_subscription_state import (
    SubscriptionEndReason,
    SubscriptionEndTrigger,
    SubscriptionMode,
)
from app.schemas.media_id import MediaID
from app.schemas.runtime.subscription_lifecycle import EndSubscriptionMutation
from app.services.domain.subscription.store import SubscriptionStore


class FakeSettingsRepository:
    def __init__(self, settings: MediaSubscriptionSettings | list[MediaSubscriptionSettings]) -> None:
        self.settings_list = settings if isinstance(settings, list) else [settings]
        self.settings = self.settings_list[0]

    async def find_by_media_id(self, media_id: MediaID, season_number: int | None = None) -> MediaSubscriptionSettings | None:
        for settings in self.settings_list:
            if settings.media_id == media_id and settings.season_number == season_number:
                return settings
        return None

    async def get_all(self) -> list[MediaSubscriptionSettings]:
        return list(self.settings_list)


class FakeCycleRepository:
    def __init__(self, cycle: MediaSubscriptionCycle | list[MediaSubscriptionCycle]) -> None:
        self.cycles = cycle if isinstance(cycle, list) else [cycle]
        self.cycle = self.cycles[0]
        self.upserts: list[MediaSubscriptionCycle] = []
        self.latest_by_media_calls: list[tuple[MediaID, int | None]] = []
        self.latest_by_targets_calls = 0

    async def find_active_by_media_id(self, media_id: MediaID, season_number: int | None = None) -> MediaSubscriptionCycle | None:
        for cycle in self.cycles:
            if cycle.media_id == media_id and cycle.season_number == season_number and cycle.status == SubscriptionCycleStatus.ACTIVE:
                return cycle
        return None

    async def find_latest_by_media_id(self, media_id: MediaID, season_number: int | None = None) -> MediaSubscriptionCycle | None:
        self.latest_by_media_calls.append((media_id, season_number))
        for cycle in self.cycles:
            if cycle.media_id == media_id and cycle.season_number == season_number:
                return cycle
        return None

    async def find_active_by_media_targets(self, targets: list[tuple[MediaID, int | None]]) -> dict[tuple[str, int], MediaSubscriptionCycle]:
        requested = {(str(media_id), int(season_number or 0)) for media_id, season_number in targets}
        return {
            (str(cycle.media_id), int(cycle.season_number or 0)): cycle
            for cycle in self.cycles
            if cycle.status == SubscriptionCycleStatus.ACTIVE
            and (str(cycle.media_id), int(cycle.season_number or 0)) in requested
        }

    async def find_latest_by_media_targets(self, targets: list[tuple[MediaID, int | None]]) -> dict[tuple[str, int], MediaSubscriptionCycle]:
        self.latest_by_targets_calls += 1
        requested = {(str(media_id), int(season_number or 0)) for media_id, season_number in targets}
        latest: dict[tuple[str, int], MediaSubscriptionCycle] = {}
        for cycle in self.cycles:
            key = (str(cycle.media_id), int(cycle.season_number or 0))
            if key not in requested or key in latest:
                continue
            latest[key] = cycle
        return latest

    async def find_current_by_media_id(
        self,
        media_id: MediaID,
        season_number: int | None = None,
    ) -> tuple[MediaSubscriptionCycle | None, MediaSubscriptionCycle | None]:
        latest = await self.find_latest_by_media_id(media_id, season_number)
        active = latest if latest and latest.status == SubscriptionCycleStatus.ACTIVE else None
        return active, latest

    async def find_active_by_sub_id(self, sub_id: str) -> MediaSubscriptionCycle | None:
        for cycle in self.cycles:
            if cycle.sub_id == sub_id and cycle.status == SubscriptionCycleStatus.ACTIVE:
                return cycle
        return None

    async def find_latest_by_sub_id(self, sub_id: str) -> MediaSubscriptionCycle | None:
        for cycle in self.cycles:
            if cycle.sub_id == sub_id:
                return cycle
        return None

    async def upsert(self, cycle: MediaSubscriptionCycle) -> str:
        self.cycle = cycle
        self.cycles = [item for item in self.cycles if item.cycle_id != cycle.cycle_id] + [cycle]
        self.upserts.append(cycle)
        return cycle.cycle_id


def _store_with_active_cycle(sub_id: str) -> tuple[SubscriptionStore, MediaTarget, FakeCycleRepository]:
    media = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:movie:1"), title="Sample", year=2024)
    target = MediaTarget(media_id=media.media_id)
    settings = MediaSubscriptionSettings(
        sub_id=sub_id,
        media_id=media.media_id,
        media=media,
        followed=True,
        subscription_mode=SubscriptionMode.FIRST_RELEASE,
    )
    cycle = MediaSubscriptionCycle(
        media_id=media.media_id,
        sub_id=sub_id,
        status=SubscriptionCycleStatus.ACTIVE,
    )
    cycle_repo = FakeCycleRepository(cycle)
    store = SubscriptionStore()
    store.settings_repo = FakeSettingsRepository(settings)
    store.cycle_repo = cycle_repo
    return store, target, cycle_repo


@pytest.mark.asyncio
async def test_end_subscription_skips_active_cycle_when_sub_id_mismatches():
    store, target, cycle_repo = _store_with_active_cycle("new-sub")

    aggregate = await store.end_subscription(
        EndSubscriptionMutation(
            target=target,
            sub_id="old-sub",
            trigger=SubscriptionEndTrigger.SYSTEM,
            reason=SubscriptionEndReason.MOVIE_TARGET_COMPLETED,
        )
    )

    assert aggregate.active_cycle is not None
    assert aggregate.active_cycle.sub_id == "new-sub"
    assert aggregate.active_cycle.status == SubscriptionCycleStatus.ACTIVE
    assert cycle_repo.upserts == []


@pytest.mark.asyncio
async def test_end_subscription_ends_active_cycle_when_sub_id_matches():
    store, target, cycle_repo = _store_with_active_cycle("current-sub")

    aggregate = await store.end_subscription(
        EndSubscriptionMutation(
            target=target,
            sub_id="current-sub",
            trigger=SubscriptionEndTrigger.SYSTEM,
            reason=SubscriptionEndReason.MOVIE_TARGET_COMPLETED,
        )
    )

    assert aggregate.active_cycle is None
    assert aggregate.latest_cycle is not None
    assert aggregate.latest_cycle.status == SubscriptionCycleStatus.COMPLETED
    assert len(cycle_repo.upserts) == 1


@pytest.mark.asyncio
async def test_list_all_loads_latest_cycles_in_batch():
    movie = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:movie:1"), title="Movie", year=2024)
    tv = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:tv:2"), season_number=1, title="Show", year=2024)
    settings = [
        MediaSubscriptionSettings(
            sub_id="movie-sub",
            media_id=movie.media_id,
            media=movie,
            followed=False,
            subscription_mode=SubscriptionMode.FIRST_RELEASE,
        ),
        MediaSubscriptionSettings(
            sub_id="tv-sub",
            media_id=tv.media_id,
            media=tv,
            season_number=1,
            followed=False,
            subscription_mode=SubscriptionMode.CURRENT_AIRED_COMPLETE,
        ),
    ]
    cycles = [
        MediaSubscriptionCycle(media_id=movie.media_id, sub_id="movie-sub", status=SubscriptionCycleStatus.COMPLETED),
        MediaSubscriptionCycle(media_id=tv.media_id, season_number=1, sub_id="tv-sub", status=SubscriptionCycleStatus.ACTIVE),
    ]
    cycle_repo = FakeCycleRepository(cycles)
    store = SubscriptionStore()
    store.settings_repo = FakeSettingsRepository(settings)
    store.cycle_repo = cycle_repo

    aggregates = await store.list_all()

    assert [aggregate.latest_cycle.sub_id for aggregate in aggregates if aggregate.latest_cycle] == ["movie-sub", "tv-sub"]
    assert cycle_repo.latest_by_targets_calls == 1
    assert cycle_repo.latest_by_media_calls == []
