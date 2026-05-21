import asyncio
import logging
from dataclasses import dataclass

from app.clients.base import IndexerClient
from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.integration.site_models import SiteInfo
from app.schemas.runtime.indexer_runtime import IndexerSiteSearchOutcome
from app.services.integration.indexer.site_scope import scoped_site_id

logger = logging.getLogger("app.services.indexer")


@dataclass(frozen=True)
class IndexerSiteSearchResult:
    results: list[ResourceSearchResult]
    failed: bool
    searched: bool
    outcomes: list[IndexerSiteSearchOutcome]


class IndexerSiteSearcher:
    def __init__(self, *, concurrency: int, timeout: int) -> None:
        self._concurrency = concurrency
        self._timeout = timeout

    async def search_sites_by_query(
        self,
        client: IndexerClient,
        sites: list[SiteInfo],
        query: str,
        search_param: str,
    ) -> IndexerSiteSearchResult:
        if not sites:
            return IndexerSiteSearchResult(results=[], failed=False, searched=False, outcomes=[])
        semaphore = asyncio.Semaphore(self._concurrency)
        outcomes = await asyncio.gather(*(
            self.search_site_by_query(client, site, query, search_param, semaphore)
            for site in sites
        ))

        results: list[ResourceSearchResult] = []
        had_failures = False
        for outcome in outcomes:
            if outcome.success:
                if outcome.results:
                    results.extend(self._normalize_site_results(client, outcome.site, outcome.results))
                continue

            had_failures = True
            error_message = outcome.error or "unknown error"
            logger.warning(
                "Indexer site search failed: indexer=%s site=%s error=%s",
                client.config.id,
                outcome.site.id,
                error_message,
            )
        return IndexerSiteSearchResult(results=results, failed=had_failures, searched=True, outcomes=list(outcomes))

    async def search_site_by_query(
        self,
        client: IndexerClient,
        site: SiteInfo,
        query: str,
        search_param: str,
        semaphore: asyncio.Semaphore,
    ) -> IndexerSiteSearchOutcome:
        async with semaphore:
            try:
                results = await asyncio.wait_for(
                    client.search_site(site.id, query, search_param=search_param),
                    timeout=self._timeout,
                )
                initial_matched_by_id = search_param in {"doubanid", "imdbid"}
                results = [
                    result.model_copy(update={"matched_by_id": initial_matched_by_id})
                    for result in results
                ]
                logger.debug(
                    "Indexer site batch result: client=%s site=%s search_param=%s query=%s count=%s",
                    client.config.id,
                    site.id,
                    search_param,
                    query,
                    len(results),
                )
                return IndexerSiteSearchOutcome(
                    indexer_id=client.config.id,
                    indexer_name=client.config.name,
                    indexer_type=client.config.type,
                    site=site,
                    success=True,
                    results=results,
                )
            except asyncio.TimeoutError as exc:
                error_message = str(exc).strip() or f"site_search_timeout:{site.id}"
                logger.debug(
                    "Indexer site batch failed: client=%s site=%s search_param=%s query=%s error=%s",
                    client.config.id,
                    site.id,
                    search_param,
                    query,
                    error_message,
                )
                return IndexerSiteSearchOutcome(
                    indexer_id=client.config.id,
                    indexer_name=client.config.name,
                    indexer_type=client.config.type,
                    site=site,
                    success=False,
                    error=error_message,
                )
            except RuntimeError as exc:
                error_message = str(exc).strip() or f"site_search_error:{site.id}"
                logger.debug(
                    "Indexer site batch failed: client=%s site=%s search_param=%s query=%s error=%s",
                    client.config.id,
                    site.id,
                    search_param,
                    query,
                    error_message,
                )
                return IndexerSiteSearchOutcome(
                    indexer_id=client.config.id,
                    indexer_name=client.config.name,
                    indexer_type=client.config.type,
                    site=site,
                    success=False,
                    error=error_message,
                )

    def _normalize_site_results(
        self,
        client: IndexerClient,
        site: SiteInfo,
        results: list[ResourceSearchResult],
    ) -> list[ResourceSearchResult]:
        site_name = site.name or site.description or site.id
        result_site_id = scoped_site_id(client.config.id, site.id)
        enriched_results = [
            result.model_copy(update={
                "site": result_site_id,
                "site_name": site_name,
                "indexer_id": client.config.id,
                "indexer_name": client.config.name or client.config.id,
                "indexer_type": client.config.type,
            })
            for result in results
        ]
        return self._filter_by_min_seeders(client, enriched_results)

    def _filter_by_min_seeders(
        self,
        client: IndexerClient,
        results: list[ResourceSearchResult],
    ) -> list[ResourceSearchResult]:
        min_seeders = client.config.min_seeders or 0
        if min_seeders <= 0:
            return results
        return [result for result in results if (result.seeders or 0) >= min_seeders]
