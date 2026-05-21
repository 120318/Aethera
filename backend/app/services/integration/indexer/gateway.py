import asyncio
import hashlib
import json
import logging

from app.clients.base import IndexerClient
from app.clients.factory import ClientFactory, ClientType
from app.schemas.config import IndexerProviderConfig
from app.schemas.domain.media_types import MediaType
from app.schemas.integration.site_models import (
    IndexerSiteSetting,
    SiteInfo,
    SiteSearchCapabilities,
    effective_media_types_from_caps,
)
from app.schemas.constants.indexer import SITE_SEARCH_TIMEOUT_SECONDS
from app.schemas.runtime.indexer_runtime import IndexerSearchContext
from app.schemas.runtime.indexer_site_health import IndexerSiteHealthStatus
from app.services.config.settings_service import settings_service
from app.services.integration.indexer.site_scope import split_scoped_site_id
from app.services.integration.indexer.site_search import IndexerSiteSearcher, IndexerSiteSearchResult

logger = logging.getLogger("app.services.indexer")


class IndexerGateway:
    def __init__(self, client: IndexerClient | None = None) -> None:
        provided_client = client
        enabled_indexers: list[IndexerProviderConfig] = []
        if provided_client is None:
            enabled_indexers = settings_service.list_enabled_indexers()
            self.clients = [
                ClientFactory.create_client_with_config(ClientType(indexer_config.type), indexer_config)
                for indexer_config in enabled_indexers
            ]
        else:
            self.clients = [provided_client]

        self.client_factory = ClientFactory
        self._clients_fingerprint = self._fingerprint_enabled_indexers(enabled_indexers)
        self._site_searcher = IndexerSiteSearcher(concurrency=4, timeout=SITE_SEARCH_TIMEOUT_SECONDS)

    def refresh_clients(self) -> None:
        enabled_indexers = settings_service.list_enabled_indexers()
        fingerprint = self._fingerprint_enabled_indexers(enabled_indexers)
        if fingerprint == self._clients_fingerprint:
            return

        clients = []
        for indexer_config in enabled_indexers:
            try:
                client = ClientFactory.create_client_with_config(ClientType(indexer_config.type), indexer_config)
                clients.append(client)
            except (RuntimeError, ValueError) as e:
                logger.error("Failed to create indexer client %s: %s", indexer_config.id, e)

        self.clients = clients
        self._clients_fingerprint = fingerprint

    async def search_sites_by_query(
        self,
        client: IndexerClient,
        sites: list[SiteInfo],
        query: str,
        search_param: str,
    ) -> IndexerSiteSearchResult:
        return await self._site_searcher.search_sites_by_query(client, sites, query, search_param)

    async def search_context(
        self,
        context: IndexerSearchContext,
        query: str,
        search_param: str,
    ) -> IndexerSiteSearchResult:
        client = self._client_by_id(context.indexer_id)
        if client is None:
            logger.warning("Indexer search skipped because client is unavailable: indexer=%s", context.indexer_id)
            return IndexerSiteSearchResult(results=[], failed=True, searched=False, outcomes=[])
        return await self._site_searcher.search_sites_by_query(client, [context.site], query, search_param)

    async def list_search_contexts(
        self,
        requested_sites: list[str] | None,
    ) -> list[IndexerSearchContext]:
        self.refresh_clients()
        contexts: list[IndexerSearchContext] = []
        results = await asyncio.gather(
            *(self._list_search_contexts_safely(client, requested_sites) for client in self.clients),
        )
        for client, result in zip(self.clients, results, strict=True):
            contexts.extend(result)
        return contexts

    async def _list_search_contexts_safely(
        self,
        client: IndexerClient,
        requested_sites: list[str] | None,
    ) -> list[IndexerSearchContext]:
        try:
            return await self._list_search_contexts_for_client(client, requested_sites)
        except Exception as exc:
            logger.warning(
                "Indexer search contexts skipped because client failed: client=%s error=%s",
                client.config.id,
                exc,
            )
            return []

    async def _list_search_contexts_for_client(
        self,
        client: IndexerClient,
        requested_sites: list[str] | None,
    ) -> list[IndexerSearchContext]:
        sites = await self.resolve_sites_for_client(client, requested_sites)
        if not sites:
            return []
        capabilities_by_site = await self.resolve_site_capabilities(client, sites)
        return [
            IndexerSearchContext(
                indexer_id=client.config.id,
                indexer_name=client.config.name or client.config.id,
                indexer_type=client.config.type,
                site=site,
                capabilities=capabilities_by_site[site.id],
                setting=self.get_site_setting(client, site.id),
                cache_scope=self._config_cache_scope(client.config),
            )
            for site in sites
        ]

    async def resolve_sites_for_client(
        self,
        client: IndexerClient,
        requested_sites: list[str] | None,
    ) -> list[SiteInfo]:
        try:
            available_sites = await client.list_sites()
        except RuntimeError as e:
            logger.warning("Failed to get indexers for client %s: %s", client.config.id, e)
            available_sites = []

        if requested_sites:
            site_map = {site.id: site for site in available_sites}
            resolved = []
            for requested_site_id in requested_sites:
                scoped_indexer_id, site_id = split_scoped_site_id(requested_site_id)
                if scoped_indexer_id and scoped_indexer_id != client.config.id:
                    continue
                resolved.append(
                    site_map[site_id]
                    if site_id in site_map
                    else SiteInfo(
                        id=site_id,
                        name=site_id,
                        description=site_id,
                        language="",
                        type="unknown",
                    )
                )
            logger.debug(
                "Indexer resolved requested sites: client=%s requested=%s resolved=%s",
                client.config.id,
                requested_sites,
                [site.id for site in resolved],
            )
            return resolved

        logger.debug(
            "Indexer resolved all available sites: client=%s sites=%s",
            client.config.id,
            [site.id for site in available_sites],
        )
        return available_sites

    async def resolve_site_capabilities(
        self,
        client: IndexerClient,
        sites: list[SiteInfo],
    ) -> dict[str, SiteSearchCapabilities]:
        loaded = await asyncio.gather(*(self._resolve_site_capability(client, site) for site in sites))
        capabilities_by_site = dict(loaded)
        logger.debug(
            "Indexer site capabilities loaded: client=%s capabilities=%s",
            client.config.id,
            {site_id: caps.model_dump(mode="json") for site_id, caps in capabilities_by_site.items()},
        )
        return capabilities_by_site

    async def _resolve_site_capability(
        self,
        client: IndexerClient,
        site: SiteInfo,
    ) -> tuple[str, SiteSearchCapabilities]:
        try:
            capabilities = await client.get_site_capabilities(site.id)
        except Exception as exc:
            logger.warning(
                "Indexer site capabilities fallback: client=%s site=%s error=%s",
                client.config.id,
                site.id,
                exc,
            )
            capabilities = SiteSearchCapabilities()
        return site.id, capabilities

    def is_site_enabled(self, client: IndexerClient, site_id: str) -> bool:
        return self.get_site_setting(client, site_id).enabled

    def is_context_enabled(self, context: IndexerSearchContext) -> bool:
        return context.setting.enabled

    def should_use_title(
        self,
        client: IndexerClient,
        site_id: str,
        capabilities: SiteSearchCapabilities,
    ) -> bool:
        setting = self.get_site_setting(client, site_id)
        return setting.enabled and capabilities.supports_q and not setting.disable_title

    def context_should_use_title(self, context: IndexerSearchContext) -> bool:
        return context.setting.enabled and context.capabilities.supports_q and not context.setting.disable_title

    def should_use_imdb(
        self,
        client: IndexerClient,
        site_id: str,
        capabilities: SiteSearchCapabilities,
    ) -> bool:
        setting = self.get_site_setting(client, site_id)
        return setting.enabled and capabilities.supports_imdbid and not setting.disable_imdb

    def context_should_use_imdb(self, context: IndexerSearchContext) -> bool:
        return context.setting.enabled and context.capabilities.supports_imdbid and not context.setting.disable_imdb

    def should_use_douban(
        self,
        client: IndexerClient,
        site_id: str,
        capabilities: SiteSearchCapabilities,
    ) -> bool:
        setting = self.get_site_setting(client, site_id)
        return setting.enabled and capabilities.supports_doubanid and not setting.disable_douban

    def context_should_use_douban(self, context: IndexerSearchContext) -> bool:
        return context.setting.enabled and context.capabilities.supports_doubanid and not context.setting.disable_douban

    def site_supports_media_type(
        self,
        client: IndexerClient,
        site_id: str,
        capabilities: SiteSearchCapabilities,
        media_type: MediaType | None,
    ) -> bool:
        if media_type is None:
            return True
        setting = self.get_site_setting(client, site_id)
        return media_type in effective_media_types_from_caps(capabilities, setting.media_types)

    def context_supports_media_type(
        self,
        context: IndexerSearchContext,
        media_type: MediaType | None,
    ) -> bool:
        if media_type is None:
            return True
        return media_type in effective_media_types_from_caps(context.capabilities, context.setting.media_types)

    def build_torznab_feed(self, query: str, indexers: list[str] | None = None) -> str:
        self.refresh_clients()
        if not self.clients:
            logger.warning("Cannot build torznab feed because no indexer clients are available")
            return ""
        return self.clients[0].build_torznab_feed(query, indexers)

    async def get_site_health_for_config(self, indexer: IndexerProviderConfig) -> list[IndexerSiteHealthStatus]:
        client = self.client_factory.create_client_with_config(ClientType(indexer.type), indexer)
        try:
            return await client.get_site_health()
        finally:
            await client.close()

    async def test_connection_for_config(self, indexer: IndexerProviderConfig) -> bool:
        client = self.client_factory.create_client_with_config(ClientType(indexer.type), indexer)
        try:
            return await client.test_connection()
        finally:
            await client.close()

    async def list_sites_for_config(self, indexer: IndexerProviderConfig) -> list[SiteInfo]:
        client = self.client_factory.create_client_with_config(ClientType(indexer.type), indexer)
        try:
            return await client.list_sites()
        finally:
            await client.close()

    def get_site_setting(self, client: IndexerClient, site_id: str) -> IndexerSiteSetting:
        for item in client.config.site_settings:
            if item.site_id == site_id:
                return item
        return IndexerSiteSetting(site_id=site_id)

    def _client_by_id(self, indexer_id: str) -> IndexerClient | None:
        for client in self.clients:
            if client.config.id == indexer_id:
                return client
        self.refresh_clients()
        for client in self.clients:
            if client.config.id == indexer_id:
                return client
        return None

    def _fingerprint_enabled_indexers(self, indexers: list[IndexerProviderConfig]) -> tuple[tuple[str, str], ...]:
        fingerprints: list[tuple[str, str]] = []
        for idx in indexers:
            fingerprints.append((idx.id, self._config_cache_scope(idx)))
        return tuple(fingerprints)

    def _config_cache_scope(self, config: IndexerProviderConfig) -> str:
        payload = json.dumps(config.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()


indexer_gateway = IndexerGateway()
