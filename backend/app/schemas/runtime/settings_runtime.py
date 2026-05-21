from pydantic import BaseModel

from app.schemas.config import (
    Tag,
    DirectoryConfig,
    DoubanConfig,
    DownloaderProviderConfig,
    DownloadConfig,
    IndexerProviderConfig,
    MediaServerProviderConfig,
    NamingTemplateConfig,
    Template,
    TransferMode,
    TMDBConfig,
)
from app.schemas.domain.filter_config import FilterConfig
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.quality_profile import QualityProfile


class SettingsUsage(BaseModel):
    task_count: int = 0
    subscription_count: int = 0
    directory_count: int = 0
    library_file_count: int = 0
    is_default: bool = False


class ObjectConfigSnapshot(BaseModel):
    themoviedb: TMDBConfig
    douban: DoubanConfig
    download: DownloadConfig
    downloaders: list[DownloaderProviderConfig]
    indexers: list[IndexerProviderConfig]
    media_servers: list[MediaServerProviderConfig]
    directories: list[DirectoryConfig]
    naming_templates: list[NamingTemplateConfig]
    filter_presets: list[FilterConfig]
    quality_profiles: list[QualityProfile]
    tags: list[Tag]
    default_media_server_id: str | None = None
    default_indexer_id: str | None = None
    default_movie_template_id: str | None = None
    default_tv_template_id: str | None = None


class DirectoryDownloadTarget(BaseModel):
    directory_id: str
    downloader_id: str
    download_path: str
    download_category: str | None = None


class DirectoryDownloadBinding(BaseModel):
    directory_id: str
    downloader_id: str | None = None
    download_path: str | None = None
    download_category: str | None = None


class DirectoryLibraryTarget(BaseModel):
    directory_id: str
    media_type: MediaType
    library_path: str
    template: Template | None = None
    transfer_mode: TransferMode = TransferMode.HARDLINK
