from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.command import CommandCreateRequest, CommandInitiator
from app.schemas.domain.download import DownloadTaskCreateInput
from app.schemas.domain.event import EventActor, EventEntityRef, EventLevel, EventSource, MediaEventCreate
from app.schemas.domain.event_meta import SubscriptionRunCompletedEventMeta
from app.schemas.domain.media import MediaTarget
from app.schemas.domain.media_subscription_state import MediaSubscriptionState, SubscriptionEndTrigger
from app.schemas.domain.resource_search import MediaSearchQuery, Resource
from app.schemas.domain.subscription import Subscription
from app.schemas.domain.subscription import SubscriptionSearchWarning, SubscriptionSearchWarningType
from app.schemas.domain.subscription_run_result import SubscriptionRunResponse
from app.schemas.exception import SubscriptionNotFoundException
from app.schemas.exception.base import AppException
from app.services.application.commands.service import command_service
from app.schemas.runtime.subscription_runtime import (
    SubscriptionPlanningStatus,
    SubscriptionRunOutcome,
    SubscriptionRunOutcomeStatus,
    SubscriptionRunPlan,
)
from app.schemas.runtime.subscription_lifecycle import EndSubscriptionCommand, ResourceRunSelection, SubscriptionRunRecord
from app.services.audit.event_service import event_service
from app.services.domain.media import media_service
from app.services.domain.subscription.download_config_service import subscription_download_config_service
from app.services.domain.resource.filtering import compute_preference_score
from app.services.domain.resource.selection import ResourceSelectionPlan, partition_search_results, resource_sort_rank, select_resources
from app.services.domain.subscription.command_service import subscription_command_service
from app.services.domain.subscription.completion_checker import subscription_completion_checker
from app.services.domain.subscription.query_service import subscription_query_service
from app.services.domain.subscription.resource_run_plan_service import resource_run_plan_service
from app.services.domain.subscription.store import subscription_store
from app.services.domain.subscription.upgrade_baseline_service import subscription_upgrade_baseline_service
from app.services.application.workflows.resource_search import resource_search_service
from app.services.platform.domain_lock_service import domain_lock_service

logger = logging.getLogger("app.services.subscription.run")


class SubscriptionRunApplicationService:
    async def run_one_by_media_id(self, media_id, season_number: int | None = None) -> SubscriptionRunResponse:
        state = await subscription_query_service.get_state(MediaTarget(media_id=media_id, season_number=season_number))
        if not state or not state.active:
            raise SubscriptionNotFoundException()
        sub = await self._build_runtime_subscription(state)
        return await self.run_one(sub)

    async def run_one_by_sub_id(self, sub_id: str) -> SubscriptionRunResponse:
        state = await subscription_query_service.get_state_by_sub_id(sub_id)
        if not state or not state.active:
            raise SubscriptionNotFoundException()
        sub = await self._build_runtime_subscription(state)
        return await self.run_one(sub)

    async def run_one(self, sub: Subscription) -> SubscriptionRunResponse:
        async with self._acquire_media_execution_flow(sub.media_id, reason=f"subscription:{sub.sub_id}") as acquired:
            if not acquired:
                logger.info("Subscription run skipped because the media resource pipeline is busy: media=%s sub=%s", sub.media_id, sub.sub_id)
                return SubscriptionRunOutcome(status=SubscriptionRunOutcomeStatus.BUSY).response

            runtime_sub = await self._refresh_runtime_media_snapshot(sub)
            resource_run_plan_service.validate_runtime_subscription(runtime_sub)
            checked_at = time.time()
            outcome = await self._run_one_outcome(runtime_sub)
            self._emit_run_events(runtime_sub, outcome)
            upgrade_snapshot = await subscription_upgrade_baseline_service.resolve_for_subscription(runtime_sub)

            await subscription_store.save_run_record(
                SubscriptionRunRecord(
                    sub_id=runtime_sub.sub_id,
                    target=MediaTarget(media_id=runtime_sub.media_id, season_number=runtime_sub.season_number),
                    checked_at=checked_at,
                    warnings=outcome.warnings,
                    upgrade_snapshot=upgrade_snapshot,
                )
            )
            completion = await subscription_completion_checker.check(runtime_sub)
            if completion:
                await subscription_command_service.end_subscription(
                    completion.target,
                    EndSubscriptionCommand(
                        sub_id=completion.sub_id,
                        trigger=SubscriptionEndTrigger.SYSTEM,
                        reason=completion.reason,
                    ),
                )
            return outcome.response

    async def _run_one_outcome(self, runtime_sub: Subscription) -> SubscriptionRunOutcome:
        planning_result = await resource_run_plan_service.build_subscription_plan(runtime_sub)
        if planning_result.status == SubscriptionPlanningStatus.INVALID:
            return SubscriptionRunOutcome(
                status=SubscriptionRunOutcomeStatus.INVALID,
                message_key=planning_result.message_key,
                message_params=planning_result.message_params,
                correlation_id=planning_result.correlation_id,
            )
        if planning_result.status == SubscriptionPlanningStatus.SATISFIED:
            return SubscriptionRunOutcome(
                status=SubscriptionRunOutcomeStatus.SATISFIED,
                message_key=planning_result.message_key,
                message_params=planning_result.message_params,
                correlation_id=planning_result.correlation_id,
            )
        plan = planning_result.plan
        if plan is None:
            return SubscriptionRunOutcome(
                status=SubscriptionRunOutcomeStatus.INVALID,
                message_key="subscriptionRunMessages.planMissing",
                correlation_id=planning_result.correlation_id,
            )

        selection = await self._search_and_select_resources(subscription=runtime_sub, plan=plan)
        if selection.checked <= 0:
            logger.debug("Subscription run produced no search results: media=%s sub=%s", plan.media.media_id, runtime_sub.sub_id)
            return SubscriptionRunOutcome(
                status=SubscriptionRunOutcomeStatus.NO_RESOURCE,
                response=SubscriptionRunResponse(),
                plan=plan,
                correlation_id=plan.correlation_id,
            )

        if selection.matched <= 0:
            return SubscriptionRunOutcome(
                status=SubscriptionRunOutcomeStatus.NO_MATCH,
                response=SubscriptionRunResponse(checked=selection.checked),
                plan=plan,
                correlation_id=plan.correlation_id,
                warnings=selection.warnings,
            )

        if not selection.selected:
            logger.info(
                "Subscription run completed without queued downloads: media=%s sub=%s checked=%d matched=%d targets=%s",
                plan.media.media_id,
                runtime_sub.sub_id,
                selection.checked,
                selection.matched,
                sorted(plan.target_episodes),
            )
            return SubscriptionRunOutcome(
                status=SubscriptionRunOutcomeStatus.NO_SELECTION,
                response=SubscriptionRunResponse(checked=selection.checked),
                plan=plan,
                correlation_id=plan.correlation_id,
                warnings=selection.warnings,
            )

        added = await self._queue_selected_resources(runtime_sub, plan, selection.selected)
        logger.info(
            "Subscription run completed: media=%s sub=%s checked=%d matched=%d selected=%d queued=%d",
            plan.media.media_id,
            runtime_sub.sub_id,
            selection.checked,
            selection.matched,
            len(selection.selected),
            added,
        )
        if added <= 0:
            return SubscriptionRunOutcome(
                status=SubscriptionRunOutcomeStatus.QUEUE_FAILED,
                response=SubscriptionRunResponse(checked=selection.matched),
                plan=plan,
                message_key="subscriptionRunMessages.queueFailed",
                correlation_id=plan.correlation_id,
                warnings=selection.warnings,
            )
        return SubscriptionRunOutcome(
            status=SubscriptionRunOutcomeStatus.QUEUED,
            response=SubscriptionRunResponse(checked=selection.matched, added=added),
            plan=plan,
            correlation_id=plan.correlation_id,
            warnings=selection.warnings,
        )

    async def _search_and_select_resources(
        self,
        *,
        subscription: Subscription,
        plan: SubscriptionRunPlan,
    ) -> ResourceRunSelection:
        search_results = await resource_search_service.search_media(
            MediaSearchQuery(
                media=plan.media,
                indexers=plan.sites,
                unmatched_rules=list(subscription.unmatched_rules),
                use_cache=False,
            )
        )
        if not search_results:
            logger.info("Subscription run found no resources: media=%s sub=%s", subscription.media_id, subscription.sub_id)
            return ResourceRunSelection(checked=0, matched=0)

        selection_plan = ResourceSelectionPlan(
            media_id=plan.media.media_id,
            season_number=plan.season_number,
            episode_mode=plan.episode_mode,
            filters=plan.filters,
            quality_profile=plan.quality_profile,
            target_episodes=plan.target_episodes,
            required_scores=dict(plan.required_scores or {}),
        )
        standard_results, unmatched_results, has_any_id_match = partition_search_results(
            selection_plan,
            search_results,
            unmatched_rules=subscription.unmatched_rules,
        )
        warnings = self._build_search_warnings(
            plan=plan,
            standard_results=standard_results,
            unmatched_results=unmatched_results,
            has_any_id_match=has_any_id_match,
        )
        if not standard_results:
            return ResourceRunSelection(checked=len(search_results), matched=0, warnings=warnings)

        selected = await select_resources(
            standard_results,
            episodes=plan.target_episodes,
            filters=plan.filters,
            quality_profile=plan.quality_profile,
            required_scores=plan.required_scores,
            episode_mode=plan.episode_mode,
            existing_disc_numbers=plan.existing_disc_numbers,
        )
        return ResourceRunSelection(
            checked=len(search_results),
            matched=len(standard_results),
            warnings=warnings,
            selected=list(selected or []),
        )

    def _build_search_warnings(
        self,
        *,
        plan: SubscriptionRunPlan,
        standard_results: list[Resource],
        unmatched_results: list[Resource],
        has_any_id_match: bool,
    ) -> list[SubscriptionSearchWarning]:
        warnings: list[SubscriptionSearchWarning] = []
        now = time.time()
        if (standard_results or unmatched_results) and not has_any_id_match:
            warnings.append(
                SubscriptionSearchWarning(
                    type=SubscriptionSearchWarningType.NO_ID_MATCH,
                    message_key="subscriptionWarnings.noIdMatchTitleOnly",
                    created_at=now,
                )
            )
        if standard_results and unmatched_results:
            best_standard_score = max(compute_preference_score(item, plan.quality_profile)[0] for item in standard_results)
            best_unmatched_score = max(compute_preference_score(item, plan.quality_profile)[0] for item in unmatched_results)
            best_standard_rank = max(resource_sort_rank(item, plan.quality_profile) for item in standard_results)
            best_unmatched_rank = max(resource_sort_rank(item, plan.quality_profile) for item in unmatched_results)
            if best_unmatched_rank > best_standard_rank or (
                best_unmatched_rank == best_standard_rank and best_unmatched_score > best_standard_score
            ):
                warnings.append(
                    SubscriptionSearchWarning(
                        type=SubscriptionSearchWarningType.HIGHER_QUALITY_UNMATCHED,
                        message_key="subscriptionWarnings.higherQualityUnmatched",
                        created_at=now,
                    )
                )
        return warnings

    async def _queue_selected_resources(self, runtime_sub: Subscription, plan: SubscriptionRunPlan, selected) -> int:
        added = 0
        for payload, selected_files, resource in selected:
            try:
                await command_service.create_command(
                    CommandCreateRequest.from_task_create_input(
                        DownloadTaskCreateInput(
                            media=plan.media,
                            directory_id=runtime_sub.directory_id,
                            result_id=resource.resources.result_id,
                            selected_files=selected_files,
                        ),
                        initiator=CommandInitiator.SYSTEM,
                    )
                )
            except AppException as exc:
                logger.warning(
                    "Failed to queue subscription download: media=%s sub=%s resource=%s error=%s",
                    plan.media.media_id,
                    runtime_sub.sub_id,
                    resource.resources.title,
                    exc,
                )
                continue
            logger.debug(
                "Queued subscription resource: media=%s sub=%s resource=%s size=%d episodes=%s files=%d",
                plan.media.media_id,
                runtime_sub.sub_id,
                payload.metadata.name,
                payload.metadata.size,
                sorted(payload.metadata.get_episodes()),
                len(selected_files),
            )
            added += 1
        return added

    def _emit_run_events(self, runtime_sub: Subscription, outcome: SubscriptionRunOutcome) -> None:
        if outcome.should_emit_failed:
            self._emit_run_failed(runtime_sub, outcome)
        if outcome.should_emit_completed:
            self._emit_run_completed(runtime_sub, outcome)

    def _emit_run_failed(self, runtime_sub: Subscription, outcome: SubscriptionRunOutcome) -> None:
        correlation_id = outcome.correlation_id or (outcome.plan.correlation_id if outcome.plan else runtime_sub.sub_id)
        event_service.emit_media(
            MediaEventCreate(
                type=EventTypes.SUBSCRIPTION_RUN_FAILED,
                level=EventLevel.error,
                message_params={"reason_key": outcome.message_key or "subscriptionRunMessages.failed"},
                media=outcome.plan.media if outcome.plan else runtime_sub.media,
                subscription_id=runtime_sub.sub_id,
                actor=EventActor.system,
                source=EventSource.base,
                entities=[
                    EventEntityRef(type="subscription", id=runtime_sub.sub_id),
                    EventEntityRef(type="job_run", id=correlation_id),
                ],
                correlation_id=correlation_id,
            ),
        )

    def _emit_run_completed(self, runtime_sub: Subscription, outcome: SubscriptionRunOutcome) -> None:
        if outcome.plan is None:
            return
        event_service.emit_media(
            MediaEventCreate(
                type=EventTypes.SUBSCRIPTION_RUN_COMPLETED,
                level=EventLevel.info,
                media=outcome.plan.media,
                subscription_id=runtime_sub.sub_id,
                actor=EventActor.system,
                source=EventSource.base,
                entities=[
                    EventEntityRef(type="subscription", id=runtime_sub.sub_id),
                    EventEntityRef(type="job_run", id=outcome.plan.correlation_id),
                ],
                correlation_id=outcome.plan.correlation_id,
            ),
            meta=SubscriptionRunCompletedEventMeta(checked=outcome.response.checked, added=outcome.response.added),
        )

    async def run_all(self) -> SubscriptionRunResponse:
        async with self._acquire_subscription_sweep() as acquired:
            if not acquired:
                logger.info("Subscription sweep skipped because the previous sweep is still running")
                return SubscriptionRunResponse()

            states = [state for state in await subscription_query_service.list_states() if state.active]
            total_checked = 0
            total_added = 0
            for state in states:
                try:
                    sub = await self._build_runtime_subscription(state)
                    res = await self.run_one(sub)
                    total_checked += res.checked
                    total_added += res.added
                except (AppException, ValueError) as exc:
                    logger.warning("Subscription run failed for %s: %s", state.media_id, exc)
            logger.info("Subscription sweep completed: subscriptions=%d checked=%d queued=%d", len(states), total_checked, total_added)
            return SubscriptionRunResponse(checked=total_checked, added=total_added)

    async def _build_runtime_subscription(self, state: MediaSubscriptionState) -> Subscription:
        config = await subscription_download_config_service.resolve_effective_config(
            state.media_id,
            state.media_id.media_type,
            season_number=state.season_number,
        )
        return subscription_query_service.compose_runtime_subscription(state, config)

    async def _refresh_runtime_media_snapshot(self, sub: Subscription) -> Subscription:
        try:
            media = await media_service.resolve_execution_snapshot(
                sub.media_id,
                season_number=sub.season_number,
                require_tv_season=True,
                include_schedule_snapshot=True,
            )
        except AppException:
            logger.warning("Subscription run uses stored media snapshot because current profile is missing: media=%s sub=%s", sub.media_id, sub.sub_id)
            return sub
        return sub.model_copy(update={"media": media})

    @asynccontextmanager
    async def _acquire_media_execution_flow(self, media_id, *, reason: str) -> AsyncIterator[bool]:
        _ = reason
        async with domain_lock_service.acquire_media_acquire(media_id) as acquired:
            yield acquired

    @asynccontextmanager
    async def _acquire_subscription_sweep(self) -> AsyncIterator[bool]:
        async with domain_lock_service.acquire_scheduler_job("subscription_sweep") as acquired:
            yield acquired


subscription_run_application_service = SubscriptionRunApplicationService()
