import hashlib
from datetime import UTC, datetime

import pytest

from app.clients.base import IndexerClient
from app.schemas.config import JackettConfig
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.resource_search import MediaSearchQuery, ResourceSearchResult
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.schemas.integration.site_models import SiteInfo, SiteSearchCapabilities
from app.schemas.media_id import MediaID
from app.schemas.runtime.indexer_runtime import CachedIndexerSearchPayload
from app.services.application.workflows.resource_search import ResourceSearchService
from app.services.integration.indexer import IndexerGateway
from app.services.platform.runtime_cache import runtime_cache


class FakeIndexerClient(IndexerClient):
    def __init__(self) -> None:
        super().__init__(JackettConfig(id="fake-indexer", name="Fake Indexer", url="http://fake", api_key="fake"))
        self.calls: list[tuple[str, str, str]] = []

    async def test_connection(self) -> bool:
        return True

    def get_id(self) -> str:
        return self.config.id

    async def search_all_torznab(self, query: str, category: str | None = None, indexers: list[str] | None = None):
        return []

    async def get_indexers(self) -> list[SiteInfo]:
        return [SiteInfo(id="fake-site", name="Fake Site", description="Fake", language="", type="private")]

    async def get_indexer_caps(self, indexer: str) -> SiteSearchCapabilities:
        return SiteSearchCapabilities(supports_q=True)

    async def search_indexer_torznab(
        self,
        indexer: str,
        query: str,
        category: str | None = None,
        search_param: str = "auto",
        season_number: int | None = None,
    ) -> list[ResourceSearchResult]:
        self.calls.append((indexer, search_param, query))
        return [
            ResourceSearchResult(
                id="raw-id",
                title="Example Show S01E01-E03 2160p WEB-DL",
                site=indexer,
                category="tv",
                size="1 GB",
                seeders=10,
                leechers=0,
                publish_date=datetime.now(UTC),
                download_url="https://example.com/download",
                detail_url="https://example.com/detail/1",
                result_id="raw-guid-from-indexer",
                matched_by_id=False,
            )
        ]


def _query() -> MediaSearchQuery:
    return MediaSearchQuery(
        media=MediaExecutionSnapshot(
            media_id=MediaID.parse("douban:tv:123"),
            title="Example Show",
            year=2026,
            season_number=1,
        ),
        use_cache=False,
    )


def _site_cache_key(service: ResourceSearchService, client: FakeIndexerClient, query: MediaSearchQuery) -> str:
    return service.cache.media_site_cache_key(
        query.media_id,
        client.config.id,
        "fake-site",
        service.indexer_gateway._config_cache_scope(client.config),
        query.season_number,
        service._site_query_scope([("q", query.title)]),
    )


@pytest.mark.asyncio
async def test_search_media_returns_stable_result_id_for_fresh_results():
    runtime_cache.clear()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=FakeIndexerClient()))
    query = _query()

    results = await service.search_media(query)

    assert len(results) == 1
    expected_result_id = hashlib.sha1("fake-indexer|fake-indexer::fake-site|https://example.com/detail/1".encode("utf-8")).hexdigest()
    assert results[0].result_id == expected_result_id
    stored = service.get_by_result_id(results[0].result_id)
    assert stored is not None
    assert stored.result_id == expected_result_id


@pytest.mark.asyncio
async def test_empty_latest_media_results_overwrite_existing_snapshot():
    runtime_cache.clear()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=FakeIndexerClient()))
    query = _query()

    first_results = await service.search_media(query)
    service.cache_latest_media_results(query.media_id, [])

    assert len(first_results) == 1
    assert service.get_latest_media_cached_results(query.media_id) == []


@pytest.mark.asyncio
async def test_latest_media_result_cache_stores_ids_and_resolves_details():
    runtime_cache.clear()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=FakeIndexerClient()))
    query = _query()

    results = await service.search_media(query)
    payload = CachedIndexerSearchPayload.model_validate(
        runtime_cache.read(service.cache.latest_media_storage_key(query.media_id, query.season_number))
    )

    assert len(results) == 1
    assert payload.result_ids == [results[0].result_id]
    assert payload.results[0].result_id == results[0].result_id
    assert service.get_latest_media_cached_results(query.media_id, query.season_number)[0].result_id == results[0].result_id


@pytest.mark.asyncio
async def test_latest_media_result_cache_falls_back_to_snapshot_without_detail_cache():
    runtime_cache.clear()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=FakeIndexerClient()))
    query = _query()

    results = await service.search_media(query)
    runtime_cache.delete(service.cache.result_storage_key(results[0].result_id))

    assert service.get_latest_media_cached_results(query.media_id, query.season_number)[0].result_id == results[0].result_id


@pytest.mark.asyncio
async def test_search_cache_detail_miss_is_not_empty_cache_hit():
    runtime_cache.clear()
    client = FakeIndexerClient()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=client))
    query = _query()

    results = await service.search_media(query)
    site_key = _site_cache_key(service, client, query)
    runtime_cache.delete(service.cache.result_storage_key(results[0].result_id))

    assert service.cache.get_search_results(site_key, allow_error=True) is None


@pytest.mark.asyncio
async def test_site_search_cache_is_scoped_by_tv_season():
    runtime_cache.clear()
    client = FakeIndexerClient()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=client))
    season_one_query = _query().model_copy(update={"use_cache": True})
    season_three_query = MediaSearchQuery(
        media=season_one_query.media.model_copy(update={"season_number": 3}),
        use_cache=True,
    )

    season_one_results = await service.search_media(season_one_query)
    season_three_results = await service.search_media(season_three_query)

    assert len(season_one_results) == 1
    assert season_three_results == []
    assert len(client.calls) == 2
    assert service.cache.media_site_cache_key(
        season_one_query.media_id,
        client.config.id,
        "fake-site",
        service.indexer_gateway._config_cache_scope(client.config),
        season_one_query.season_number,
        service._site_query_scope([("q", season_one_query.title)]),
    ) != service.cache.media_site_cache_key(
        season_three_query.media_id,
        client.config.id,
        "fake-site",
        service.indexer_gateway._config_cache_scope(client.config),
        season_three_query.season_number,
        service._site_query_scope([("q", season_three_query.title)]),
    )


@pytest.mark.asyncio
async def test_search_title_replacement_adds_site_title_query():
    runtime_cache.clear()
    client = FakeIndexerClient()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=client))
    query = _query().model_copy(
        update={
            "unmatched_rules": [
                SubscriptionUnmatchedRule(sites=["fake-indexer::fake-site"], search_title="Special Keyword", pattern=""),
            ],
        }
    )

    results = await service.search_media(query)

    assert len(results) == 2
    assert client.calls == [
        ("fake-site", "q", "Example Show"),
        ("fake-site", "q", "Special Keyword"),
    ]


@pytest.mark.asyncio
async def test_site_search_cache_is_scoped_by_search_title_replacement():
    runtime_cache.clear()
    client = FakeIndexerClient()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=client))
    base_query = _query().model_copy(update={"use_cache": True})
    override_query = base_query.model_copy(
        update={
            "unmatched_rules": [
                SubscriptionUnmatchedRule(sites=["fake-indexer::fake-site"], search_title="Special Keyword", pattern=""),
            ],
        }
    )

    await service.search_media(base_query)
    await service.search_media(override_query)

    assert client.calls == [
        ("fake-site", "q", "Example Show"),
        ("fake-site", "q", "Example Show"),
        ("fake-site", "q", "Special Keyword"),
    ]
    assert service.cache.media_site_cache_key(
        base_query.media_id,
        client.config.id,
        "fake-site",
        service.indexer_gateway._config_cache_scope(client.config),
        base_query.season_number,
        service._site_query_scope([("q", base_query.title)]),
    ) != service.cache.media_site_cache_key(
        override_query.media_id,
        client.config.id,
        "fake-site",
        service.indexer_gateway._config_cache_scope(client.config),
        override_query.season_number,
        service._site_query_scope([("q", override_query.title), ("q", "Special Keyword")]),
    )
