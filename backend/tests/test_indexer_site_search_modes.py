from datetime import UTC, datetime
import asyncio

import pytest

from app.clients.base import IndexerClient
from app.schemas.config import JackettConfig
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_search import MediaSearchQuery, ResourceSearchResult
from app.schemas.integration.site_models import IndexerSiteSetting, SiteInfo, SiteSearchCapabilities
from app.schemas.media_id import MediaID
from app.services.integration.indexer.site_scope import scoped_site_id
from app.services.integration.indexer import IndexerGateway
from app.services.application.workflows.resource_search import ResourceSearchService
from app.services.platform.runtime_cache import runtime_cache


pytestmark = [pytest.mark.drift]


def _query(
    media_id: str,
    *,
    title: str,
    year: int = 2026,
    imdb_id: str | None = None,
    douban_id: str | None = None,
    season_number: int | None = None,
    indexers: list[str] | None = None,
) -> MediaSearchQuery:
    return MediaSearchQuery(
        media=MediaExecutionSnapshot(
            media_id=MediaID.parse(media_id),
            title=title,
            year=year,
            imdb_id=imdb_id,
            douban_id=douban_id,
            season_number=season_number,
        ),
        indexers=indexers,
        use_cache=False,
    )


class RecordingIndexerClient(IndexerClient):
    def __init__(self) -> None:
        super().__init__(
            JackettConfig(
                id="fake-indexer",
                name="Fake Indexer",
                url="http://fake",
                api_key="fake",
                site_settings=[
                    IndexerSiteSetting(site_id="site-a", enabled=True, disable_imdb=True, disable_douban=True),
                    IndexerSiteSetting(site_id="site-b", enabled=False),
                ],
            )
        )
        self.calls: list[tuple[str, str]] = []

    async def test_connection(self) -> bool:
        return True

    def get_id(self) -> str:
        return self.config.id

    async def search_all_torznab(self, query: str, category: str | None = None, indexers: list[str] | None = None):
        return []

    async def get_indexers(self) -> list[SiteInfo]:
        return [
            SiteInfo(id="site-a", name="Site A", description="A", language="", type="private"),
            SiteInfo(id="site-b", name="Site B", description="B", language="", type="private"),
        ]

    async def get_indexer_caps(self, indexer: str) -> SiteSearchCapabilities:
        return SiteSearchCapabilities(supports_q=True, supports_imdbid=True, supports_doubanid=True)

    async def search_indexer_torznab(
        self,
        indexer: str,
        query: str,
        category: str | None = None,
        search_param: str = "auto",
        season_number: int | None = None,
        capabilities: SiteSearchCapabilities | None = None,
    ) -> list[ResourceSearchResult]:
        self.calls.append((indexer, search_param))
        return [
            ResourceSearchResult(
                id=f"{indexer}-{search_param}",
                title="Example Show S01E01 2160p WEB-DL",
                site=indexer,
                category="tv",
                size="1 GB",
                seeders=10,
                leechers=0,
                publish_date=datetime.now(UTC),
                download_url="https://example.com/download",
                detail_url=f"https://example.com/detail/{indexer}/{search_param}",
                result_id=f"{indexer}-{search_param}",
                matched_by_id=False,
            )
        ]


@pytest.mark.asyncio
async def test_search_media_respects_site_level_disable_settings():
    runtime_cache.clear()
    client = RecordingIndexerClient()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=client))
    query = _query("douban:tv:123", title="Example Show", imdb_id="tt1234567", season_number=1)

    results = await service.search_media(query)

    assert len(results) == 1
    assert results[0].indexer_id == "fake-indexer"
    assert results[0].indexer_name == "Fake Indexer"
    assert results[0].indexer_type == "jackett"
    assert results[0].site == scoped_site_id("fake-indexer", "site-a")
    assert results[0].site_name == "Site A"
    assert client.calls == [("site-a", "q")]


class MediaTypeFilteringClient(RecordingIndexerClient):
    def __init__(self, site_settings=None) -> None:
        super().__init__()
        self.config.site_settings = site_settings or []

    async def get_indexers(self) -> list[SiteInfo]:
        return [
            SiteInfo(id="movie-site", name="Movie Site", description="Movies", language="", type="private"),
            SiteInfo(id="tv-site", name="TV Site", description="TV", language="", type="private"),
            SiteInfo(id="mixed-site", name="Mixed Site", description="Movies and TV", language="", type="private"),
        ]

    async def get_indexer_caps(self, indexer: str) -> SiteSearchCapabilities:
        if indexer == "movie-site":
            return SiteSearchCapabilities(supports_q=True, supports_movie=True, supports_tv=False)
        if indexer == "tv-site":
            return SiteSearchCapabilities(supports_q=True, supports_movie=False, supports_tv=True)
        return SiteSearchCapabilities(supports_q=True, supports_movie=True, supports_tv=True)


@pytest.mark.asyncio
async def test_search_media_skips_sites_that_do_not_support_query_media_type():
    runtime_cache.clear()
    client = MediaTypeFilteringClient()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=client))
    query = _query("tmdb:movie:123", title="Example Movie")

    await service.search_media(query)

    assert client.calls == [("movie-site", "q"), ("mixed-site", "q")]


@pytest.mark.asyncio
async def test_search_media_limits_manual_media_types_to_caps_support():
    runtime_cache.clear()
    client = MediaTypeFilteringClient(
        site_settings=[
            IndexerSiteSetting(site_id="movie-site", media_types=[MediaType.tv]),
            IndexerSiteSetting(site_id="tv-site", media_types=[MediaType.movie]),
            IndexerSiteSetting(site_id="mixed-site", media_types=[MediaType.tv]),
        ]
    )
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=client))
    query = _query("tmdb:movie:123", title="Example Movie")

    await service.search_media(query)

    assert client.calls == []


class ExternalDoubanIdClient(RecordingIndexerClient):
    def __init__(self) -> None:
        super().__init__()
        self.config.site_settings = []
        self.queries: list[tuple[str, str, str]] = []

    async def get_indexers(self) -> list[SiteInfo]:
        return [SiteInfo(id="douban-site", name="Douban Site", description="Douban", language="", type="private")]

    async def search_indexer_torznab(
        self,
        indexer: str,
        query: str,
        category: str | None = None,
        search_param: str = "auto",
        season_number: int | None = None,
        capabilities: SiteSearchCapabilities | None = None,
    ) -> list[ResourceSearchResult]:
        self.calls.append((indexer, search_param))
        self.queries.append((indexer, search_param, query))
        return [
            ResourceSearchResult(
                id=f"{indexer}-{search_param}",
                title="Example Movie 2160p WEB-DL",
                site=indexer,
                category="movie",
                size="1 GB",
                seeders=10,
                leechers=0,
                publish_date=datetime.now(UTC),
                download_url="https://example.com/download",
                detail_url=f"https://example.com/detail/{indexer}/{search_param}",
                result_id=f"{indexer}-{search_param}",
                source_doubanid=query if search_param == "doubanid" else None,
                source_imdbid=query if search_param == "imdbid" else None,
                matched_by_id=search_param in {"doubanid", "imdbid"},
            )
        ]


@pytest.mark.asyncio
async def test_search_media_uses_explicit_douban_id_for_tmdb_media_id():
    runtime_cache.clear()
    client = ExternalDoubanIdClient()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=client))
    query = _query("tmdb:movie:123", title="Example Movie", imdb_id="tt1234567", douban_id="36513446")

    await service.search_media(query)

    assert ("douban-site", "doubanid", "36513446") in client.queries
    assert ("douban-site", "imdbid", "tt1234567") in client.queries


@pytest.mark.asyncio
async def test_search_media_can_disable_caps_supported_media_type_manually():
    runtime_cache.clear()
    client = MediaTypeFilteringClient(
        site_settings=[
            IndexerSiteSetting(site_id="movie-site", media_types=[]),
            IndexerSiteSetting(site_id="mixed-site", media_types=[MediaType.tv]),
        ]
    )
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=client))
    query = _query("tmdb:movie:123", title="Example Movie")

    await service.search_media(query)

    assert client.calls == []


class DuplicateSiteClient(RecordingIndexerClient):
    def __init__(self, indexer_id: str, name: str) -> None:
        super().__init__()
        self.config.id = indexer_id
        self.config.name = name
        self.config.site_settings = []

    async def get_indexers(self) -> list[SiteInfo]:
        return [SiteInfo(id="1", name="Shared Site", description="Shared", language="", type="private")]


@pytest.mark.asyncio
async def test_search_media_routes_scoped_site_to_selected_indexer_only():
    runtime_cache.clear()
    first_client = DuplicateSiteClient("prowlarr-a", "Prowlarr A")
    second_client = DuplicateSiteClient("prowlarr-b", "Prowlarr B")
    gateway = IndexerGateway(client=first_client)
    gateway.clients = [first_client, second_client]
    service = ResourceSearchService(indexer_gateway=gateway)
    query = _query("tmdb:movie:123", title="Example Movie", indexers=[scoped_site_id("prowlarr-b", "1")])

    results = await service.search_media(query)

    assert first_client.calls == []
    assert second_client.calls == [("1", "q")]
    assert len(results) == 1
    assert results[0].indexer_id == "prowlarr-b"
    assert results[0].site == scoped_site_id("prowlarr-b", "1")
    cached_results = service.get_latest_media_cached_results(query.media_id)
    assert cached_results is not None
    assert [result.site for result in cached_results] == [scoped_site_id("prowlarr-b", "1")]


class ConcurrentModeClient(IndexerClient):
    def __init__(self) -> None:
        super().__init__(
            JackettConfig(
                id="concurrent-indexer",
                name="Concurrent Indexer",
                url="http://fake",
                api_key="fake",
                site_settings=[],
            )
        )
        self.calls: list[tuple[str, str]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def test_connection(self) -> bool:
        return True

    def get_id(self) -> str:
        return self.config.id

    async def search_all_torznab(self, query: str, category: str | None = None, indexers: list[str] | None = None):
        return []

    async def get_indexers(self) -> list[SiteInfo]:
        return [
            SiteInfo(id="site-1", name="Site 1", description="Site 1", language="", type="private"),
            SiteInfo(id="site-2", name="Site 2", description="Site 2", language="", type="private"),
            SiteInfo(id="site-3", name="Site 3", description="Site 3", language="", type="private"),
        ]

    async def get_indexer_caps(self, indexer: str) -> SiteSearchCapabilities:
        return SiteSearchCapabilities(supports_q=True, supports_imdbid=True, supports_doubanid=True)

    async def search_indexer_torznab(
        self,
        indexer: str,
        query: str,
        category: str | None = None,
        search_param: str = "auto",
        season_number: int | None = None,
        capabilities: SiteSearchCapabilities | None = None,
    ) -> list[ResourceSearchResult]:
        self.calls.append((indexer, search_param))
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.01)
            return []
        finally:
            self.in_flight -= 1


class CapabilityRecordingClient(RecordingIndexerClient):
    def __init__(self) -> None:
        super().__init__()
        self.config.site_settings = []
        self.capability_calls = 0
        self.seen_capabilities: list[SiteSearchCapabilities | None] = []

    async def get_indexers(self) -> list[SiteInfo]:
        return [SiteInfo(id="site-a", name="Site A", description="A", language="", type="private")]

    async def get_indexer_caps(self, indexer: str) -> SiteSearchCapabilities:
        self.capability_calls += 1
        return SiteSearchCapabilities(supports_q=True, supports_imdbid=True, supports_doubanid=True)

    async def search_indexer_torznab(
        self,
        indexer: str,
        query: str,
        category: str | None = None,
        search_param: str = "auto",
        season_number: int | None = None,
        capabilities: SiteSearchCapabilities | None = None,
    ) -> list[ResourceSearchResult]:
        self.calls.append((indexer, search_param))
        self.seen_capabilities.append(capabilities)
        return []


@pytest.mark.asyncio
async def test_search_media_runs_sites_concurrently_and_modes_sequentially_per_site():
    runtime_cache.clear()
    client = ConcurrentModeClient()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=client))
    query = _query(
        "tmdb:tv:789",
        title="Example Show",
        imdb_id="tt7654321",
        douban_id="36513446",
        season_number=1,
    )

    await service.search_media(query)

    assert client.max_in_flight == 3
    for site_id in ("site-1", "site-2", "site-3"):
        assert [search_param for site, search_param in client.calls if site == site_id] == [
            "doubanid",
            "imdbid",
            "q",
        ]


@pytest.mark.asyncio
async def test_search_media_reuses_resolved_site_capabilities_for_each_mode():
    runtime_cache.clear()
    client = CapabilityRecordingClient()
    service = ResourceSearchService(indexer_gateway=IndexerGateway(client=client))
    query = _query(
        "tmdb:tv:789",
        title="Example Show",
        imdb_id="tt7654321",
        douban_id="36513446",
        season_number=1,
    )

    await service.search_media(query)

    assert client.capability_calls == 1
    assert client.calls == [("site-a", "doubanid"), ("site-a", "imdbid"), ("site-a", "q")]
    assert all(capability is not None for capability in client.seen_capabilities)


class SingleSiteClient(RecordingIndexerClient):
    def __init__(self, config: JackettConfig) -> None:
        super().__init__()
        self.config = config

    async def get_indexers(self) -> list[SiteInfo]:
        return [SiteInfo(id="hddolby", name="HDDolby", description="HDDolby", language="", type="private")]


@pytest.mark.asyncio
async def test_gateway_refresh_uses_latest_site_settings(monkeypatch):
    runtime_cache.clear()
    initial_config = JackettConfig(
        id="refresh-indexer",
        name="Refresh Indexer",
        url="http://fake",
        api_key="fake",
        site_settings=[IndexerSiteSetting(site_id="hddolby", enabled=True)],
    )
    updated_config = initial_config.model_copy(
        update={
            "site_settings": [
                IndexerSiteSetting(site_id="hddolby", enabled=True, disable_imdb=True, disable_douban=True)
            ]
        }
    )
    configs = [initial_config]

    monkeypatch.setattr(
        "app.services.integration.indexer.gateway.settings_service.list_enabled_indexers",
        lambda: configs,
    )
    monkeypatch.setattr(
        "app.services.integration.indexer.gateway.ClientFactory.create_client_with_config",
        lambda _client_type, config: SingleSiteClient(config),
    )

    gateway = IndexerGateway()
    configs[:] = [updated_config]
    service = ResourceSearchService(indexer_gateway=gateway)
    query = _query(
        "tmdb:tv:456",
        title="Example Show",
        imdb_id="tt7654321",
        douban_id="36513446",
        season_number=1,
    )

    await service.search_media(query)

    client = gateway.clients[0]
    assert isinstance(client, SingleSiteClient)
    assert client.calls == [("hddolby", "q")]
