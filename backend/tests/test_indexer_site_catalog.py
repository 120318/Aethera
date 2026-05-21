from types import SimpleNamespace

import pytest

from app.schemas.config import JackettConfig
from app.schemas.integration.site_models import SiteInfo
from app.services.integration.indexer.site_scope import scoped_site_id
from app.services.integration.indexer.catalog import IndexerSiteCatalogService


class CatalogClient:
    def __init__(self, indexer_id: str, name: str) -> None:
        self.config = JackettConfig(
            id=indexer_id,
            name=name,
            url="http://indexer",
            api_key="key",
        )

    async def list_sites(self) -> list[SiteInfo]:
        return [SiteInfo(id="1", name="Shared Site", description="Shared", language="", type="private")]


@pytest.mark.asyncio
async def test_available_site_catalog_scopes_duplicate_site_ids_by_indexer(monkeypatch):
    clients = [
        CatalogClient("prowlarr-a", "Prowlarr A"),
        CatalogClient("prowlarr-b", "Prowlarr B"),
    ]
    monkeypatch.setattr(
        "app.services.integration.indexer.catalog.indexer_gateway",
        SimpleNamespace(clients=clients, refresh_clients=lambda: None),
    )

    sites = await IndexerSiteCatalogService().list_available_sites()

    assert [site.id for site in sites] == [
        scoped_site_id("prowlarr-a", "1"),
        scoped_site_id("prowlarr-b", "1"),
    ]
    assert [site.name for site in sites] == [
        "Prowlarr A / Shared Site",
        "Prowlarr B / Shared Site",
    ]
