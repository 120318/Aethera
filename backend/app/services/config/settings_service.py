from __future__ import annotations

import logging
import os
import time

from app.core.logging_config import apply_logging_config_from_settings
from app.core.request_perf_context import db_perf_source
from app.core.storage_paths import get_download_root, get_library_root, get_log_dir
from app.db.repositories.auth_session_repository import AuthSessionRepository
from app.db.repositories.settings_sqlite_repository import SettingsSqliteRepository
from app.schemas.config import (
    AddonsConfig,
    AppConfig,
    AuthConfig,
    BrowseSource,
    Tag,
    DirectoryConfig,
    DoubanConfig,
    DownloadConfig,
    DownloaderConfig,
    IndexerConfig,
    IndexerProviderConfig,
    LoggingConfig,
    MediaServerProviderConfig,
    NamingTemplateConfig,
    SchedulerConfig,
    ServicesConfig,
    SystemConfig,
    Template,
    TMDBConfig,
)
from app.schemas.domain.filter_config import FilterConfig
from app.schemas.domain.media_types import MediaType
from app.schemas.runtime.settings_runtime import ObjectConfigSnapshot
from app.schemas.runtime.indexer_runtime import IndexerSiteSearchOutcome
from app.schemas.runtime.indexer_site_health import IndexerSiteHealthStatus
from app.schemas.runtime.directory_integrity import DirectoryIntegrityPolicy
from app.services.config.tag_settings import TagSettings
from app.services.config.directory_settings import DirectorySettings
from app.services.config.download_client_settings import DownloadClientSettings
from app.services.config.filter_preset_settings import FilterPresetSettings
from app.services.config.indexer_client_settings import IndexerClientSettings, IndexerSiteHealthState
from app.services.config.media_server_settings import MediaServerSettings
from app.services.config.naming_template_settings import NamingTemplateSettings
from app.services.config.settings_object_operations import SettingsObjectOperations
from app.services.config.quality_profile_settings import QualityProfileSettings
from app.services.config.settings_config_builder import SettingsConfigBuilder
from app.utils.fs_utils import ensure_directory

logger = logging.getLogger("app.services.settings")

CONFIG_SECTION_SERVICES = "services"
CONFIG_SECTION_SYSTEM = "system"
CONFIG_SECTION_ADDONS = "addons"
CONFIG_SECTION_AUTH = "auth"


class SettingsService(SettingsObjectOperations):
    def __init__(self) -> None:
        self._sqlite_repo = SettingsSqliteRepository()
        self._auth_session_repo = AuthSessionRepository()
        self._download_clients = DownloadClientSettings(self._sqlite_repo)
        self._indexer_clients = IndexerClientSettings(self._sqlite_repo)
        self._indexer_site_health = IndexerSiteHealthState()
        self._media_servers = MediaServerSettings(self._sqlite_repo)
        self._naming_templates = NamingTemplateSettings(self._sqlite_repo)
        self._directories = DirectorySettings(self._sqlite_repo, self._naming_templates, self._create_storage_dirs)
        self._quality_profiles = QualityProfileSettings(self._sqlite_repo)
        self._filter_presets = FilterPresetSettings(self._sqlite_repo, self._quality_profiles)
        self._tags = TagSettings(self._sqlite_repo)
        self._config_builder = SettingsConfigBuilder(
            self._download_clients,
            self._indexer_clients,
            self._media_servers,
            self._directories,
            self._naming_templates,
            self._filter_presets,
            self._quality_profiles,
            self._tags,
        )
        self._initialized = False

    def ensure_initialized(self) -> AppConfig:
        self._ensure_base_sections()
        self._naming_templates.ensure_defaults()
        self._quality_profiles.ensure_defaults()
        self._filter_presets.ensure_defaults()
        self._tags.ensure_defaults()
        merged = self._config_builder.build_full_config(self._load_base_config())
        self._create_storage_dirs(merged)
        self._initialized = True
        return merged

    def get(self) -> AppConfig:
        if not self._initialized:
            return self.ensure_initialized()
        config = self._config_builder.build_full_config(self._load_base_config())
        self._create_storage_dirs(config)
        return config

    def save_config(self, data: AppConfig) -> None:
        self.ensure_initialized()
        self._download_clients.validate_immutable_fields(list(data.downloaders))
        self._directories.validate_immutable_fields(list(data.directories))
        normalized = self._naming_templates.normalize_defaults(data)
        self._config_builder.persist_objects(normalized)
        self._persist_base_sections(normalized)
        self._create_storage_dirs(normalized)

    def list_downloaders(self, enabled_only: bool = False) -> list[DownloaderConfig]:
        return self._download_clients.list(enabled_only=enabled_only)

    def list_directories(self) -> list[DirectoryConfig]:
        return self._directories.list()

    def list_directory_integrity_policies(self) -> list[DirectoryIntegrityPolicy]:
        directory_ids = {directory.id for directory in self.list_directories()}
        policies = [
            self._normalize_directory_integrity_policy(policy)
            for policy in self._sqlite_repo.directory_integrity_policies.list()
            if policy.directory_id in directory_ids
        ]
        existing_ids = {policy.directory_id for policy in policies}
        return policies + [DirectoryIntegrityPolicy.default_for_directory(directory_id) for directory_id in sorted(directory_ids - existing_ids)]

    def update_directory_integrity_policies(self, policies: list[DirectoryIntegrityPolicy]) -> list[DirectoryIntegrityPolicy]:
        directory_ids = {directory.id for directory in self.list_directories()}
        normalized: dict[str, DirectoryIntegrityPolicy] = {}
        for policy in policies:
            if policy.directory_id in directory_ids:
                normalized[policy.directory_id] = policy
        self._sqlite_repo.directory_integrity_policies.replace(list(normalized.values()))
        return self.list_directory_integrity_policies()

    @staticmethod
    def _normalize_directory_integrity_policy(policy: DirectoryIntegrityPolicy) -> DirectoryIntegrityPolicy:
        issue_types = set(policy.issue_types or [])
        return policy.model_copy(update={"issue_types": sorted(issue_types, key=lambda item: item.value)})

    def list_indexers(self) -> list[IndexerProviderConfig]:
        return self._indexer_clients.list()

    def list_enabled_indexers(self) -> list[IndexerConfig]:
        return self._indexer_clients.list_enabled()

    def list_media_servers(self) -> list[MediaServerProviderConfig]:
        return self._media_servers.list()

    def list_naming_templates(self) -> list[NamingTemplateConfig]:
        return self._naming_templates.list()

    def list_filter_presets(self) -> list[FilterConfig]:
        return self._filter_presets.list()

    def list_quality_profiles(self):
        return self._quality_profiles.list()

    def list_tags(self) -> list[Tag]:
        return self._tags.list()

    def get_directory_by_id(self, directory_id: str) -> DirectoryConfig | None:
        return self._directories.get_by_id(directory_id)

    def get_default_directory(self, media_type: MediaType) -> DirectoryConfig | None:
        return self._directories.get_default(media_type)

    def get_default_media_server_id(self) -> str | None:
        return self._media_servers.get_default_id()

    def get_default_downloader_id(self) -> str | None:
        return self._download_clients.get_default_id()

    def get_default_indexer_id(self) -> str | None:
        return self._indexer_clients.get_default_id()

    def record_indexer_site_search_outcomes(self, outcomes: list[IndexerSiteSearchOutcome]) -> None:
        self._indexer_site_health.record_outcomes(outcomes)

    def get_indexer_site_health_map(self) -> dict[str, list[IndexerSiteHealthStatus]]:
        return dict(self._indexer_site_health.get_status_map_by_indexer())

    def list_indexer_site_health(self, indexer_id: str) -> list[IndexerSiteHealthStatus]:
        return self._indexer_site_health.list_by_indexer(indexer_id)

    def get_template_by_id(self, template_id: str) -> Template | None:
        return self._naming_templates.get_template_by_id(template_id)

    def get_template_by_directory_id(self, directory_id: str) -> Template | None:
        return self._directories.get_template_by_directory_id(directory_id)

    def get_filter(self, filter_id: str) -> FilterConfig | None:
        return self._filter_presets.find(filter_id)

    def get_quality_profile(self, profile_id: str):
        return self._quality_profiles.find(profile_id)

    def get_default_quality_profile(self):
        return self._quality_profiles.get_default()

    def get_tag(self, tag_id: str) -> Tag | None:
        return self._tags.find(tag_id)

    def update_addons_config(self, addons_config: AddonsConfig) -> AddonsConfig:
        config = self._current_config()
        config.addons = addons_config
        self.save_config(config)
        return config.addons

    def update_services_config(self, services_config: ServicesConfig) -> ServicesConfig:
        config = self._current_config()
        self._apply_services_config(config, services_config)
        self.save_config(config)
        self._clear_client_cache()
        return self._build_services_config(config)

    def get_services_config(self) -> ServicesConfig:
        with db_perf_source("settings.services_config"):
            return self._build_services_config(self._current_config())

    def get_base_services_config(self) -> ServicesConfig:
        return self._build_services_config(self._load_base_config())

    def get_addons_config(self) -> AddonsConfig:
        return self._load_base_config().addons

    def update_tmdb_config(self, tmdb_config: TMDBConfig) -> TMDBConfig:
        config = self._current_config()
        config.themoviedb = tmdb_config
        self.save_config(config)
        self._clear_client_cache()
        return config.themoviedb

    def update_douban_config(self, douban_config: DoubanConfig) -> DoubanConfig:
        config = self._current_config()
        config.douban.discover_lists = list(douban_config.discover_lists)
        config.douban.proxy_images = douban_config.proxy_images
        self.save_config(config)
        self._clear_client_cache()
        return config.douban

    def update_browse_source(self, browse_source: BrowseSource) -> ServicesConfig:
        config = self._current_config()
        config.browse_source = browse_source
        self.save_config(config)
        return self._build_services_config(config)

    def update_system_config(self, system_config: SystemConfig) -> SystemConfig:
        config = self._current_config()
        self._apply_system_config(config, system_config)
        self.save_config(config)
        apply_logging_config_from_settings(self._build_system_config(config))
        return self._build_system_config(config)

    def get_system_config(self) -> SystemConfig:
        with db_perf_source("settings.system_config"):
            return self._build_system_config(self._current_config())

    def get_base_system_config(self) -> SystemConfig:
        return self._build_system_config(self._load_base_config())

    def get_logging_config(self) -> SystemConfig:
        return SystemConfig(logging=self._load_base_config().logging)

    def is_onboarding_enabled(self) -> bool:
        return bool(self._load_base_config().onboarding_enabled)

    def get_runtime_value(self, key: str) -> str | None:
        return self._sqlite_repo.get_default(key)

    def set_runtime_value(self, key: str, value: str | None) -> None:
        self._sqlite_repo.set_default(key, value)

    def get_scheduler_config(self) -> SchedulerConfig:
        return self._load_base_config().scheduler

    def get_downloaders_tab_config(self):
        base_config = self._load_base_config()
        return {
            "download": base_config.download.model_copy(update={"default_downloader_id": self.get_default_downloader_id()}),
            "downloaders": self.list_downloaders(),
        }

    def get_indexers_tab_config(self):
        return {"indexers": self.list_indexers()}

    def get_media_servers_tab_config(self):
        return {
            "media_servers": self.list_media_servers(),
            "default_media_server_id": self.get_default_media_server_id(),
        }

    def get_directories_tab_config(self):
        naming_templates = self.list_naming_templates()
        config = AppConfig(naming_templates=naming_templates)
        return {
            "directories": self.list_directories(),
            "downloaders": self.list_downloaders(),
            "media_servers": self.list_media_servers(),
            "naming_templates": naming_templates,
            "default_movie_template_id": self._naming_templates.resolve_default_id(config, "movie"),
            "default_tv_template_id": self._naming_templates.resolve_default_id(config, "tv"),
        }

    def get_naming_tab_config(self):
        naming_templates = self.list_naming_templates()
        config = AppConfig(naming_templates=naming_templates)
        return {
            "naming_templates": naming_templates,
            "default_movie_template_id": self._naming_templates.resolve_default_id(config, "movie"),
            "default_tv_template_id": self._naming_templates.resolve_default_id(config, "tv"),
        }

    def get_metadata_tab_config(self):
        base_config = self._load_base_config()
        return {
            "browse_source": base_config.browse_source,
            "themoviedb": base_config.themoviedb,
            "douban": base_config.douban,
        }

    def get_addons_tab_config(self) -> AddonsConfig:
        return self._load_base_config().addons

    def get_system_tab_config(self):
        config = self._load_base_config()
        download = config.download.model_copy(update={"default_downloader_id": self.get_default_downloader_id()})
        return {
            "auth": {
                "enabled": bool(config.auth.enabled),
                "session_ttl_seconds": config.auth.session_ttl_seconds,
            },
            "download": download,
            "logging": config.logging,
            "scheduler": config.scheduler,
        }

    def update_scheduler_config(self, scheduler_config: SchedulerConfig) -> SystemConfig:
        config = self._current_config()
        config.scheduler = scheduler_config
        self.save_config(config)
        return self._build_system_config(config)

    def update_logging_config(self, logging_config: LoggingConfig) -> SystemConfig:
        config = self._current_config()
        config.logging = logging_config
        self.save_config(config)
        apply_logging_config_from_settings(self._build_system_config(config))
        return self._build_system_config(config)

    def update_download_config(self, download_config: DownloadConfig) -> SystemConfig:
        config = self._current_config()
        config.download = self._download_config_preserving_default(download_config)
        self.save_config(config)
        self._clear_client_cache()
        return self._build_system_config(config)

    def update_auth_config(self, enabled: bool, session_ttl_seconds: int) -> AuthConfig:
        config = self._current_config()
        config.auth.enabled = enabled
        ttl = int(session_ttl_seconds or 0)
        config.auth.session_ttl_seconds = 0 if ttl == 0 else (ttl if ttl > 0 else 86400)
        self.save_config(config)
        now = time.time()
        expires_at = 0.0 if config.auth.session_ttl_seconds == 0 else now + config.auth.session_ttl_seconds
        self._auth_session_repo.update_active_expirations(now, expires_at)
        return config.auth

    def get_auth_config(self) -> AuthConfig:
        with db_perf_source("settings.auth_config"):
            return self._current_config().auth

    def get_base_auth_config(self) -> AuthConfig:
        return self._load_base_config().auth

    def update_auth_password_hash(self, password_hash: str | None) -> AuthConfig:
        config = self._current_config()
        config.auth.password_hash = password_hash
        self.save_config(config)
        return config.auth

    def get_object_config(self) -> ObjectConfigSnapshot:
        with db_perf_source("settings.object_config"):
            return self._config_builder.build_object_snapshot(self._current_config())

    def get_default_movie_template_id(self) -> str | None:
        return self._current_config().default_movie_template_id

    def get_default_tv_template_id(self) -> str | None:
        return self._current_config().default_tv_template_id

    def delete_directory(self, directory_id: str) -> None:
        self._directories.delete(directory_id)
        self._remove_directory_runtime_references(directory_id)

    def migrate_directory_references(self, source_directory_id: str, target_directory_id: str) -> None:
        self._migrate_directory_integrity_policy(source_directory_id, target_directory_id)
        self._migrate_danmu_directory_reference(source_directory_id, target_directory_id)

    def _current_config(self) -> AppConfig:
        if not self._initialized:
            return self.ensure_initialized()
        config = self._config_builder.build_full_config(self._load_base_config())
        self._create_storage_dirs(config)
        return config

    def _remove_directory_runtime_references(self, directory_id: str) -> None:
        policies = [policy for policy in self._sqlite_repo.directory_integrity_policies.list() if policy.directory_id != directory_id]
        self._sqlite_repo.directory_integrity_policies.replace(policies)
        config = self._current_config()
        next_directory_ids = [item for item in config.addons.danmu.directory_ids if item != directory_id]
        if next_directory_ids != config.addons.danmu.directory_ids:
            config.addons.danmu.directory_ids = next_directory_ids
            self.save_config(config)

    def _migrate_directory_integrity_policy(self, source_directory_id: str, target_directory_id: str) -> None:
        policies = self._sqlite_repo.directory_integrity_policies.list()
        source_policy = next((policy for policy in policies if policy.directory_id == source_directory_id), None)
        target_exists = any(policy.directory_id == target_directory_id for policy in policies)
        next_policies = [policy for policy in policies if policy.directory_id != source_directory_id]
        if source_policy and not target_exists:
            next_policies.append(source_policy.model_copy(update={"directory_id": target_directory_id}))
        self._sqlite_repo.directory_integrity_policies.replace(next_policies)

    def _migrate_danmu_directory_reference(self, source_directory_id: str, target_directory_id: str) -> None:
        config = self._current_config()
        directory_ids = list(config.addons.danmu.directory_ids)
        if source_directory_id not in directory_ids:
            return
        next_directory_ids = [item for item in directory_ids if item != source_directory_id]
        if target_directory_id not in next_directory_ids:
            next_directory_ids.append(target_directory_id)
        config.addons.danmu.directory_ids = next_directory_ids
        self.save_config(config)

    def _load_base_config(self) -> AppConfig:
        base_config = self._config_builder.build_base_config(self._build_default_base_config())
        return self._apply_stored_sections(base_config)

    def _build_default_base_config(self) -> AppConfig:
        config = AppConfig()
        config.auth.enabled = True
        config.logging.dir = str(get_log_dir())
        backend_mode = (os.getenv("BACKEND_MODE", "dev") or "dev").lower()
        config.logging.level = "DEBUG" if backend_mode != "prod" else "INFO"
        return config

    def _apply_stored_sections(self, config: AppConfig) -> AppConfig:
        services_payload = self._sqlite_repo.get_section(CONFIG_SECTION_SERVICES)
        if type(services_payload) is dict:
            self._apply_services_config(config, ServicesConfig.model_validate(services_payload))

        system_payload = self._sqlite_repo.get_section(CONFIG_SECTION_SYSTEM)
        if type(system_payload) is dict:
            self._apply_system_config(config, SystemConfig.model_validate(system_payload))

        addons_payload = self._sqlite_repo.get_section(CONFIG_SECTION_ADDONS)
        if type(addons_payload) is dict:
            config.addons = AddonsConfig.model_validate(addons_payload)

        auth_payload = self._sqlite_repo.get_section(CONFIG_SECTION_AUTH)
        if type(auth_payload) is dict:
            config.auth = AuthConfig.model_validate(auth_payload)

        return config

    def _persist_base_sections(self, config: AppConfig) -> None:
        self._sqlite_repo.replace_sections(
            {
                CONFIG_SECTION_SERVICES: self._build_services_config(config).model_dump(mode="json"),
                CONFIG_SECTION_SYSTEM: self._build_system_config(config).model_dump(mode="json"),
                CONFIG_SECTION_ADDONS: config.addons.model_dump(mode="json"),
                CONFIG_SECTION_AUTH: config.auth.model_dump(mode="json"),
            }
        )

    def _ensure_base_sections(self) -> None:
        default_config = self._config_builder.build_base_config(self._build_default_base_config())
        sections = {}
        if self._sqlite_repo.get_section(CONFIG_SECTION_SERVICES) is None:
            sections[CONFIG_SECTION_SERVICES] = self._build_services_config(default_config).model_dump(mode="json")
        if self._sqlite_repo.get_section(CONFIG_SECTION_SYSTEM) is None:
            sections[CONFIG_SECTION_SYSTEM] = self._build_system_config(default_config).model_dump(mode="json")
        if self._sqlite_repo.get_section(CONFIG_SECTION_ADDONS) is None:
            sections[CONFIG_SECTION_ADDONS] = default_config.addons.model_dump(mode="json")
        if self._sqlite_repo.get_section(CONFIG_SECTION_AUTH) is None:
            sections[CONFIG_SECTION_AUTH] = default_config.auth.model_dump(mode="json")
        if sections:
            self._sqlite_repo.replace_sections(sections)

    def _build_system_config(self, config: AppConfig) -> SystemConfig:
        return SystemConfig(
            cache=config.cache,
            scheduler=config.scheduler,
            download=config.download,
            library=config.library,
            logging=config.logging,
            onboarding_enabled=config.onboarding_enabled,
        )

    def _apply_system_config(self, config: AppConfig, system_config: SystemConfig) -> None:
        config.cache, config.scheduler = system_config.cache, system_config.scheduler
        config.download = self._download_config_preserving_default(system_config.download)
        config.library, config.logging, config.onboarding_enabled = system_config.library, system_config.logging, system_config.onboarding_enabled

    def _download_config_preserving_default(self, download_config: DownloadConfig) -> DownloadConfig:
        if download_config.default_downloader_id:
            return download_config
        return download_config.model_copy(update={"default_downloader_id": self.get_default_downloader_id()})

    def _build_services_config(self, config: AppConfig) -> ServicesConfig:
        return ServicesConfig(browse_source=config.browse_source, douban=config.douban, themoviedb=config.themoviedb)

    def _apply_services_config(self, config: AppConfig, services_config: ServicesConfig) -> None:
        config.browse_source = services_config.browse_source
        config.douban.discover_lists = list(services_config.douban.discover_lists)
        config.douban.proxy_images = services_config.douban.proxy_images
        config.themoviedb = services_config.themoviedb

    def _create_storage_dirs(self, config: AppConfig) -> None:
        ensure_directory(get_library_root())
        ensure_directory(get_download_root())
        ensure_directory(get_log_dir())
        for directory in config.directories:
            if directory.path:
                ensure_directory(directory.path)
            if directory.download_path:
                ensure_directory(directory.download_path)

    def _clear_client_cache(self) -> None:
        from app.clients.factory import ClientFactory

        ClientFactory.clear_cache()


settings_service = SettingsService()
