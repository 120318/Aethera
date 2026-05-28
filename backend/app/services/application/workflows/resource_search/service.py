import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass

from app.schemas.domain.resource_search import MediaSearchQuery, ResourceSearchResult
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.schemas.runtime.indexer_runtime import IndexerSiteSearchOutcome
from app.schemas.runtime.indexer_runtime import IndexerSearchContext
from app.services.application.workflows.resource_search.cache import ResourceSearchCache
from app.services.config.settings_service import settings_service
from app.services.domain.resource.search_policy import ResourceSearchResultPolicy, resource_search_result_policy
from app.services.integration.indexer import IndexerGateway, IndexerSiteSearchResult

logger = logging.getLogger("app.services.application.workflows.resource_search")


@dataclass(frozen=True)
class _SiteSearchPlan:
    context: IndexerSearchContext
    modes: list[tuple[str, str]]
    query_scope: str
    media_type: MediaType | None
    season_number: int | None


class ResourceSearchService:
    def __init__(
        self,
        *,
        indexer_gateway: IndexerGateway | None = None,
        cache: ResourceSearchCache | None = None,
        policy: ResourceSearchResultPolicy | None = None,
    ) -> None:
        self.indexer_gateway = indexer_gateway or IndexerGateway()
        self.cache = cache or ResourceSearchCache()
        self.policy = policy or resource_search_result_policy

    async def search_media(self, query: MediaSearchQuery) -> list[ResourceSearchResult]:
        started_at = time.perf_counter()
        douban_id = self.policy.expected_douban_id(query)
        logger.debug(
            "Resource media search start: media_id=%s imdbid=%s douban_id=%s title=%s year=%s media_type=%s season_number=%s requested_sites=%s use_cache=%s",
            str(query.media_id),
            query.imdbid,
            douban_id,
            query.title,
            query.year,
            query.media_type.value if query.media_type else None,
            query.season_number,
            query.indexers,
            query.use_cache,
        )

        self.cache.refresh_ttls()
        contexts = await self.indexer_gateway.list_search_contexts(query.indexers)
        if not contexts:
            logger.warning("Resource media search skipped because no indexer clients are available")
            self.cache.cache_latest_media_results(
                query.media_id,
                [],
                query.season_number,
                search_duration_seconds=time.perf_counter() - started_at,
            )
            return []

        built_title_query = self._build_title_query(str(query.title or "").strip(), query) if query.title else ""
        all_results: list[ResourceSearchResult] = []
        searched_any_site = False
        had_site_failures = False
        cache_hits = 0
        cache_misses = 0
        skipped_sites = 0
        scheduled_site_count = 0
        mode_request_count = 0
        raw_result_count = 0
        ordered_entries: list[tuple[str, list[ResourceSearchResult] | None]] = []
        scheduled_plans: list[_SiteSearchPlan] = []

        contexts_by_indexer: dict[str, list[IndexerSearchContext]] = {}
        for context in contexts:
            contexts_by_indexer.setdefault(context.indexer_id, []).append(context)

        for indexer_id, indexer_contexts in contexts_by_indexer.items():
            compatible_contexts = self._filter_media_compatible_contexts(indexer_contexts, query)
            if not compatible_contexts:
                continue
            site_batches = self._build_site_batches(compatible_contexts, query, built_title_query, douban_id)

            for context in compatible_contexts:
                modes = site_batches[context.site.id] if context.site.id in site_batches else []
                query_scope = self._site_query_scope(modes)
                cached_results = self._read_site_cache(context, query, query_scope)
                if cached_results is not None:
                    cache_hits += 1
                    ordered_entries.append(("cached", cached_results))
                    continue
                cache_misses += 1
                if not self.indexer_gateway.is_context_enabled(context):
                    logger.debug(
                        "Resource media search skipping site refresh: client=%s site=%s reason=site_disabled",
                        context.indexer_id,
                        context.site.id,
                    )
                    skipped_sites += 1
                    ordered_entries.append(("skipped", []))
                    continue
                if not modes:
                    logger.debug(
                        "Resource media search skipping site refresh: client=%s site=%s reason=no_supported_search_mode",
                        context.indexer_id,
                        context.site.id,
                    )
                    skipped_sites += 1
                    ordered_entries.append(("skipped", []))
                    continue
                scheduled_site_count += 1
                mode_request_count += len(modes)
                scheduled_plans.append(
                    _SiteSearchPlan(
                        context=context,
                        modes=modes,
                        query_scope=query_scope,
                        media_type=query.media_type,
                        season_number=query.season_number,
                    )
                )
                ordered_entries.append(("scheduled", None))

        scheduled_results = await self._search_site_plans(scheduled_plans)
        scheduled_result_index = 0
        for entry_type, entry_results in ordered_entries:
            if entry_type != "scheduled":
                all_results.extend(entry_results or [])
                raw_result_count += len(entry_results or [])
                continue
            plan, search_result = scheduled_results[scheduled_result_index]
            scheduled_result_index += 1
            context = plan.context
            settings_service.record_indexer_site_search_outcomes(search_result.outcomes)
            searched_any_site = searched_any_site or search_result.searched
            had_site_failures = had_site_failures or search_result.failed
            if search_result.searched:
                if search_result.failed and not search_result.results:
                    self.cache.cache_media_search_error_for_site(
                        query.media_id,
                        context.indexer_id,
                        context.site.id,
                        context.cache_scope,
                        "site_search_failed",
                        query.season_number,
                        plan.query_scope,
                    )
                else:
                    self.cache.cache_media_results_for_site(
                        query.media_id,
                        context.indexer_id,
                        context.site.id,
                        context.cache_scope,
                        search_result.results,
                        query.season_number,
                        plan.query_scope,
                    )
            all_results.extend(search_result.results)
            raw_result_count += len(search_result.results)

        merged_results = self.policy.merge_results(all_results)
        filtered_results = self.policy.filter_media_results(merged_results, query)
        for result in filtered_results:
            logger.debug(
                "Resource media result final: media_id=%s site=%s title=%s matched_by_id=%s match_source=%s detail_url=%s",
                str(query.media_id),
                result.site,
                result.title,
                result.matched_by_id,
                self.policy.resolve_match_source(result, query),
                result.detail_url,
            )
        season_filtered_results = self.policy.filter_results_for_active_season(filtered_results, query)
        logger.debug(
            "Resource media search merged results: media_id=%s merged=%s filtered=%s season_filtered=%s",
            str(query.media_id),
            len(merged_results),
            len(filtered_results),
            len(season_filtered_results),
        )
        normalized_results = self.cache.normalize_results(season_filtered_results)
        search_duration_seconds = time.perf_counter() - started_at
        self.cache.cache_latest_media_results(
            query.media_id,
            normalized_results,
            query.season_number,
            search_duration_seconds=search_duration_seconds,
        )
        self._log_search_timing(
            started_at=started_at,
            query=query,
            contexts=len(contexts),
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            skipped_sites=skipped_sites,
            scheduled_sites=scheduled_site_count,
            mode_requests=mode_request_count,
            failed_sites=sum(1 for _plan, result in scheduled_results if result.failed),
            raw_results=raw_result_count,
            merged_results=len(merged_results),
            filtered_results=len(filtered_results),
            season_filtered_results=len(season_filtered_results),
        )
        if had_site_failures and not season_filtered_results and searched_any_site:
            return normalized_results
        return normalized_results

    async def _search_site_plans(
        self,
        plans: list[_SiteSearchPlan],
    ) -> list[tuple[_SiteSearchPlan, IndexerSiteSearchResult]]:
        if not plans:
            return []
        return await asyncio.gather(*(self._search_site_plan(plan) for plan in plans))

    async def _search_site_plan(self, plan: _SiteSearchPlan) -> tuple[_SiteSearchPlan, IndexerSiteSearchResult]:
        try:
            result = await self._search_site_modes(
                plan.context,
                plan.modes,
                media_type=plan.media_type,
                season_number=plan.season_number,
            )
        except Exception:
            logger.exception(
                "Resource media search site task failed: client=%s site=%s",
                plan.context.indexer_id,
                plan.context.site.id,
            )
            result = IndexerSiteSearchResult(results=[], failed=True, searched=True, outcomes=[])
        return plan, result

    def get_by_result_id(self, result_id: str) -> ResourceSearchResult | None:
        return self.cache.get_by_result_id(result_id)

    def get_latest_media_cached_results(
        self,
        media_id: MediaID,
        season_number: int | None = None,
    ) -> list[ResourceSearchResult] | None:
        return self.cache.get_latest_media_cached_results(media_id, season_number)

    def get_latest_media_search_metadata(
        self,
        media_id: MediaID,
        season_number: int | None = None,
    ) -> tuple[float | None, float | None]:
        payload = self.cache.get_latest_media_cache_payload(media_id, season_number)
        if payload is None:
            return None, None
        return payload.updated_at, payload.search_duration_seconds

    def cache_latest_media_results(
        self,
        media_id: MediaID,
        results: list[ResourceSearchResult],
        season_number: int | None = None,
    ) -> None:
        self.cache.cache_latest_media_results(media_id, results, season_number)

    def _read_site_cache(
        self,
        context: IndexerSearchContext,
        query: MediaSearchQuery,
        query_scope: str,
    ) -> list[ResourceSearchResult] | None:
        site_cache_key = self.cache.media_site_cache_key(
            query.media_id,
            context.indexer_id,
            context.site.id,
            context.cache_scope,
            query.season_number,
            query_scope,
        )
        if not query.use_cache:
            logger.debug(
                "Resource media search site cache bypassed: media_id=%s client=%s site=%s",
                str(query.media_id),
                context.indexer_id,
                context.site.id,
            )
            return None
        cached_results = self.cache.get_search_results(site_cache_key, allow_error=True)
        if cached_results is None:
            logger.debug(
                "Resource media search site cache miss: media_id=%s client=%s site=%s",
                str(query.media_id),
                context.indexer_id,
                context.site.id,
            )
            return None
        logger.debug(
            "Resource media search site cache hit: media_id=%s client=%s site=%s count=%s",
            str(query.media_id),
            context.indexer_id,
            context.site.id,
            len(cached_results),
        )
        return cached_results

    def _filter_media_compatible_contexts(
        self,
        contexts: list[IndexerSearchContext],
        query: MediaSearchQuery,
    ) -> list[IndexerSearchContext]:
        compatible_contexts = [
            context
            for context in contexts
            if self.indexer_gateway.context_supports_media_type(context, query.media_type)
        ]
        skipped_site_ids = [context.site.id for context in contexts if context not in compatible_contexts]
        if skipped_site_ids:
            logger.debug(
                "Resource media search skipping sites by media type: client=%s media_type=%s sites=%s",
                contexts[0].indexer_id if contexts else "",
                query.media_type.value if query.media_type else None,
                skipped_site_ids,
            )
        return compatible_contexts

    def _build_site_batches(
        self,
        contexts: list[IndexerSearchContext],
        query: MediaSearchQuery,
        built_title_query: str,
        douban_id: str | None,
    ) -> dict[str, list[tuple[str, str]]]:
        batches: dict[str, list[tuple[str, str]]] = {}
        for context in contexts:
            modes: list[tuple[str, str]] = []
            if douban_id and self.indexer_gateway.context_should_use_douban(context):
                modes.append(("doubanid", douban_id))
            if query.imdbid and self.indexer_gateway.context_should_use_imdb(context):
                modes.append(("imdbid", str(query.imdbid)))
            if built_title_query and self.indexer_gateway.context_should_use_title(context):
                modes.append(("q", built_title_query))
            for search_title in self._search_title_overrides_for_site(query, context):
                if search_title and self.indexer_gateway.context_should_use_title(context):
                    modes.append(("q", search_title))
            modes = self._dedupe_modes(modes)
            batches[context.site.id] = modes
        logger.debug(
            "Resource media search site batches: client=%s batches=%s",
            contexts[0].indexer_id if contexts else "",
            {site_id: [search_param for search_param, _ in modes] for site_id, modes in batches.items()},
        )
        return batches

    def _search_title_overrides_for_site(self, query: MediaSearchQuery, context: IndexerSearchContext) -> list[str]:
        titles: list[str] = []
        site_id = f"{context.indexer_id}::{context.site.id}"
        for rule in query.unmatched_rules or []:
            if not rule.search_title:
                continue
            if rule.sites and site_id not in rule.sites:
                continue
            titles.append(rule.search_title)
        return titles

    @staticmethod
    def _dedupe_modes(modes: list[tuple[str, str]]) -> list[tuple[str, str]]:
        seen: set[tuple[str, str]] = set()
        deduped: list[tuple[str, str]] = []
        for search_param, query_text in modes:
            key = (search_param, query_text.strip())
            if not key[1] or key in seen:
                continue
            seen.add(key)
            deduped.append(key)
        return deduped

    @staticmethod
    def _site_query_scope(modes: list[tuple[str, str]]) -> str:
        payload = "\n".join(f"{search_param}:{query_text}" for search_param, query_text in modes)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

    async def _search_site_modes(
        self,
        context: IndexerSearchContext,
        modes: list[tuple[str, str]],
        media_type: MediaType | None = None,
        season_number: int | None = None,
    ) -> IndexerSiteSearchResult:
        site_results: list[ResourceSearchResult] = []
        outcomes: list[IndexerSiteSearchOutcome] = []
        site_failed = False
        site_searched = False
        for search_param, query_text in modes:
            logger.debug(
                "Resource media search executing site search: client=%s site=%s search_param=%s query=%s",
                context.indexer_id,
                context.site.id,
                search_param,
                query_text,
            )
            result = await self.indexer_gateway.search_context(
                context,
                query_text,
                search_param,
                media_type=media_type,
                season_number=season_number,
            )
            outcomes.extend(result.outcomes)
            site_results.extend(result.results)
            site_failed = site_failed or result.failed
            site_searched = site_searched or result.searched

        merged_site_results = self.policy.merge_results(site_results)
        logger.debug(
            "Resource media search site merged results: client=%s site=%s raw=%s merged=%s searched=%s failed=%s",
            context.indexer_id,
            context.site.id,
            len(site_results),
            len(merged_site_results),
            site_searched,
            site_failed,
        )
        return IndexerSiteSearchResult(
            results=merged_site_results,
            failed=site_failed,
            searched=site_searched,
            outcomes=outcomes,
        )

    def _build_title_query(self, title: str, query: MediaSearchQuery) -> str:
        return title

    def _log_search_timing(
        self,
        *,
        started_at: float,
        query: MediaSearchQuery,
        contexts: int,
        cache_hits: int,
        cache_misses: int,
        skipped_sites: int,
        scheduled_sites: int,
        mode_requests: int,
        failed_sites: int,
        raw_results: int,
        merged_results: int,
        filtered_results: int,
        season_filtered_results: int,
    ) -> None:
        total_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "resource_search_timing total_ms=%.1f media_id=%s season=%s contexts=%s cache_hits=%s cache_misses=%s skipped_sites=%s scheduled_sites=%s mode_requests=%s failed_sites=%s raw_results=%s merged_results=%s filtered_results=%s season_filtered_results=%s use_cache=%s",
            total_ms,
            query.media_id,
            query.season_number,
            contexts,
            cache_hits,
            cache_misses,
            skipped_sites,
            scheduled_sites,
            mode_requests,
            failed_sites,
            raw_results,
            merged_results,
            filtered_results,
            season_filtered_results,
            query.use_cache,
        )


resource_search_service = ResourceSearchService()
