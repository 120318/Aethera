from __future__ import annotations

from app.schemas.config import AppConfig
from app.schemas.runtime.settings_runtime import ObjectConfigSnapshot
from app.services.config.tag_settings import TagSettings
from app.services.config.directory_settings import DirectorySettings
from app.services.config.download_client_settings import DownloadClientSettings
from app.services.config.filter_preset_settings import FilterPresetSettings
from app.services.config.indexer_client_settings import IndexerClientSettings
from app.services.config.media_server_settings import MediaServerSettings
from app.services.config.naming_template_settings import NamingTemplateSettings
from app.services.config.quality_profile_settings import QualityProfileSettings


class SettingsConfigBuilder:
    def __init__(
        self,
        download_clients: DownloadClientSettings,
        indexer_clients: IndexerClientSettings,
        media_servers: MediaServerSettings,
        directories: DirectorySettings,
        naming_templates: NamingTemplateSettings,
        filter_presets: FilterPresetSettings,
        quality_profiles: QualityProfileSettings,
        tags: TagSettings,
    ) -> None:
        self._download_clients = download_clients
        self._indexer_clients = indexer_clients
        self._media_servers = media_servers
        self._directories = directories
        self._naming_templates = naming_templates
        self._filter_presets = filter_presets
        self._quality_profiles = quality_profiles
        self._tags = tags

    def build_full_config(self, base_config: AppConfig) -> AppConfig:
        config = AppConfig.model_validate(base_config.to_plain())
        config.downloaders = self._download_clients.list()
        config.directories = self._directories.list()
        config.indexers = self._indexer_clients.list()
        config.media_servers = self._media_servers.list()
        config.naming_templates = self._naming_templates.list()
        config.filter_presets = self._filter_presets.list()
        config.quality_profiles = self._quality_profiles.list()
        config.tags = self._tags.list()
        config.download.default_downloader_id = self._download_clients.get_default_id()
        config.default_media_server_id = self._media_servers.get_default_id()
        config.default_indexer_id = self._indexer_clients.get_default_id()
        config.default_movie_template_id = self._naming_templates.resolve_default_id(config, "movie")
        config.default_tv_template_id = self._naming_templates.resolve_default_id(config, "tv")
        config.library.default_movie_template_id = config.default_movie_template_id
        config.library.default_tv_template_id = config.default_tv_template_id
        return config

    def build_base_config(self, config: AppConfig) -> AppConfig:
        base_config = AppConfig.model_validate(config.to_plain())
        if base_config.__pydantic_extra__:
            base_config.__pydantic_extra__.pop("cache_ttl", None)
        base_config.downloaders = []
        base_config.directories = []
        base_config.indexers = []
        base_config.media_servers = []
        base_config.naming_templates = []
        base_config.filter_presets = []
        base_config.quality_profiles = []
        base_config.tags = []
        base_config.download.default_downloader_id = None
        base_config.default_media_server_id = None
        base_config.default_indexer_id = None
        base_config.default_movie_template_id = None
        base_config.default_tv_template_id = None
        base_config.library.default_movie_template_id = None
        base_config.library.default_tv_template_id = None
        return base_config

    def persist_objects(self, config: AppConfig) -> None:
        self._download_clients.replace_all(list(config.downloaders))
        self._directories.replace_all(list(config.directories))
        self._indexer_clients.replace_all(list(config.indexers))
        self._media_servers.replace_all(list(config.media_servers))
        self._naming_templates.replace_all(list(config.naming_templates))
        self._filter_presets.replace_all(list(config.filter_presets))
        self._quality_profiles.replace_all(list(config.quality_profiles))
        self._tags.replace_all(list(config.tags))
        if config.download.default_downloader_id:
            self._download_clients.set_default(config.download.default_downloader_id)
        else:
            self._download_clients.clear_default()
        if config.default_media_server_id:
            self._media_servers.set_default(config.default_media_server_id)
        else:
            self._media_servers.clear_default()
        if config.default_indexer_id:
            self._indexer_clients.set_default(config.default_indexer_id)
        else:
            self._indexer_clients.clear_default()

    def build_object_snapshot(self, config: AppConfig) -> ObjectConfigSnapshot:
        return ObjectConfigSnapshot(
            themoviedb=config.themoviedb,
            douban=config.douban,
            download=config.download,
            downloaders=self._download_clients.list(),
            indexers=self._indexer_clients.list(),
            media_servers=self._media_servers.list(),
            directories=self._directories.list(),
            naming_templates=self._naming_templates.list(),
            filter_presets=self._filter_presets.list(),
            quality_profiles=self._quality_profiles.list(),
            tags=self._tags.list(),
            default_media_server_id=config.default_media_server_id,
            default_indexer_id=config.default_indexer_id,
            default_movie_template_id=config.default_movie_template_id,
            default_tv_template_id=config.default_tv_template_id,
        )
