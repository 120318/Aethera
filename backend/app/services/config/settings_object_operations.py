from __future__ import annotations

from app.schemas.config import DirectoryConfig, DownloaderConfig, IndexerProviderConfig, MediaServerProviderConfig, NamingTemplateConfig, Tag
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.schemas.runtime.settings_runtime import SettingsUsage


class SettingsObjectOperations:
    def create_filter(self, name: str, filters: SubscriptionFilters, quality_profile_id: str | None = None, active_default: bool = False):
        return self._filter_presets.create(name, filters, quality_profile_id, active_default)

    def update_filter(self, filter_id: str, name: str | None = None, filters: SubscriptionFilters | None = None, quality_profile_id: str | None = None, active_default: bool | None = None):
        return self._filter_presets.update(filter_id, name, filters, quality_profile_id, active_default)

    def delete_filter(self, filter_id: str) -> bool:
        return self._filter_presets.delete(filter_id)

    def create_quality_profile(self, *, name: str, ranking, min_score: int | None = None, tag_scores: dict[str, int] | None = None, active_default: bool = False):
        return self._quality_profiles.create(name, ranking, min_score, tag_scores, active_default)

    def update_quality_profile(self, profile_id: str, **updates):
        return self._quality_profiles.update(profile_id, **updates)

    def delete_quality_profile(self, profile_id: str) -> bool:
        filter_refs = [item.name for item in self.list_filter_presets() if item.quality_profile_id == profile_id]
        return self._quality_profiles.delete(profile_id, filter_refs)

    def create_tag(self, name: str, include_keywords: list[str] | None = None, exclude_keywords: list[str] | None = None, regex: str | None = None) -> Tag:
        return self._tags.create(name, include_keywords, exclude_keywords, regex)

    def update_tag(self, tag_id: str, name: str | None = None, include_keywords: list[str] | None = None, exclude_keywords: list[str] | None = None, regex: str | None = None) -> Tag | None:
        return self._tags.update(tag_id, name, include_keywords, exclude_keywords, regex)

    def delete_tag(self, tag_id: str) -> bool:
        return self._tags.delete(tag_id)

    def create_downloader(self, downloader: DownloaderConfig) -> DownloaderConfig:
        created = self._download_clients.create(downloader)
        self._clear_client_cache()
        return created

    def update_downloader(self, downloader_id: str, downloader: DownloaderConfig) -> DownloaderConfig:
        updated = self._download_clients.update(downloader_id, downloader)
        self._clear_client_cache()
        return updated

    def delete_downloader(self, downloader_id: str) -> None:
        self._download_clients.delete(downloader_id)
        self._clear_client_cache()

    def set_default_downloader(self, downloader_id: str) -> None:
        self._download_clients.set_default(downloader_id)
        self._clear_client_cache()

    def clear_default_downloader(self) -> None:
        self._download_clients.clear_default()
        self._clear_client_cache()

    def create_indexer(self, indexer: IndexerProviderConfig) -> IndexerProviderConfig:
        created = self._indexer_clients.create(indexer)
        self._clear_client_cache()
        return created

    def update_indexer(self, indexer_id: str, indexer: IndexerProviderConfig) -> IndexerProviderConfig:
        updated = self._indexer_clients.update(indexer_id, indexer)
        self._clear_client_cache()
        return updated

    def delete_indexer(self, indexer_id: str) -> None:
        self._indexer_clients.delete(indexer_id)
        self._clear_client_cache()

    def reorder_indexers(self, indexers: list[IndexerProviderConfig]) -> None:
        self._indexer_clients.reorder(indexers)
        self._clear_client_cache()

    def create_media_server(self, media_server: MediaServerProviderConfig) -> MediaServerProviderConfig:
        created = self._media_servers.create(media_server)
        self._clear_client_cache()
        return created

    def update_media_server(self, media_server_id: str, media_server: MediaServerProviderConfig) -> MediaServerProviderConfig:
        updated = self._media_servers.update(media_server_id, media_server)
        self._clear_client_cache()
        return updated

    def delete_media_server(self, media_server_id: str) -> None:
        self._media_servers.delete(media_server_id)
        self._clear_client_cache()

    def set_default_media_server(self, media_server_id: str) -> None:
        self._media_servers.set_default(media_server_id)
        self._clear_client_cache()

    def clear_default_media_server(self) -> None:
        self._media_servers.clear_default()
        self._clear_client_cache()

    def create_naming_template(self, template: NamingTemplateConfig) -> NamingTemplateConfig:
        return self._naming_templates.create(template)

    def update_naming_template(self, template: NamingTemplateConfig) -> NamingTemplateConfig:
        return self._naming_templates.update(template)

    def delete_naming_template(self, template_id: str) -> None:
        self._naming_templates.delete(template_id)

    def set_default_naming_template(self, template_id: str) -> None:
        self._naming_templates.set_default(template_id)

    def clear_default_naming_template(self, template_type: str) -> None:
        self._naming_templates.clear_default(template_type)

    def create_directory(self, directory: DirectoryConfig) -> DirectoryConfig:
        return self._directories.create(directory)

    def update_directory(self, directory: DirectoryConfig) -> DirectoryConfig:
        return self._directories.update(directory)

    def set_default_directory(self, directory_id: str, media_type: MediaType) -> None:
        self._directories.set_default(directory_id, media_type)

    def get_downloader_usage(self, downloader_id: str) -> SettingsUsage:
        usage = self._download_clients.get_usage(downloader_id)
        usage.directory_count = sum(1 for item in self.list_directories() if item.downloader_id == downloader_id)
        return usage

    def get_directory_usage(self, directory_id: str) -> SettingsUsage:
        return self._directories.get_usage(directory_id)

    def validate_directory(self, directory: DirectoryConfig) -> list[str]:
        return self._directories.validate_directory(directory)

    def check_directory_permissions(self, path: str) -> dict[str, bool]:
        return self._directories.check_directory_permissions(path)

    def create_directory_if_not_exists(self, path: str) -> None:
        self._directories.create_directory_if_not_exists(path)
