from __future__ import annotations

import time
from uuid import uuid4

from app.db.repositories.media_subscription_cycle_repository import MediaSubscriptionCycleRepository
from app.db.repositories.media_subscription_settings_repository import MediaSubscriptionSettingsRepository
from app.schemas.domain.media import MediaTarget
from app.schemas.domain.media_subscription_cycle import MediaSubscriptionCycle, SubscriptionCycleStatus
from app.schemas.domain.media_subscription_settings import MediaSubscriptionSettings
from app.schemas.domain.media_subscription_state import (
    MediaSubscriptionState,
    default_subscription_mode_for_media,
    build_subscription_state_view,
)
from app.schemas.runtime.media_management import MediaMonitorState
from app.schemas.runtime.subscription_lifecycle import (
    EndSubscriptionMutation,
    SubscriptionAggregate,
    SubscriptionMutation,
    SubscriptionRunRecord,
)


def _state_cycle_key(target: MediaTarget) -> tuple[str, int]:
    if target.media_id.media_type.value != "tv":
        return str(target.media_id), 0
    return str(target.media_id), int(target.season_number or 0)


class SubscriptionStore:
    def __init__(self) -> None:
        self.settings_repo = MediaSubscriptionSettingsRepository()
        self.cycle_repo = MediaSubscriptionCycleRepository()

    async def load_current(self, target: MediaTarget) -> SubscriptionAggregate:
        settings = await self.settings_repo.find_by_media_id(target.media_id, target.season_number)
        active_cycle, latest_cycle = await self.cycle_repo.find_current_by_media_id(target.media_id, target.season_number)
        latest_cycle = active_cycle or latest_cycle
        return self._build_aggregate(target, settings, active_cycle, latest_cycle)

    async def load_by_sub_id(self, sub_id: str) -> SubscriptionAggregate | None:
        settings = await self.settings_repo.find_by_sub_id(sub_id)
        active_cycle = await self.cycle_repo.find_active_by_sub_id(sub_id)
        latest_cycle = active_cycle or await self.cycle_repo.find_latest_by_sub_id(sub_id)
        media_id = settings.media_id if settings else (latest_cycle.media_id if latest_cycle else None)
        if media_id is None:
            return None
        season_number = settings.season_number if settings else (latest_cycle.season_number if latest_cycle else None)
        target = MediaTarget(media_id=media_id, season_number=season_number)
        return self._build_aggregate(target, settings, active_cycle, latest_cycle)

    async def list_all(self) -> list[SubscriptionAggregate]:
        settings_list = await self.settings_repo.get_all()
        targets = [MediaTarget(media_id=settings.media_id, season_number=settings.season_number) for settings in settings_list]
        active_cycle_by_target: dict[tuple[str, int], MediaSubscriptionCycle] = await self.cycle_repo.find_active_by_media_targets([
            (target.media_id, target.season_number)
            for target in targets
        ])
        latest_cycle_by_target: dict[tuple[str, int], MediaSubscriptionCycle] = await self.cycle_repo.find_latest_by_media_targets([
            (target.media_id, target.season_number)
            for target in targets
        ])
        rows: list[SubscriptionAggregate] = []
        for settings in settings_list:
            target = MediaTarget(media_id=settings.media_id, season_number=settings.season_number)
            target_key = _state_cycle_key(target)
            active_cycle = active_cycle_by_target.get(target_key)
            latest_cycle = active_cycle or latest_cycle_by_target.get(target_key)
            rows.append(self._build_aggregate(target, settings, active_cycle, latest_cycle))
        return rows

    async def list_active(self) -> list[SubscriptionAggregate]:
        cycles = await self.cycle_repo.get_active_cycles()
        rows: list[SubscriptionAggregate] = []
        for cycle in cycles:
            target = MediaTarget(media_id=cycle.media_id, season_number=cycle.season_number)
            settings = await self.settings_repo.find_by_media_id(cycle.media_id, cycle.season_number)
            rows.append(self._build_aggregate(target, settings, cycle, cycle))
        return rows

    async def find_current_monitors_by_media_ids(self, media_ids: list) -> dict[str, MediaMonitorState]:
        monitor_map = await self.cycle_repo.find_current_monitors_by_media_ids(media_ids)
        requested_media_keys = {str(item) for item in media_ids}
        settings_by_media: dict[str, MediaSubscriptionSettings] = {}
        for settings in await self.settings_repo.get_all():
            media_key = str(settings.media_id)
            if media_key not in requested_media_keys:
                continue
            if media_key not in settings_by_media or settings.followed:
                settings_by_media[media_key] = settings
        for media_id in media_ids:
            media_key = str(media_id)
            settings = settings_by_media.get(media_key)
            if media_key in monitor_map:
                monitor_map[media_key].followed = bool(settings.followed) if settings else False
                continue
            if settings and settings.followed:
                monitor_map[media_key] = MediaMonitorState(
                    subscription_id=settings.sub_id,
                    subscribed=False,
                    followed=True,
                )
        return monitor_map

    async def save_subscription(self, mutation: SubscriptionMutation) -> SubscriptionAggregate:
        now = time.time()
        existing = await self.load_current(mutation.target)
        resolved_sub_id = (
            mutation.sub_id
            or (existing.settings.sub_id if existing.settings else None)
            or (existing.active_cycle.sub_id if existing.active_cycle else None)
            or uuid4().hex
        )
        settings = MediaSubscriptionSettings(
            sub_id=resolved_sub_id,
            media_id=mutation.target.media_id,
            media=mutation.media,
            season_number=mutation.target.season_number if mutation.target.media_id.media_type.value == "tv" else None,
            followed=mutation.followed,
            subscription_mode=mutation.subscription_mode,
            upgrade_policy=mutation.upgrade_policy,
            target_filters=mutation.target_filters,
            target_filter_config_id=mutation.target_filter_config_id,
            directory_id=mutation.directory_id,
            filter_config_id=mutation.filter_config_id,
            quality_profile_id=mutation.quality_profile_id,
            filters=mutation.filters,
            sites=mutation.sites,
            unmatched_rules=list(mutation.unmatched_rules),
            follow_reminded_air_date=mutation.follow_reminded_air_date,
            follow_reminded_digital_release_date=mutation.follow_reminded_digital_release_date,
            follow_reminded_physical_release_date=mutation.follow_reminded_physical_release_date,
            follow_reminded_at=mutation.follow_reminded_at,
            follow_reminded_digital_release_at=mutation.follow_reminded_digital_release_at,
            follow_reminded_physical_release_at=mutation.follow_reminded_physical_release_at,
            created_at=existing.settings.created_at if existing.settings else now,
            updated_at=now,
        )
        await self.settings_repo.upsert(settings)
        active_cycle = existing.active_cycle
        if mutation.active:
            active_cycle = await self._upsert_active_cycle(
                target=mutation.target,
                sub_id=resolved_sub_id,
                existing=active_cycle,
                config_fingerprint=settings.compute_config_fingerprint(),
                clear_completion_snapshot=mutation.clear_completion_snapshot,
            )
        elif active_cycle is not None:
            status = SubscriptionCycleStatus.CANCELLED if mutation.end_trigger.value == "manual" else SubscriptionCycleStatus.COMPLETED
            active_cycle = active_cycle.model_copy(update={
                "status": status,
                "ended_at": time.time(),
                "ended_reason": mutation.end_reason,
                "ended_trigger": mutation.end_trigger,
                "completion_snapshot": None,
                "updated_at": time.time(),
            })
            await self.cycle_repo.upsert(active_cycle)
        return await self.load_current(mutation.target)

    async def end_subscription(self, mutation: EndSubscriptionMutation) -> SubscriptionAggregate:
        aggregate = await self.load_current(mutation.target)
        if aggregate.active_cycle is None:
            return aggregate
        if mutation.sub_id is not None and aggregate.active_cycle.sub_id != mutation.sub_id:
            return aggregate
        ended_cycle = aggregate.active_cycle.model_copy(update={
            "status": SubscriptionCycleStatus.CANCELLED if mutation.trigger.value == "manual" else SubscriptionCycleStatus.COMPLETED,
            "ended_at": time.time(),
            "ended_reason": mutation.reason,
            "ended_trigger": mutation.trigger,
            "completion_snapshot": None,
            "updated_at": time.time(),
        })
        await self.cycle_repo.upsert(ended_cycle)
        return await self.load_current(mutation.target)

    async def save_run_record(self, record: SubscriptionRunRecord) -> SubscriptionAggregate | None:
        aggregate = await self.load_by_sub_id(record.sub_id)
        if aggregate is None or aggregate.active_cycle is None:
            return aggregate
        cycle = aggregate.active_cycle.model_copy(update={
            "last_checked_at": record.checked_at,
            "warnings": list(record.warnings),
            "completion_snapshot": record.upgrade_snapshot if record.upgrade_snapshot is not None else aggregate.active_cycle.completion_snapshot,
            "updated_at": time.time(),
        })
        await self.cycle_repo.upsert(cycle)
        return await self.load_by_sub_id(record.sub_id)

    async def _upsert_active_cycle(
        self,
        *,
        target: MediaTarget,
        sub_id: str,
        existing: MediaSubscriptionCycle | None,
        config_fingerprint: str,
        clear_completion_snapshot: bool,
    ) -> MediaSubscriptionCycle:
        now = time.time()
        if existing is not None:
            cycle = existing.model_copy(update={
                "sub_id": sub_id,
                "status": SubscriptionCycleStatus.ACTIVE,
                "ended_at": None,
                "ended_reason": None,
                "ended_trigger": None,
                "completion_snapshot": None if clear_completion_snapshot else existing.completion_snapshot,
                "config_fingerprint": config_fingerprint,
                "updated_at": now,
            })
            await self.cycle_repo.upsert(cycle)
            return cycle
        cycle = MediaSubscriptionCycle(
            media_id=target.media_id,
            season_number=target.season_number if target.media_id.media_type.value == "tv" else None,
            sub_id=sub_id,
            status=SubscriptionCycleStatus.ACTIVE,
            started_at=now,
            completion_snapshot=None,
            config_fingerprint=config_fingerprint,
            created_at=now,
            updated_at=now,
        )
        await self.cycle_repo.upsert(cycle)
        return cycle

    @staticmethod
    def _build_aggregate(
        target: MediaTarget,
        settings: MediaSubscriptionSettings | None,
        active_cycle: MediaSubscriptionCycle | None,
        latest_cycle: MediaSubscriptionCycle | None,
    ) -> SubscriptionAggregate:
        state = _build_state(target, settings, active_cycle or latest_cycle)
        return SubscriptionAggregate(
            target=target,
            settings=settings,
            active_cycle=active_cycle,
            latest_cycle=latest_cycle,
            state=state,
            view=build_subscription_state_view(media_id=target.media_id, state=state, cycle=active_cycle or latest_cycle),
        )


def _build_state(
    target: MediaTarget,
    settings: MediaSubscriptionSettings | None,
    cycle: MediaSubscriptionCycle | None,
) -> MediaSubscriptionState | None:
    if not settings and not cycle:
        return None
    subscription_mode = settings.subscription_mode if settings else default_subscription_mode_for_media(target.media_id)
    return MediaSubscriptionState(
        sub_id=(settings.sub_id if settings else (cycle.sub_id if cycle else uuid4().hex)),
        media_id=target.media_id,
        media=settings.media if settings else None,
        season_number=settings.season_number if settings else target.season_number,
        active=bool(cycle and cycle.status == SubscriptionCycleStatus.ACTIVE),
        followed=bool(settings.followed) if settings else False,
        subscription_mode=subscription_mode,
        upgrade_policy=settings.upgrade_policy if settings else None,
        target_filters=settings.target_filters if settings else None,
        target_filter_config_id=settings.target_filter_config_id if settings else None,
        upgrade_completion_snapshot=cycle.completion_snapshot if cycle else None,
        created_at=min(
            [value for value in [settings.created_at if settings else None, cycle.created_at if cycle else None, time.time()] if value is not None]
        ),
        updated_at=max(
            [value for value in [settings.updated_at if settings else None, cycle.updated_at if cycle else None, time.time()] if value is not None]
        ),
        last_run_at=cycle.last_checked_at if cycle else None,
        follow_reminded_air_date=settings.follow_reminded_air_date if settings else None,
        follow_reminded_digital_release_date=settings.follow_reminded_digital_release_date if settings else None,
        follow_reminded_physical_release_date=settings.follow_reminded_physical_release_date if settings else None,
        follow_reminded_at=settings.follow_reminded_at if settings else None,
        follow_reminded_digital_release_at=settings.follow_reminded_digital_release_at if settings else None,
        follow_reminded_physical_release_at=settings.follow_reminded_physical_release_at if settings else None,
        warnings=list(cycle.warnings) if cycle else [],
    )


subscription_store = SubscriptionStore()
