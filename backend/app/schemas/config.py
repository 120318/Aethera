from __future__ import annotations

import uuid
import re
from pathlib import PurePath
from enum import Enum
from typing import Annotated, Literal

from app.schemas.domain.filter_config import FilterConfig
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.integration.site_models import IndexerSiteSetting
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TOKEN_PATTERN = re.compile(r"\{([^{}:]+?)(?::(0+))?\}")
CAMEL_BOUNDARY_PATTERN = re.compile(r"([a-z0-9])([A-Z])")
TOKEN_ALIASES = {
    "Movie Title": "title",
    "Series Title": "title",
    "Title": "title",
    "Year": "year",
    "ReleaseYear": "year",
    "tmdbId": "tmdb_id",
    "imdbId": "imdb_id",
    "Quality": "quality",
    "QualityFull": "quality",
    "Source": "source",
    "SourceShort": "source_short",
    "Release Group": "group",
    "ReleaseGroup": "group",
    "Group": "group",
    "seasonFolder": "season_folder",
    "Episode Title": "episode_title",
    "episodeTitle": "episode_title",
}


def normalize_template_token(token: str) -> str:
    token_text = str(token or "").strip()
    if not token_text:
        return ""
    if token_text in TOKEN_ALIASES:
        return TOKEN_ALIASES[token_text]
    normalized = CAMEL_BOUNDARY_PATTERN.sub(r"\1_\2", token_text)
    normalized = normalized.replace("-", " ").replace("/", " ")
    normalized = re.sub(r"\s+", "_", normalized.strip())
    return normalized.lower()


def migrate_template_tokens(template: str) -> str:
    def replace_token(match: re.Match[str]) -> str:
        token = normalize_template_token(match.group(1))
        pad = match.group(2)
        return f"{{{token}:{pad}}}" if pad else f"{{{token}}}"

    if not template:
        return ""
    return TOKEN_PATTERN.sub(replace_token, template)


def split_legacy_template(template: str) -> tuple[str, str]:
    if not template:
        return "", ""
    if "/" in template:
        return template.rsplit("/", 1)
    return "", template


def combine_template_parts(dir_template: str, file_template: str) -> str:
    directory = (dir_template or "").strip()
    file_name = (file_template or "").strip()
    if directory and file_name:
        return f"{directory}/{file_name}"
    return directory or file_name


class PathMapping(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(extra='ignore')

    remote_path: str = ""
    local_path: str = ""


class ClientConfigBase(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(extra='ignore')

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Field description")
    name: str = ""
    type: str = Field(..., description="Field description")
    enabled: bool = True


class DownloaderConfig(ClientConfigBase):
    """Internal helper."""
    path_mappings: list[PathMapping] = Field(default_factory=list, description="Field description")


class QBittorrentConfig(DownloaderConfig):
    """qBittorrenttext"""
    type: Literal["qbittorrent"] = "qbittorrent"
    url: str = ""
    username: str | None = None
    password: str | None = None


class RTorrentConfig(DownloaderConfig):
    """rTorrent XMLRPC downloader config."""
    type: Literal["rtorrent"] = "rtorrent"
    url: str = ""
    username: str | None = None
    password: str | None = None


class IndexerConfig(ClientConfigBase):
    """Internal helper."""
    priority: int = 0
    min_seeders: int = Field(default=0, description="Field description")
    url: str = ""
    api_key: str = ""
    site_settings: list[IndexerSiteSetting] = Field(default_factory=list)


class JackettConfig(IndexerConfig):
    """Jacketttext"""
    type: str = "jackett"


class ProwlarrConfig(IndexerConfig):
    """Prowlarrtext"""
    type: str = "prowlarr"


class MediaServerConfig(ClientConfigBase):
    """Internal helper."""


class MediaServerSyncConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    enabled: bool = False
    fetch_metadata: bool = True
    write_nfo: bool = True
    download_images: bool = True
    refresh_after_sync: bool = True
    interval_hours: int = 6
    batch_size: int = 20
    stale_after_days_movie: int = 30
    stale_after_days_tvshow: int = 7
    stale_after_days_ongoing_tv: int = 1
    max_backoff_hours: int = 24


class JellyfinConfig(MediaServerConfig):
    """Jellyfintext"""
    type: str = "jellyfin"
    url: str = ""
    api_key: str = ""
    path_mappings: list[PathMapping] = Field(default_factory=list, description="Field description")
    sync: MediaServerSyncConfig = Field(default_factory=MediaServerSyncConfig)


class DoubanConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    discover_lists: list[str] = Field(default_factory=lambda: ["movie_hot_gaia", "tv_hot", "tv_animation", "tv_variety_show"])
    proxy_images: bool = True


class TMDBConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    api_key: str = ""
    proxy_images: bool = False
    discover_lists: list[str] = Field(default_factory=lambda: ["movie_popular", "tv_popular", "trending_movie_week", "trending_tv_week"])


class BrowseSource(str, Enum):
    douban = "douban"
    tmdb = "tmdb"


class CacheConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    search_result_expire_seconds: int = 0
    search_empty_expire_seconds: int = 60
    search_error_expire_seconds: int = 60
    torrent_cache_max_age_seconds: int = 604800
    torrent_cache_max_files: int = 2000


class DownloadConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    default_path: str = ""
    movies_category: str = "movies"
    tv_category: str = "tv"
    anime_category: str = "anime"
    default_tag: str = "Aethera"
    default_downloader_id: str | None = None

    @field_validator("default_tag", mode="before")
    @classmethod
    def validate_default_tag(cls, value: object) -> str:
        return str(value or "").strip()


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    dir: str = "/config/logs"
    file: str = "backend.log"
    level: str = "INFO"
    server_retention_days: int = 7

    @field_validator("file")
    @classmethod
    def validate_file_name(cls, value: str) -> str:
        file_name = str(value or "").strip()
        if not file_name:
            return "backend.log"
        if "/" in file_name or "\\" in file_name:
            raise ValueError("logging.file must be a file name without path separators")
        if PurePath(file_name).name != file_name:
            raise ValueError("logging.file must not include a path")
        return file_name

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = str(value or "").strip().upper()
        if not normalized:
            return "INFO"
        if normalized not in {"TRACE", "DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError("logging.level must be one of TRACE, DEBUG, INFO, WARNING, ERROR")
        return normalized


class SchedulerConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    sync_active_downloads_interval_seconds: int = 30
    process_completed_tasks_interval_seconds: int = 60
    subscription_sweep_interval_seconds: int = 600
    schedule_refresh_sweep_interval_seconds: int = 3600
    directory_integrity_audit_interval_seconds: int = 21600
    cleanup_inactive_managed_media_profiles_interval_seconds: int = 86400
    cleanup_expired_sessions_interval_seconds: int = 3600


class NamingTemplateConfig(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(extra='ignore')

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Field description")
    name: str = ""  # Internal note.
    type: str = Field(..., description="Template media type, such as movie or tv")  # Internal note.
    dir_template: str = ""  # Internal note.
    file_template: str = ""  # Internal note.
    enabled: bool = True  # Internal note.
    is_default: bool = False  # Internal note.

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_template_fields(cls, data):
        raw = dict(data or {})
        legacy_template = raw.pop("template", None)
        dir_template = raw.get("dir_template")
        file_template = raw.get("file_template")
        if legacy_template is not None and not (dir_template or file_template):
            dir_template, file_template = split_legacy_template(str(legacy_template or ""))
        raw["dir_template"] = migrate_template_tokens(str(dir_template or ""))
        raw["file_template"] = migrate_template_tokens(str(file_template or ""))
        return raw


class MovieNamingTemplateConfig(NamingTemplateConfig):
    """Internal helper."""
    type: str = "movie"


class TVNamingTemplateConfig(NamingTemplateConfig):
    """Internal helper."""
    type: str = "tv"


class Template(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(extra='ignore')
    full_template: str = ""
    dir_template: str = ""
    file_template: str = ""

    @model_validator(mode="after")
    def populate_full_template(self) -> "Template":
        self.full_template = combine_template_parts(self.dir_template, self.file_template)
        return self


class TransferMode(str, Enum):
    HARDLINK = "hardlink"
    COPY = "copy"


class LibraryConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    naming_templates: list[NamingTemplateConfig] = Field(default_factory=list)
    default_movie_template_id: str | None = None
    default_tv_template_id: str | None = None


class DirectoryConfig(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(extra='ignore')

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Field description")
    name: str = ""  # Internal note.
    path: str = ""  # Internal note.
    media_type: MediaType = Field(default=MediaType.movie, description="Field description")
    enabled: bool = True  # Internal note.
    is_default: bool = False  # Internal note.
    media_server_id: str | None = None  # Internal note.
    downloader_id: str | None = None  # Internal note.
    movie_template_id: str | None = None  # Internal note.
    tv_template_id: str | None = None  # Internal note.
    download_path: str = ""  # Internal note.
    download_category: str | None = None
    transfer_mode: TransferMode = TransferMode.HARDLINK


class Tag(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(extra='ignore')

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Field description")
    name: str = Field(..., description="Field description")
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    regex: str = Field(default="")


# Provider-specific config unions
DownloaderProviderConfig = Annotated[QBittorrentConfig | RTorrentConfig, Field(discriminator="type")]
IndexerProviderConfig = IndexerConfig
MediaServerProviderConfig = JellyfinConfig
NamingTemplateVariant = NamingTemplateConfig


class AuthProviderClaimMappings(BaseModel):
    model_config = ConfigDict(extra='ignore')

    email: str = "email"
    username: str = "preferred_username"
    groups: str = "groups"


class AuthProviderConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Field description")
    type: str
    name: str = ""
    enabled: bool = True
    admin_emails: list[str] = Field(default_factory=list)


class OIDCAuthProviderConfig(AuthProviderConfig):
    model_config = ConfigDict(extra='ignore')

    type: str = "oidc"
    issuer_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    discovery_enabled: bool = True
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    userinfo_endpoint: str = ""
    jwks_uri: str = ""
    claim_mappings: AuthProviderClaimMappings = Field(default_factory=AuthProviderClaimMappings)
    allow_local_fallback: bool = True


class AuthAddonConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    enabled: bool = False
    default_provider_id: str | None = None
    providers: list[OIDCAuthProviderConfig] = Field(default_factory=list)


class NotificationChannelConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Field description")
    type: str = Field(..., description="Field description")
    name: str = ""
    enabled: bool = True
    event_patterns: list[str] = Field(
        default_factory=lambda: ["subscription.*", "follow.*", "media.*", "download.*"]
    )
    levels: list[str] = Field(default_factory=list)


class TelegramNotificationChannelConfig(NotificationChannelConfig):
    model_config = ConfigDict(extra='ignore')

    type: str = "telegram"
    bot_token: str = ""
    chat_id: str = ""


NotificationChannelVariant = TelegramNotificationChannelConfig


class NotificationsAddonConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    enabled: bool = False
    channels: list[NotificationChannelVariant] = Field(default_factory=list)


class DanmuAddonConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    enabled: bool = False
    directory_ids: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=lambda: ["iqiyi", "bilibili", "youku", "qq"])
    backfill_enabled: bool = True
    backfill_interval_seconds: int = 21600
    backfill_recent_days: int = 30
    backfill_missing_window_days: int = 90
    output_xml: bool = True
    output_ass: bool = True
    font_size: int = 60
    font_opacity_percent: int = 80
    scroll_duration_seconds: int = 20
    density_percent: int = 20
    display_area: Literal["top", "full"] = "top"
    duration_tolerance_seconds: int = 120

    @field_validator("font_size", mode="before")
    @classmethod
    def validate_font_size(cls, value: object) -> int:
        return min(max(int(value or 60), 18), 96)

    @field_validator("font_opacity_percent", mode="before")
    @classmethod
    def validate_font_opacity_percent(cls, value: object) -> int:
        return min(max(int(value or 80), 30), 100)

    @field_validator("scroll_duration_seconds", mode="before")
    @classmethod
    def validate_scroll_duration_seconds(cls, value: object) -> int:
        return min(max(int(value or 20), 5), 35)

    @field_validator("density_percent", mode="before")
    @classmethod
    def validate_density_percent(cls, value: object) -> int:
        return min(max(int(value or 20), 10), 100)

    @field_validator("duration_tolerance_seconds", mode="before")
    @classmethod
    def validate_duration_tolerance_seconds(cls, value: object) -> int:
        return max(int(value if value is not None else 120), 0)

    @field_validator("backfill_interval_seconds", mode="before")
    @classmethod
    def validate_backfill_interval_seconds(cls, value: object) -> int:
        return max(int(value or 21600), 60)

    @field_validator("backfill_recent_days", "backfill_missing_window_days", mode="before")
    @classmethod
    def validate_backfill_days(cls, value: object) -> int:
        return max(int(value or 1), 1)


class AddonsConfig(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(extra='allow')
    auth: AuthAddonConfig = Field(default_factory=AuthAddonConfig)
    notifications: NotificationsAddonConfig = Field(default_factory=NotificationsAddonConfig)
    danmu: DanmuAddonConfig = Field(default_factory=DanmuAddonConfig)

    @model_validator(mode='before')
    @classmethod
    def migrate_legacy_addons(cls, value: object) -> object:
        if type(value) is not dict:
            return value
        payload = dict(value)
        if "auth" not in payload and "auth_providers" in payload:
            payload["auth"] = payload["auth_providers"]
        payload.pop("auth_providers", None)
        if "notifications" not in payload and "telegram" in payload:
            telegram = payload["telegram"] if type(payload["telegram"]) is dict else {}
            bots = telegram["bots"] if "bots" in telegram and type(telegram["bots"]) is list else []
            payload["notifications"] = {
                "enabled": bool(telegram["enabled"]) if "enabled" in telegram else False,
                "channels": [
                    {
                        "id": bot["id"] if type(bot) is dict and "id" in bot else str(uuid.uuid4()),
                        "type": "telegram",
                        "name": bot["name"] if type(bot) is dict and "name" in bot else "",
                        "enabled": bool(bot["enabled"]) if type(bot) is dict and "enabled" in bot else True,
                        "event_patterns": list(bot["event_patterns"]) if type(bot) is dict and "event_patterns" in bot and type(bot["event_patterns"]) is list else ["subscription.*", "follow.*", "media.*", "download.*"],
                        "levels": list(bot["levels"]) if type(bot) is dict and "levels" in bot and type(bot["levels"]) is list else [],
                        "bot_token": bot["bot_token"] if type(bot) is dict and "bot_token" in bot else "",
                        "chat_id": bot["chat_id"] if type(bot) is dict and "chat_id" in bot else "",
                    }
                    for bot in bots
                ],
            }
        payload.pop("telegram", None)
        return payload


class AuthConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    enabled: bool = True
    password_hash: str | None = None
    session_ttl_seconds: int = 86400


class ServicesConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    browse_source: BrowseSource = BrowseSource.douban
    douban: DoubanConfig = Field(default_factory=DoubanConfig)
    themoviedb: TMDBConfig = Field(default_factory=TMDBConfig)


class SystemConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')

    cache: CacheConfig = Field(default_factory=CacheConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    library: LibraryConfig = Field(default_factory=LibraryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    onboarding_enabled: bool = False


class AppConfig(BaseModel):
    model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)

    # Internal note.
    browse_source: BrowseSource = BrowseSource.douban
    douban: DoubanConfig = Field(default_factory=DoubanConfig)
    themoviedb: TMDBConfig = Field(default_factory=TMDBConfig)

    # Internal note.
    indexers: list[IndexerProviderConfig] = Field(default_factory=list)
    downloaders: list[DownloaderProviderConfig] = Field(default_factory=list)
    media_servers: list[MediaServerProviderConfig] = Field(default_factory=list)
    directories: list[DirectoryConfig] = Field(default_factory=list)
    naming_templates: list[NamingTemplateVariant] = Field(default_factory=list)
    filter_presets: list[FilterConfig] = Field(default_factory=list)
    quality_profiles: list[QualityProfile] = Field(default_factory=list)
    tags: list[Tag] = Field(default_factory=list)

    # Internal note.
    default_media_server_id: str | None = None
    default_indexer_id: str | None = None
    default_movie_template_id: str | None = None
    default_tv_template_id: str | None = None

    # Internal note.
    cache: CacheConfig = Field(default_factory=CacheConfig)
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    library: LibraryConfig = Field(default_factory=LibraryConfig)
    onboarding_enabled: bool = False
    addons: AddonsConfig = Field(default_factory=AddonsConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_addons_field(cls, value: object) -> object:
        if type(value) is not dict:
            return value
        payload = dict(value)
        if "tags" not in payload and "custom_tags" in payload:
            payload["tags"] = payload["custom_tags"]
        payload.pop("custom_tags", None)
        if "addons" not in payload and "extensions" in payload:
            payload["addons"] = payload["extensions"]
        payload.pop("extensions", None)
        return payload

    def to_plain(self):
        """Return a plain dict suitable for persistence."""
        return self.model_dump(mode='json')


# Internal note.
DownloaderConfig.model_rebuild()
IndexerConfig.model_rebuild()
JackettConfig.model_rebuild()
ProwlarrConfig.model_rebuild()
MediaServerConfig.model_rebuild()
NotificationChannelConfig.model_rebuild()
AppConfig.model_rebuild()
