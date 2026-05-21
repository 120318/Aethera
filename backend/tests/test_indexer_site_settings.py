from types import SimpleNamespace

import pytest

from app.api.v1.config.indexers.sites import list_indexer_sites
from app.schemas.config import JackettConfig
from app.schemas.integration.site_models import IndexerSiteSetting, SiteInfo, SiteSearchCapabilities


class FakeJackettClient:
    def __init__(self, _config):
        self.session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get_indexers(self):
        return [
            SiteInfo(id="site-a", name="text A", description="A", language="zh", type="private"),
            SiteInfo(id="site-b", name="text B", description="B", language="en", type="private"),
        ]

    async def get_indexer_caps(self, site_id: str):
        if site_id == "site-a":
            return SiteSearchCapabilities(supports_q=True, supports_imdbid=True, supports_doubanid=False)
        return SiteSearchCapabilities(supports_q=False, supports_imdbid=False, supports_doubanid=True)

    async def list_sites(self):
        return await self.get_indexers()

    async def get_site_capabilities(self, site_id: str):
        return await self.get_indexer_caps(site_id)

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_list_indexer_sites_returns_settings_capabilities_and_effective(monkeypatch):
    indexer = JackettConfig(
        id="indexer-1",
        name="Jackett A",
        url="http://jackett",
        api_key="key",
        site_settings=[
            IndexerSiteSetting(site_id="site-a", enabled=True, disable_imdb=True),
            IndexerSiteSetting(site_id="site-offline", enabled=False, disable_title=True),
        ],
    )

    monkeypatch.setattr(
        "app.services.integration.indexer.catalog.settings_service",
        SimpleNamespace(list_indexers=lambda: [indexer]),
    )
    monkeypatch.setattr(
        "app.services.integration.indexer.catalog.indexer_gateway",
        SimpleNamespace(
            client_factory=SimpleNamespace(
                create_client_with_config=lambda _client_type, config: FakeJackettClient(config)
            )
        ),
    )

    response = await list_indexer_sites(indexer_id=None)

    assert len(response.indexers) == 1
    group = response.indexers[0]
    assert group.indexer_id == "indexer-1"
    site_a = next(item for item in group.sites if item.site_id == "site-a")
    assert site_a.is_live is True
    assert site_a.settings.enabled is True
    assert site_a.settings.disable_imdb is True
    assert site_a.capabilities.supports_title is True
    assert site_a.capabilities.supports_imdb is True
    assert site_a.capabilities.supports_douban is False
    assert site_a.effective.enabled is True
    assert site_a.effective.use_title is True
    assert site_a.effective.use_imdb is False
    assert site_a.effective.use_douban is False

    offline_site = next(item for item in group.sites if item.site_id == "site-offline")
    assert offline_site.is_live is False
    assert offline_site.settings.enabled is False
    assert offline_site.capabilities.supports_title is True
    assert offline_site.effective.enabled is False
    assert offline_site.effective.use_title is False
