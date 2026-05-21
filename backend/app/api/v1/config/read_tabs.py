from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.config import (
    DirectoryConfig,
    DownloaderProviderConfig,
    DownloadConfig,
    DoubanConfig,
    AddonsConfig,
    IndexerProviderConfig,
    LoggingConfig,
    MediaServerProviderConfig,
    NamingTemplateConfig,
    BrowseSource,
    SchedulerConfig,
    TMDBConfig,
)
from app.services.config.settings_service import settings_service

router = APIRouter()


class DownloadersTabResponse(BaseModel):
    download: DownloadConfig
    downloaders: list[DownloaderProviderConfig]


class IndexersTabResponse(BaseModel):
    indexers: list[IndexerProviderConfig]


class MediaServersTabResponse(BaseModel):
    media_servers: list[MediaServerProviderConfig]
    default_media_server_id: str | None = None


class DirectoriesTabResponse(BaseModel):
    directories: list[DirectoryConfig]
    downloaders: list[DownloaderProviderConfig]
    media_servers: list[MediaServerProviderConfig]
    naming_templates: list[NamingTemplateConfig]
    default_movie_template_id: str | None = None
    default_tv_template_id: str | None = None


class NamingTabResponse(BaseModel):
    naming_templates: list[NamingTemplateConfig]
    default_movie_template_id: str | None = None
    default_tv_template_id: str | None = None


class MetadataTabResponse(BaseModel):
    browse_source: BrowseSource
    themoviedb: TMDBConfig
    douban: DoubanConfig


class AddonsTabResponse(BaseModel):
    addons: AddonsConfig


class SystemTabAuthResponse(BaseModel):
    enabled: bool = False
    session_ttl_seconds: int = 86400


class SystemTabResponse(BaseModel):
    auth: SystemTabAuthResponse
    download: DownloadConfig
    logging: LoggingConfig
    scheduler: SchedulerConfig


@router.get("/config/tab/downloaders", response_model=DownloadersTabResponse)
def get_downloaders_tab() -> DownloadersTabResponse:
    payload = settings_service.get_downloaders_tab_config()
    return DownloadersTabResponse(**payload)


@router.get("/config/tab/indexers", response_model=IndexersTabResponse)
def get_indexers_tab() -> IndexersTabResponse:
    payload = settings_service.get_indexers_tab_config()
    return IndexersTabResponse(**payload)


@router.get("/config/tab/media-servers", response_model=MediaServersTabResponse)
def get_media_servers_tab() -> MediaServersTabResponse:
    payload = settings_service.get_media_servers_tab_config()
    return MediaServersTabResponse(**payload)


@router.get("/config/tab/directories", response_model=DirectoriesTabResponse)
def get_directories_tab() -> DirectoriesTabResponse:
    payload = settings_service.get_directories_tab_config()
    return DirectoriesTabResponse(**payload)


@router.get("/config/tab/naming", response_model=NamingTabResponse)
def get_naming_tab() -> NamingTabResponse:
    payload = settings_service.get_naming_tab_config()
    return NamingTabResponse(**payload)


@router.get("/config/tab/metadata", response_model=MetadataTabResponse)
def get_metadata_tab() -> MetadataTabResponse:
    payload = settings_service.get_metadata_tab_config()
    return MetadataTabResponse(**payload)


@router.get("/config/tab/addons", response_model=AddonsTabResponse)
def get_addons_tab() -> AddonsTabResponse:
    payload = settings_service.get_addons_tab_config()
    return AddonsTabResponse(addons=payload)


@router.get("/config/tab/system", response_model=SystemTabResponse)
def get_system_tab() -> SystemTabResponse:
    payload = settings_service.get_system_tab_config()
    return SystemTabResponse(**payload)
