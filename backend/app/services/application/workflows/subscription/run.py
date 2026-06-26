from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime

from app.schemas.domain.command import CommandCreateRequest, CommandInitiator
from app.schemas.domain.download import DownloadTaskCreateInput
from app.schemas.domain.media import MediaTarget
from app.schemas.domain.media_subscription_state import MediaSubscriptionState, SubscriptionEndTrigger
from app.schemas.domain.resource_search import MediaSearchQuery, Resource, ResourceSearchResult
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
from app.services.config.settings_service import settings_service
from app.services.domain.resource.parser import resource_parser
from app.services.integration.indexer.site_scope import split_scoped_site_id
from app.services.platform.domain_lock_service import domain_lock_service

logger = logging.getLogger("app.services.subscription.run")
RSS_WITH_SEARCH_BACKFILL_MODE = "rss_with_search_backfill"


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

    async def run_one(
        self,
        sub: Subscription,
        *,
        recent_candidates: list[ResourceSearchResult] | None = None,
        active_search: bool | None = None,
    ) -> SubscriptionRunResponse:
        async with self._acquire_media_execution_flow(sub.media_id, reason=f"subscription:{sub.sub_id}") as acquired:
            if not acquired:
                logger.info("Subscription run skipped because the media resource pipeline is busy: media=%s sub=%s", sub.media_id, sub.sub_id)
                return SubscriptionRunOutcome(status=SubscriptionRunOutcomeStatus.BUSY).response

            runtime_sub = await self._refresh_runtime_media_snapshot(sub)
            resource_run_plan_service.validate_runtime_subscription(runtime_sub)
            checked_at = time.time()
            outcome = await self._run_one_outcome(runtime_sub, recent_candidates=recent_candidates)
            upgrade_snapshot = await subscription_upgrade_baseline_service.resolve_for_subscription(runtime_sub)
            searched_at = checked_at if self._records_active_search(recent_candidates, active_search) else None

            await subscription_store.save_run_record(
                SubscriptionRunRecord(
                    sub_id=runtime_sub.sub_id,
                    target=MediaTarget(media_id=runtime_sub.media_id, season_number=runtime_sub.season_number),
                    checked_at=checked_at,
                    searched_at=searched_at,
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

    async def _run_one_outcome(
        self,
        runtime_sub: Subscription,
        *,
        recent_candidates: list[ResourceSearchResult] | None = None,
    ) -> SubscriptionRunOutcome:
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

        selection = await self._search_and_select_resources(
            subscription=runtime_sub,
            plan=plan,
            recent_candidates=recent_candidates,
        )
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
        recent_candidates: list[ResourceSearchResult] | None = None,
    ) -> ResourceRunSelection:
        query = MediaSearchQuery(
            media=plan.media,
            indexers=plan.sites,
            unmatched_rules=list(subscription.unmatched_rules),
            use_cache=False,
        )
        search_results = (
            await resource_search_service.search_media(query)
            if recent_candidates is None
            else self._filter_recent_candidates(
                query=query,
                plan=plan,
                candidates=recent_candidates,
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

    def _filter_recent_candidates(
        self,
        *,
        query: MediaSearchQuery,
        plan: SubscriptionRunPlan,
        candidates: list[ResourceSearchResult],
    ) -> list[ResourceSearchResult]:
        site_filtered = [result for result in candidates if self._candidate_matches_plan_sites(result, plan.sites)]
        matched_candidates = [result for result in site_filtered if self._recent_candidate_matches_media(result, query)]
        merged_results = resource_search_service.policy.merge_results(matched_candidates)
        media_filtered = resource_search_service.policy.filter_media_results(merged_results, query)
        season_filtered = resource_search_service.policy.filter_results_for_active_season(media_filtered, query)
        return resource_search_service.cache_results(season_filtered)

    def _candidate_matches_plan_sites(self, result: ResourceSearchResult, sites: list[str] | None) -> bool:
        if not sites:
            return True
        result_indexer_id, result_site_id = split_scoped_site_id(result.site)
        for site in sites:
            requested_indexer_id, requested_site_id = split_scoped_site_id(site)
            if site == result.site:
                return True
            if requested_indexer_id and requested_indexer_id == result_indexer_id and requested_site_id == result_site_id:
                return True
            if not requested_indexer_id and requested_site_id == result_site_id:
                return True
        return False

    def _recent_candidate_matches_media(self, result: ResourceSearchResult, query: MediaSearchQuery) -> bool:
        expected_douban_id = resource_search_service.policy.expected_douban_id(query)
        expected_imdb_id = resource_search_service.policy.normalize_external_id(query.imdbid)
        result_douban_id = resource_search_service.policy.normalize_external_id(result.source_doubanid)
        result_imdb_id = resource_search_service.policy.normalize_external_id(result.source_imdbid)
        if result_douban_id and expected_douban_id and result_douban_id == expected_douban_id:
            return True
        if result_imdb_id and expected_imdb_id and result_imdb_id == expected_imdb_id:
            return True
        return self._recent_title_matches(query.title, result.title)

    @staticmethod
    def _recent_title_tokens(value: str | None) -> list[str]:
        return re.findall(r"[^\W_]+", str(value or "").lower(), flags=re.UNICODE)

    @staticmethod
    def _recent_resource_title(value: str | None) -> str | None:
        title = str(value or "").strip()
        if not title:
            return None
        attrs = resource_parser.parse(title)
        if attrs.groups:
            return re.sub(r"^\s*[\[【][^\[\]【】]+?[\]】]\s*", "", title, count=1)
        return title

    def _recent_title_matches(self, media_title: str | None, resource_title: str | None) -> bool:
        media_tokens = self._recent_title_tokens(media_title)
        resource_tokens = self._recent_title_tokens(self._recent_resource_title(resource_title))
        if not media_tokens or not resource_tokens:
            return False
        if len(media_tokens) == 1:
            return resource_tokens[:1] == media_tokens
        window_size = len(media_tokens)
        return any(
            resource_tokens[index:index + window_size] == media_tokens
            for index in range(0, len(resource_tokens) - window_size + 1)
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

    async def run_all(self) -> SubscriptionRunResponse:
        async with self._acquire_subscription_sweep() as acquired:
            if not acquired:
                logger.info("Subscription sweep skipped because the previous sweep is still running")
                return SubscriptionRunResponse()

            scheduler_config = settings_service.get_scheduler_config()
            if scheduler_config.subscription_resource_discovery_mode == RSS_WITH_SEARCH_BACKFILL_MODE:
                return await self._run_all_with_recent_feed(scheduler_config)
            return await self._run_all_with_search(scheduler_config)

    async def _run_all_with_search(self, scheduler_config=None) -> SubscriptionRunResponse:
        states = [state for state in await subscription_query_service.list_states() if state.active]
        interval_seconds = (
            scheduler_config.subscription_search_interval_seconds
            if scheduler_config is not None
            else settings_service.get_scheduler_config().subscription_search_interval_seconds
        )
        max_search_count = (
            scheduler_config.subscription_search_max_per_sweep
            if scheduler_config is not None
            else settings_service.get_scheduler_config().subscription_search_max_per_sweep
        )
        due_states = [state for state in states if self._active_search_due(state, interval_seconds)]
        search_states = await self._select_active_search_states(due_states, max_search_count)
        total_checked = 0
        total_added = 0
        for state in search_states:
            try:
                sub = await self._build_runtime_subscription(state)
                res = await self.run_one(sub, active_search=True)
                total_checked += res.checked
                total_added += res.added
            except (AppException, ValueError) as exc:
                logger.warning("Subscription run failed for %s: %s", state.media_id, exc)
        logger.info(
            "Subscription sweep completed: subscriptions=%d search_due=%d search_run=%d checked=%d queued=%d",
            len(states),
            len(due_states),
            len(search_states),
            total_checked,
            total_added,
        )
        return SubscriptionRunResponse(checked=total_checked, added=total_added)

    async def _run_all_with_recent_feed(self, scheduler_config=None) -> SubscriptionRunResponse:
        states = [state for state in await subscription_query_service.list_states() if state.active]
        recent_candidates = await self._fetch_recent_candidates_for_sweep()
        interval_seconds = (
            scheduler_config.subscription_search_backfill_interval_seconds
            if scheduler_config is not None
            else settings_service.get_scheduler_config().subscription_search_backfill_interval_seconds
        )
        max_search_count = (
            scheduler_config.subscription_search_max_per_sweep
            if scheduler_config is not None
            else settings_service.get_scheduler_config().subscription_search_max_per_sweep
        )
        due_states = [state for state in states if self._active_search_due(state, interval_seconds)]
        search_states = await self._select_active_search_states(due_states, max_search_count)
        search_sub_ids = {state.sub_id for state in search_states}
        total_checked = 0
        total_added = 0
        for state in states:
            try:
                sub = await self._build_runtime_subscription(state)
                if state.sub_id in search_sub_ids:
                    res = await self.run_one(sub, active_search=True)
                else:
                    res = await self.run_one(sub, recent_candidates=recent_candidates, active_search=False)
                total_checked += res.checked
                total_added += res.added
            except (AppException, ValueError) as exc:
                logger.warning("Subscription RSS run failed for %s: %s", state.media_id, exc)
        logger.info(
            "Subscription RSS sweep completed: subscriptions=%d search_due=%d search_run=%d candidates=%d checked=%d queued=%d",
            len(states),
            len(due_states),
            len(search_states),
            len(recent_candidates),
            total_checked,
            total_added,
        )
        return SubscriptionRunResponse(checked=total_checked, added=total_added)

    def _active_search_due(self, state: MediaSubscriptionState, interval_seconds: int) -> bool:
        if state.last_search_at is None:
            return True
        return (time.time() - state.last_search_at) >= max(1, int(interval_seconds or 600))

    async def _select_active_search_states(
        self,
        states: list[MediaSubscriptionState],
        max_search_count: int,
    ) -> list[MediaSubscriptionState]:
        limit = max(1, int(max_search_count or 1))
        ordered_states = sorted(
            states,
            key=lambda state: (
                state.last_search_at if state.last_search_at is not None else 0,
                state.created_at,
                state.sub_id or "",
            ),
        )
        selected: list[MediaSubscriptionState] = []
        for state in ordered_states:
            if not await self._active_search_needed(state):
                continue
            selected.append(state)
            if len(selected) >= limit:
                break
        return selected

    async def _active_search_needed(self, state: MediaSubscriptionState) -> bool:
        if state.last_search_at is None:
            return True
        if state.media_id.media_type.value != "tv":
            return True
        if state.upgrade_policy and state.upgrade_policy.enabled:
            return True
        try:
            sub = await self._build_runtime_subscription(state)
            runtime_sub = await self._refresh_runtime_media_snapshot(sub)
            planning_result = await resource_run_plan_service.build_subscription_plan(runtime_sub)
        except (AppException, ValueError) as exc:
            logger.warning("Subscription active search readiness check failed for %s: %s", state.media_id, exc)
            return True
        if planning_result.status != SubscriptionPlanningStatus.SATISFIED:
            return True
        return not self._next_episode_air_date_in_future(runtime_sub.media.next_episode_to_air.air_date if runtime_sub.media.next_episode_to_air else None)

    @staticmethod
    def _next_episode_air_date_in_future(air_date: str | None) -> bool:
        if not air_date:
            return False
        try:
            parsed = datetime.fromisoformat(air_date[:10]).date()
        except ValueError:
            return False
        return parsed > date.today()

    @staticmethod
    def _records_active_search(
        recent_candidates: list[ResourceSearchResult] | None,
        active_search: bool | None,
    ) -> bool:
        if active_search is not None:
            return active_search
        return recent_candidates is None

    async def _fetch_recent_candidates_for_sweep(self) -> list[ResourceSearchResult]:
        contexts = await resource_search_service.indexer_gateway.list_search_contexts(None)
        enabled_contexts = [
            context
            for context in contexts
            if resource_search_service.indexer_gateway.is_context_enabled(context)
        ]
        if not enabled_contexts:
            return []
        recent_result = await resource_search_service.indexer_gateway.fetch_recent_contexts(enabled_contexts)
        settings_service.record_indexer_site_search_outcomes(recent_result.outcomes)
        if recent_result.failed:
            logger.warning("Subscription RSS sweep completed with indexer site failures")
        return recent_result.results

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
