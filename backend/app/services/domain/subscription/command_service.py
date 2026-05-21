from __future__ import annotations

import logging

from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.event import EventActor, EventEntityRef, EventSource, MediaEventCreate
from app.schemas.domain.media import MediaExecutionSnapshot, MediaTarget
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.media_download_config import MediaDownloadConfigView
from app.schemas.domain.media_subscription_cycle import MediaSubscriptionCycle
from app.schemas.domain.media_subscription_state import (
    MediaSubscriptionState,
    MediaSubscriptionStatePatch,
    SubscriptionEndReason,
    SubscriptionEndTrigger,
    SubscriptionMode,
    default_subscription_mode_for_media,
    resolve_subscription_mode,
    resolve_upgrade_policy_for_mode,
)
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.schemas.exception import ConfigurationException, DownloadException
from app.services.audit.event_service import event_service
from app.services.domain.directory import directory_service
from app.services.domain.media import media_service
from app.services.domain.subscription.download_config_service import subscription_download_config_service
from app.services.domain.subscription.store import SubscriptionStore, subscription_store
from app.schemas.runtime.subscription_lifecycle import (
    EndSubscriptionCommand,
    EndSubscriptionMutation,
    SaveSubscriptionCommand,
    SetSubscriptionStateCommand,
    SubscriptionChange,
    SubscriptionLifecycleEventIntent,
    SubscriptionLifecycleEventType,
    SubscriptionMutation,
)


logger = logging.getLogger("app.services.subscription.command")


class SubscriptionCommandService:
    def __init__(self, store: SubscriptionStore | None = None) -> None:
        self.store = store or subscription_store

    @staticmethod
    def validate_media_snapshot_target(media: MediaExecutionSnapshot, media_id, season_number: int | None) -> None:
        if media.media_id != media_id:
            raise DownloadException("backendErrors.subscriptionMediaSnapshotMismatch")
        expected_season_number = season_number if media_id.media_type == MediaType.tv else None
        if media.season_number != expected_season_number:
            raise DownloadException("backendErrors.subscriptionMediaSnapshotSeasonMismatch")

    @staticmethod
    def normalize_upgrade_policy_for_media(media_id, upgrade_policy: UpgradePolicy | None) -> UpgradePolicy | None:
        if not upgrade_policy or not upgrade_policy.enabled:
            return None
        if media_id.media_type.value != "movie":
            return upgrade_policy
        return UpgradePolicy(
            enabled=True,
            strategy="consistent_allow_temp",
            min_upgrade_score_delta=0,
            lock_mode="best_existing",
        )

    @staticmethod
    def normalize_filters(filters: SubscriptionFilters | None) -> SubscriptionFilters | None:
        if not filters:
            return None
        if filters.upgrade_policy is None:
            return filters
        return filters.model_copy(update={"upgrade_policy": None})

    @classmethod
    def resolve_target_filter_payload(
        cls,
        command: SaveSubscriptionCommand,
        requested_mode: SubscriptionMode,
    ) -> tuple[SubscriptionFilters | None, str | None]:
        if requested_mode != SubscriptionMode.UPGRADE_CONTINUOUS:
            return None, None
        return cls.normalize_filters(command.target_filters), command.target_filter_config_id

    @staticmethod
    def should_clear_upgrade_snapshot(
        *,
        previous_active: bool,
        next_active: bool,
        existing_upgrade_policy: UpgradePolicy | None,
        next_upgrade_policy: UpgradePolicy | None,
        active_cycle: MediaSubscriptionCycle | None,
        next_config_fingerprint: str | None,
    ) -> bool:
        if not next_active:
            return False
        if not previous_active:
            return True
        if not existing_upgrade_policy and next_upgrade_policy:
            return True
        if not next_upgrade_policy or not next_upgrade_policy.enabled:
            return False
        if not active_cycle or not active_cycle.completion_snapshot:
            return False
        snapshot_fingerprint = active_cycle.completion_snapshot.config_fingerprint
        if not snapshot_fingerprint:
            return True
        if next_config_fingerprint and snapshot_fingerprint != next_config_fingerprint:
            return True
        if next_config_fingerprint and active_cycle.config_fingerprint and active_cycle.config_fingerprint != next_config_fingerprint:
            return True
        return False

    async def save_subscription(self, target: MediaTarget, command: SaveSubscriptionCommand) -> SubscriptionChange:
        previous_aggregate = await self.store.load_current(target)
        previous = previous_aggregate.state
        requested_mode = command.subscription_mode or resolve_subscription_mode(
            target.media_id,
            command.upgrade_policy if command.upgrade_policy else (previous.upgrade_policy if previous else None),
        )
        resolved_upgrade_policy = self.normalize_upgrade_policy_for_media(
            target.media_id,
            resolve_upgrade_policy_for_mode(
                target.media_id,
                requested_mode,
                requested_upgrade_policy=command.upgrade_policy,
                existing_upgrade_policy=previous.upgrade_policy if previous else None,
            ),
        )
        existing_upgrade_policy = self.normalize_upgrade_policy_for_media(target.media_id, previous.upgrade_policy if previous else None)
        normalized_filters = self.normalize_filters(command.filters)
        normalized_target_filters, normalized_target_filter_config_id = self.resolve_target_filter_payload(command, requested_mode)
        next_media = await self._resolve_next_media(target, previous, command.active or command.followed)
        if command.active:
            await self._validate_activation_directory(target, command.directory_id)

        provisional = SubscriptionMutation(
            target=target,
            sub_id=previous.sub_id if previous else None,
            media=next_media,
            active=command.active,
            followed=command.followed,
            subscription_mode=requested_mode,
            upgrade_policy=resolved_upgrade_policy,
            target_filters=normalized_target_filters,
            target_filter_config_id=normalized_target_filter_config_id,
            directory_id=command.directory_id,
            filter_config_id=command.filter_config_id,
            quality_profile_id=command.quality_profile_id,
            filters=normalized_filters,
            sites=command.sites,
            unmatched_rules=list(command.unmatched_rules or []),
        )
        next_config_fingerprint = self._mutation_fingerprint(provisional)
        should_clear_snapshot = self.should_clear_upgrade_snapshot(
            previous_active=bool(previous.active) if previous else False,
            next_active=command.active,
            existing_upgrade_policy=existing_upgrade_policy,
            next_upgrade_policy=resolved_upgrade_policy,
            active_cycle=previous_aggregate.active_cycle,
            next_config_fingerprint=next_config_fingerprint,
        )
        aggregate = await self.store.save_subscription(provisional.model_copy(update={"clear_completion_snapshot": should_clear_snapshot}))
        change = self._build_change(previous, aggregate.state, aggregate.view, config=self._build_config_view(aggregate), ended_cycle=bool(previous and previous.active and not command.active))
        await self._dispatch_change(change)
        return change

    async def set_subscription_state(self, target: MediaTarget, command: SetSubscriptionStateCommand) -> SubscriptionChange:
        previous_aggregate = await self.store.load_current(target)
        previous = previous_aggregate.state
        next_media = await self._resolve_next_media(
            target,
            previous,
            command.active or command.followed,
            provided=command.media,
        )
        resolved_upgrade_policy = self.normalize_upgrade_policy_for_media(target.media_id, command.upgrade_policy)
        settings = previous_aggregate.settings
        if command.active:
            effective_config = await subscription_download_config_service.resolve_effective_config(
                target.media_id,
                target.media_id.media_type,
                season_number=target.season_number,
            )
            await self._validate_directory_id(effective_config.directory_id)
        mutation = SubscriptionMutation(
            target=target,
            sub_id=previous.sub_id if previous else None,
            media=next_media,
            active=command.active,
            followed=command.followed,
            subscription_mode=command.subscription_mode,
            upgrade_policy=resolved_upgrade_policy,
            target_filters=command.target_filters,
            target_filter_config_id=command.target_filter_config_id,
            directory_id=settings.directory_id if settings else None,
            filter_config_id=settings.filter_config_id if settings else None,
            quality_profile_id=settings.quality_profile_id if settings else None,
            filters=settings.filters if settings else None,
            sites=settings.sites if settings else None,
            unmatched_rules=list(settings.unmatched_rules if settings else []),
            follow_reminded_air_date=settings.follow_reminded_air_date if settings else None,
            follow_reminded_digital_release_date=settings.follow_reminded_digital_release_date if settings else None,
            follow_reminded_physical_release_date=settings.follow_reminded_physical_release_date if settings else None,
            follow_reminded_at=settings.follow_reminded_at if settings else None,
            follow_reminded_digital_release_at=settings.follow_reminded_digital_release_at if settings else None,
            follow_reminded_physical_release_at=settings.follow_reminded_physical_release_at if settings else None,
        )
        aggregate = await self.store.save_subscription(mutation.model_copy(update={
            "clear_completion_snapshot": bool(previous and ((not previous.active and command.active) or (not previous.upgrade_policy and resolved_upgrade_policy)))
        }))
        change = self._build_change(previous, aggregate.state, aggregate.view)
        if command.emit_events:
            await self._dispatch_change(change)
        return change

    async def end_subscription(self, target: MediaTarget, command: EndSubscriptionCommand) -> SubscriptionChange:
        previous_aggregate = await self.store.load_current(target)
        previous = previous_aggregate.state
        aggregate = await self.store.end_subscription(
            EndSubscriptionMutation(
                target=target,
                sub_id=command.sub_id,
                trigger=command.trigger,
                reason=command.reason,
            )
        )
        events = []
        if previous and previous.active and aggregate.state and not aggregate.state.active:
            events.append(
                SubscriptionLifecycleEventIntent(
                    type=SubscriptionLifecycleEventType.SUBSCRIPTION_ENDED,
                    trigger=command.trigger,
                    reason=command.reason,
                )
            )
        change = SubscriptionChange(previous=previous, current=aggregate.state, view=aggregate.view, events=events)
        await self._dispatch_change(change)
        return change

    async def delete_subscription(self, target: MediaTarget) -> SubscriptionChange:
        previous_aggregate = await self.store.load_current(target)
        previous = previous_aggregate.state
        mutation = SubscriptionMutation(
            target=target,
            sub_id=previous.sub_id if previous else None,
            media=previous.media if previous else None,
            active=False,
            followed=False,
            subscription_mode=default_subscription_mode_for_media(target.media_id),
            upgrade_policy=None,
            target_filters=None,
            target_filter_config_id=None,
        )
        aggregate = await self.store.save_subscription(mutation)
        change = self._build_change(previous, aggregate.state, aggregate.view, ended_cycle=bool(previous and previous.active))
        await self._dispatch_change(change)
        return change

    async def patch_settings_by_sub_id(self, sub_id: str, patch: MediaSubscriptionStatePatch) -> MediaSubscriptionState | None:
        aggregate = await self.store.load_by_sub_id(sub_id)
        if aggregate is None or aggregate.state is None:
            return None
        state = aggregate.state
        settings = aggregate.settings
        mutation = SubscriptionMutation(
            target=aggregate.target,
            sub_id=sub_id,
            media=patch.media if "media" in patch.model_fields_set else state.media,
            active=state.active,
            followed=patch.followed if "followed" in patch.model_fields_set and patch.followed is not None else state.followed,
            subscription_mode=patch.subscription_mode if "subscription_mode" in patch.model_fields_set and patch.subscription_mode is not None else state.subscription_mode,
            upgrade_policy=patch.upgrade_policy if "upgrade_policy" in patch.model_fields_set else state.upgrade_policy,
            target_filters=patch.target_filters if "target_filters" in patch.model_fields_set else state.target_filters,
            target_filter_config_id=patch.target_filter_config_id if "target_filter_config_id" in patch.model_fields_set else state.target_filter_config_id,
            directory_id=settings.directory_id if settings else None,
            filter_config_id=settings.filter_config_id if settings else None,
            quality_profile_id=settings.quality_profile_id if settings else None,
            filters=settings.filters if settings else None,
            sites=settings.sites if settings else None,
            unmatched_rules=list(settings.unmatched_rules if settings else []),
            follow_reminded_air_date=patch.follow_reminded_air_date if "follow_reminded_air_date" in patch.model_fields_set else state.follow_reminded_air_date,
            follow_reminded_digital_release_date=patch.follow_reminded_digital_release_date if "follow_reminded_digital_release_date" in patch.model_fields_set else state.follow_reminded_digital_release_date,
            follow_reminded_physical_release_date=patch.follow_reminded_physical_release_date if "follow_reminded_physical_release_date" in patch.model_fields_set else state.follow_reminded_physical_release_date,
            follow_reminded_at=patch.follow_reminded_at if "follow_reminded_at" in patch.model_fields_set else state.follow_reminded_at,
            follow_reminded_digital_release_at=patch.follow_reminded_digital_release_at if "follow_reminded_digital_release_at" in patch.model_fields_set else state.follow_reminded_digital_release_at,
            follow_reminded_physical_release_at=patch.follow_reminded_physical_release_at if "follow_reminded_physical_release_at" in patch.model_fields_set else state.follow_reminded_physical_release_at,
        )
        next_aggregate = await self.store.save_subscription(mutation)
        return next_aggregate.state

    async def _resolve_next_media(
        self,
        target: MediaTarget,
        previous: MediaSubscriptionState | None,
        requires_media: bool,
        *,
        provided: MediaExecutionSnapshot | None = None,
    ) -> MediaExecutionSnapshot | None:
        next_media = provided if provided is not None else (previous.media if previous else None)
        if requires_media:
            if next_media is None:
                next_media = await media_service.resolve_execution_snapshot(
                    target.media_id,
                    season_number=target.season_number,
                    require_tv_season=True,
                )
        if next_media is not None:
            self.validate_media_snapshot_target(next_media, target.media_id, target.season_number)
        return next_media

    async def _validate_activation_directory(self, target: MediaTarget, directory_id: str | None) -> None:
        if directory_id:
            await self._validate_directory_id(directory_id)
            return
        default_directory = subscription_download_config_service.get_default_directory(target.media_id.media_type)
        await self._validate_directory_id(default_directory.id if default_directory else None)

    @staticmethod
    async def _validate_directory_id(directory_id: str | None) -> None:
        try:
            directory_service.validate_subscription_directory(directory_id)
        except ConfigurationException as exc:
            raise DownloadException(
                "backendErrors.subscriptionCommandFailed",
                params={"reason_key": exc.message_key, "reason_params": exc.params},
            ) from exc

    @staticmethod
    def _mutation_fingerprint(mutation: SubscriptionMutation) -> str:
        from app.schemas.domain.media_subscription_settings import MediaSubscriptionSettings

        return MediaSubscriptionSettings(
            sub_id=mutation.sub_id or "pending",
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
        ).compute_config_fingerprint()

    @staticmethod
    def _build_config_view(aggregate) -> MediaDownloadConfigView:
        settings = aggregate.settings
        target = aggregate.target
        return MediaDownloadConfigView(
            sub_id=settings.sub_id if settings else None,
            media_id=target.media_id,
            season_number=settings.season_number if settings else target.season_number,
            directory_id=settings.directory_id if settings else None,
            filter_config_id=settings.filter_config_id if settings else None,
            quality_profile_id=settings.quality_profile_id if settings else None,
            filters=settings.filters if settings else None,
            sites=settings.sites if settings else None,
            unmatched_rules=list(settings.unmatched_rules) if settings else [],
        )

    @staticmethod
    def _build_change(
        previous: MediaSubscriptionState | None,
        current: MediaSubscriptionState | None,
        view,
        *,
        config: MediaDownloadConfigView | None = None,
        ended_cycle: bool = False,
    ) -> SubscriptionChange:
        events: list[SubscriptionLifecycleEventIntent] = []
        previous_active = bool(previous.active) if previous else False
        previous_followed = bool(previous.followed) if previous else False
        current_active = bool(current.active) if current else False
        current_followed = bool(current.followed) if current else False
        if ended_cycle and previous_active:
            events.append(
                SubscriptionLifecycleEventIntent(
                    type=SubscriptionLifecycleEventType.SUBSCRIPTION_ENDED,
                    trigger=SubscriptionEndTrigger.MANUAL,
                    reason=SubscriptionEndReason.MANUAL,
                )
            )
        elif previous_active != current_active:
            events.append(
                SubscriptionLifecycleEventIntent(
                    type=SubscriptionLifecycleEventType.SUBSCRIPTION_ENABLED if current_active else SubscriptionLifecycleEventType.SUBSCRIPTION_DISABLED
                )
            )
        if previous_followed != current_followed:
            events.append(
                SubscriptionLifecycleEventIntent(
                    type=SubscriptionLifecycleEventType.FOLLOW_ENABLED if current_followed else SubscriptionLifecycleEventType.FOLLOW_DISABLED
                )
            )
        return SubscriptionChange(
            previous=previous,
            current=current,
            view=view,
            config=config,
            events=events,
            profile_activation_needed=bool(current and (current.active or current.followed)),
        )

    async def _dispatch_change(self, change: SubscriptionChange) -> None:
        for intent in change.events:
            await self._emit_event(change, intent)
        if change.profile_activation_needed:
            await self._ensure_active_profile(change.current)

    @staticmethod
    async def _ensure_active_profile(state: MediaSubscriptionState | None) -> None:
        if state is None or not (state.active or state.followed):
            return
        try:
            await media_service.activate_existing_profile(state.media_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Subscription profile activation failed: media=%s error=%s", state.media_id, exc)

    async def _emit_event(self, change: SubscriptionChange, intent: SubscriptionLifecycleEventIntent) -> None:
        current = change.current or change.previous
        if current is None:
            return
        media = await self._resolve_event_media(current)
        if media is None:
            logger.warning("Skip subscription lifecycle event because media snapshot is missing: media=%s", current.media_id)
            return
        entities = [
            EventEntityRef(type="subscription", id=current.sub_id),
            EventEntityRef(type="media", id=str(current.media_id)),
        ]
        if intent.type == SubscriptionLifecycleEventType.SUBSCRIPTION_ENDED:
            reason = intent.reason or SubscriptionEndReason.MANUAL
            event_type = {
                SubscriptionEndReason.MANUAL: EventTypes.SUBSCRIPTION_ENDED_MANUAL,
                SubscriptionEndReason.MOVIE_LIBRARY_COMPLETED: EventTypes.SUBSCRIPTION_ENDED_MOVIE_COMPLETED,
                SubscriptionEndReason.MOVIE_DOWNLOADING_COMPLETED: EventTypes.SUBSCRIPTION_ENDED_MOVIE_DOWNLOADING_COMPLETED,
                SubscriptionEndReason.MOVIE_TARGET_COMPLETED: EventTypes.SUBSCRIPTION_ENDED_MOVIE_TARGET_COMPLETED,
                SubscriptionEndReason.TV_COMPLETED: EventTypes.SUBSCRIPTION_ENDED_TV_COMPLETED,
                SubscriptionEndReason.TV_UPGRADE_COMPLETED: EventTypes.SUBSCRIPTION_ENDED_TV_UPGRADE_COMPLETED,
                SubscriptionEndReason.TV_TARGET_COMPLETED: EventTypes.SUBSCRIPTION_ENDED_TV_TARGET_COMPLETED,
            }[reason]
            actor = EventActor.user if intent.trigger == SubscriptionEndTrigger.MANUAL else EventActor.system
        elif intent.type == SubscriptionLifecycleEventType.SUBSCRIPTION_ENABLED:
            event_type = EventTypes.SUBSCRIPTION_ENABLED
            actor = EventActor.user
        elif intent.type == SubscriptionLifecycleEventType.SUBSCRIPTION_DISABLED:
            event_type = EventTypes.SUBSCRIPTION_DISABLED
            actor = EventActor.user
        elif intent.type == SubscriptionLifecycleEventType.FOLLOW_ENABLED:
            event_type = EventTypes.FOLLOW_ENABLED
            actor = EventActor.user
        else:
            event_type = EventTypes.FOLLOW_DISABLED
            actor = EventActor.user
        event_service.emit_media(
            MediaEventCreate(
                type=event_type,
                media=media,
                subscription_id=current.sub_id,
                actor=actor,
                source=EventSource.base,
                entities=entities,
            )
        )

    @staticmethod
    async def _resolve_event_media(current: MediaSubscriptionState):
        if current.media is not None:
            return current.media
        return await media_service.simple_info(current.media_id)


subscription_command_service = SubscriptionCommandService()
