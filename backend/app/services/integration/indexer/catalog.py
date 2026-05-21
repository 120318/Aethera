import logging
import time

from app.clients.factory import ClientType
from app.schemas.config import IndexerProviderConfig
from app.schemas.domain.media_types import MediaType
from app.schemas.exception import ConfigurationException
from app.schemas.integration.site_models import (
    IndexerSiteSetting,
    SiteInfo,
    SiteSearchCapabilities,
    effective_media_types_from_caps,
)
from app.schemas.runtime.indexer_sites import (
    IndexerSiteCapabilitiesPayload,
    IndexerSiteEffectivePayload,
    IndexerSitesGroup,
    IndexerSiteSettingsPayload,
    IndexerSiteStatusItem,
)
from app.services.config.settings_service import settings_service
from app.services.integration.indexer import indexer_gateway
from app.services.integration.indexer.site_scope import scoped_site_id

logger = logging.getLogger(__name__)


class IndexerSiteCatalogService:
    def _is_site_enabled(self, config: IndexerProviderConfig, site_id: str) -> bool:
        for setting in config.site_settings:
            if setting.site_id == site_id:
                return setting.enabled
        return True

    async def list_available_sites(self) -> list[SiteInfo]:
        try:
            indexer_gateway.refresh_clients()
            if not indexer_gateway.clients:
                return []

            all_sites: list[SiteInfo] = []
            for client in indexer_gateway.clients:
                try:
                    sites = await client.list_sites()
                    if sites:
                        for site in sites:
                            if not self._is_site_enabled(client.config, site.id):
                                continue
                            display_name = site.name or site.description or site.id
                            all_sites.append(site.model_copy(update={
                                "id": scoped_site_id(client.config.id, site.id),
                                "name": f"{client.config.name or client.config.id} / {display_name}",
                            }))
                except (RuntimeError, ValueError) as client_error:
                    logger.warning("Failed to get sites from client %s: %s", client, client_error)

            configured_sites_by_id: dict[str, SiteInfo] = {}
            for site in all_sites:
                if not site.id:
                    continue
                existing = configured_sites_by_id[site.id] if site.id in configured_sites_by_id else None
                display_name = site.name or site.description or site.id
                normalized = site.model_copy(update={"name": display_name})
                if existing is None:
                    configured_sites_by_id[site.id] = normalized
                    continue
                if not existing.name and normalized.name:
                    configured_sites_by_id[site.id] = normalized
            return list(configured_sites_by_id.values())
        except (RuntimeError, ValueError) as error:
            logger.warning("Failed to get sites from indexers: %s", error)
            return []

    async def list_indexer_site_groups(self, indexer_id: str | None = None) -> list[IndexerSitesGroup]:
        request_started_at = time.perf_counter()
        groups: list[IndexerSitesGroup] = []
        indexers = settings_service.list_indexers()
        if indexer_id:
            indexers = [item for item in indexers if item.id == indexer_id]
            if not indexers:
                raise ConfigurationException("backendErrors.config.indexerNotFound", params={"id": indexer_id})

        for indexer in indexers:
            groups.append(await self._build_indexer_group(indexer))

        logger.debug(
            "Indexer sites catalog completed: groups=%s total_ms=%.1f",
            len(groups),
            (time.perf_counter() - request_started_at) * 1000,
        )
        return groups

    async def _build_indexer_group(self, indexer: IndexerProviderConfig) -> IndexerSitesGroup:
        settings_by_site = {item.site_id: item for item in indexer.site_settings}
        indexer_started_at = time.perf_counter()

        try:
            client = indexer_gateway.client_factory.create_client_with_config(ClientType(indexer.type), indexer)
        except (RuntimeError, ValueError) as e:
            return self._offline_group(indexer, settings_by_site, indexer_started_at, e)

        try:
            try:
                list_started_at = time.perf_counter()
                live_sites = await client.list_sites()
                list_duration_ms = (time.perf_counter() - list_started_at) * 1000
                caps_started_at = time.perf_counter()
                capabilities_by_site = {
                    site.id: await client.get_site_capabilities(site.id)
                    for site in live_sites
                }
                caps_duration_ms = (time.perf_counter() - caps_started_at) * 1000
            finally:
                await client.close()
            items = self._build_live_site_items(live_sites, settings_by_site, capabilities_by_site)
            live_site_ids = {site.id for site in live_sites}
            items.extend(self._build_saved_only_site_items(settings_by_site, live_site_ids))
            items.sort(key=lambda item: (0 if item.is_live else 1, (item.site_name or item.site_id).lower()))
            logger.debug(
                "Indexer sites catalog group completed: indexer=%s live_sites=%s saved_only=%s list_ms=%.1f caps_ms=%.1f total_ms=%.1f",
                indexer.id,
                len(live_sites),
                len(items) - len(live_sites),
                list_duration_ms,
                caps_duration_ms,
                (time.perf_counter() - indexer_started_at) * 1000,
            )
            return IndexerSitesGroup(
                indexer_id=indexer.id,
                indexer_name=indexer.name,
                sites=items,
                error=None,
            )
        except (RuntimeError, ValueError) as e:
            return self._offline_group(indexer, settings_by_site, indexer_started_at, e)

    def _offline_group(
        self,
        indexer: IndexerProviderConfig,
        settings_by_site: dict[str, IndexerSiteSetting],
        indexer_started_at: float,
        error: Exception,
    ) -> IndexerSitesGroup:
        offline_items = self._build_saved_only_site_items(settings_by_site, set())
        offline_items.sort(key=lambda item: (item.site_name or item.site_id).lower())
        logger.warning(
            "Indexer sites catalog group failed: indexer=%s saved_only=%s total_ms=%.1f error=%s",
            indexer.id,
            len(offline_items),
            (time.perf_counter() - indexer_started_at) * 1000,
            error,
        )
        return IndexerSitesGroup(
            indexer_id=indexer.id,
            indexer_name=indexer.name,
            sites=offline_items,
            error=f"Failed to fetch indexer site list: {str(error)}",
        )

    def _build_live_site_items(
        self,
        live_sites: list[SiteInfo],
        settings_by_site: dict[str, IndexerSiteSetting],
        live_caps_by_site: dict[str, SiteSearchCapabilities],
    ) -> list[IndexerSiteStatusItem]:
        return [
            self._build_site_item(
                site=site,
                is_live=True,
                setting=settings_by_site[site.id] if site.id in settings_by_site else None,
                capabilities=live_caps_by_site[site.id] if site.id in live_caps_by_site else None,
            )
            for site in live_sites
        ]

    def _build_saved_only_site_items(
        self,
        settings_by_site: dict[str, IndexerSiteSetting],
        live_site_ids: set[str],
    ) -> list[IndexerSiteStatusItem]:
        items: list[IndexerSiteStatusItem] = []
        for site_id, setting in settings_by_site.items():
            if site_id in live_site_ids:
                continue
            items.append(
                self._build_site_item(
                    site=SiteInfo(
                        id=site_id,
                        name=site_id,
                        description="Saved site setting is not currently present in the synced site list",
                        language="",
                        type="unknown",
                    ),
                    is_live=False,
                    setting=setting,
                    capabilities=None,
                )
            )
        return items

    def _build_site_item(
        self,
        *,
        site: SiteInfo,
        is_live: bool,
        setting: IndexerSiteSetting | None,
        capabilities: SiteSearchCapabilities | None,
    ) -> IndexerSiteStatusItem:
        settings_payload = self._to_settings_payload(setting)
        capabilities_payload = self._to_capabilities_payload(capabilities)
        return IndexerSiteStatusItem(
            site_id=site.id,
            site_name=site.name or site.description or site.id,
            description=site.description,
            language=site.language,
            type=site.type,
            is_live=is_live,
            settings=settings_payload,
            capabilities=capabilities_payload,
            effective=self._to_effective_payload(
                is_live=is_live,
                settings=settings_payload,
                capabilities=capabilities_payload,
            ),
        )

    def _to_settings_payload(self, setting: IndexerSiteSetting | None) -> IndexerSiteSettingsPayload:
        if setting is None:
            return IndexerSiteSettingsPayload()
        return IndexerSiteSettingsPayload(
            enabled=setting.enabled,
            disable_title=setting.disable_title,
            disable_imdb=setting.disable_imdb,
            disable_douban=setting.disable_douban,
            media_types=setting.media_types,
        )

    def _to_capabilities_payload(
        self,
        capabilities: SiteSearchCapabilities | None,
    ) -> IndexerSiteCapabilitiesPayload:
        caps = capabilities or SiteSearchCapabilities()
        return IndexerSiteCapabilitiesPayload(
            supports_title=caps.supports_q,
            supports_imdb=caps.supports_imdbid,
            supports_douban=caps.supports_doubanid,
            supports_movie=caps.supports_movie,
            supports_tv=caps.supports_tv,
        )

    def _to_effective_payload(
        self,
        *,
        is_live: bool,
        settings: IndexerSiteSettingsPayload,
        capabilities: IndexerSiteCapabilitiesPayload,
    ) -> IndexerSiteEffectivePayload:
        enabled = settings.enabled and is_live
        uses_manual_media_types = settings.media_types is not None
        caps = SiteSearchCapabilities(
            supports_movie=capabilities.supports_movie,
            supports_tv=capabilities.supports_tv,
        )
        supported_media_types = effective_media_types_from_caps(caps, settings.media_types)
        return IndexerSiteEffectivePayload(
            enabled=enabled,
            use_title=enabled and capabilities.supports_title and not settings.disable_title,
            use_imdb=enabled and capabilities.supports_imdb and not settings.disable_imdb,
            use_douban=enabled and capabilities.supports_douban and not settings.disable_douban,
            supports_movie=MediaType.movie in supported_media_types,
            supports_tv=MediaType.tv in supported_media_types,
            media_types_source="manual" if uses_manual_media_types else "auto",
        )


indexer_site_catalog_service = IndexerSiteCatalogService()
