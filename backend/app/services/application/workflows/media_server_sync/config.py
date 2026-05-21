from datetime import date
from enum import Enum

from app.schemas.config import JellyfinConfig, MediaServerSyncConfig
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_types import MediaType
from app.services.config.settings_service import settings_service

SECONDS_PER_DAY = 86400
HOT_TV_INTERVAL_SECONDS = 3600
UPCOMING_MOVIE_INTERVAL_SECONDS = 21600
RECENT_INTERVAL_SECONDS = SECONDS_PER_DAY
COLD_INTERVAL_SECONDS = 7 * SECONDS_PER_DAY


class MediaServerSyncTier(str, Enum):
    hot_tv = "hot_tv"
    upcoming_movie = "upcoming_movie"
    recent = "recent"
    cold = "cold"


def media_server_sync_interval_seconds(
    media: MediaFullInfo,
    sync_cfg: MediaServerSyncConfig | None = None,
    *,
    today: date | None = None,
) -> int:
    tier = _classify_media(media, today=today)
    config_interval = _configured_stale_interval_seconds(media, sync_cfg or MediaServerSyncConfig())
    if tier == MediaServerSyncTier.cold:
        return config_interval
    return {
        MediaServerSyncTier.hot_tv: HOT_TV_INTERVAL_SECONDS,
        MediaServerSyncTier.upcoming_movie: UPCOMING_MOVIE_INTERVAL_SECONDS,
        MediaServerSyncTier.recent: RECENT_INTERVAL_SECONDS,
    }[tier]


def _configured_stale_interval_seconds(media: MediaFullInfo, sync_cfg: MediaServerSyncConfig) -> int:
    days = sync_cfg.stale_after_days_movie if media.media_type == MediaType.movie else sync_cfg.stale_after_days_tvshow
    if media.media_type == MediaType.tv and media.next_episode_to_air:
        days = min(days, sync_cfg.stale_after_days_ongoing_tv)
    return max(1, int(days)) * SECONDS_PER_DAY


def _classify_media(media: MediaFullInfo, *, today: date | None = None) -> MediaServerSyncTier:
    current_day = today or date.today()
    if media.media_type == MediaType.tv:
        return _classify_tv(media, current_day)
    return _classify_movie(media, current_day)


def _classify_tv(media: MediaFullInfo, today: date) -> MediaServerSyncTier:
    status_text = f"{media.status or ''} {media.status_label or ''}".lower()
    if media.next_episode_to_air:
        return MediaServerSyncTier.hot_tv
    if "airing" in status_text:
        return MediaServerSyncTier.hot_tv
    air_dates = _tv_air_dates(media)
    if any(abs((air_date - today).days) <= 14 for air_date in air_dates):
        return MediaServerSyncTier.hot_tv
    latest_air = max((air_date for air_date in air_dates if air_date <= today), default=None)
    if latest_air and (today - latest_air).days <= 30:
        return MediaServerSyncTier.recent
    return MediaServerSyncTier.cold


def _classify_movie(media: MediaFullInfo, today: date) -> MediaServerSyncTier:
    release_dates = _movie_release_dates(media)
    if any(-14 <= (release_date - today).days <= 30 for release_date in release_dates):
        return MediaServerSyncTier.upcoming_movie
    latest_release = max((release_date for release_date in release_dates if release_date <= today), default=None)
    if latest_release and (today - latest_release).days <= 30:
        return MediaServerSyncTier.recent
    return MediaServerSyncTier.cold


def _tv_air_dates(media: MediaFullInfo) -> list[date]:
    dates: list[date] = []
    latest = _parse_ymd(media.latest_aired_episode.air_date if media.latest_aired_episode else None)
    next_air = _parse_ymd(media.next_episode_to_air.air_date if media.next_episode_to_air else None)
    if latest:
        dates.append(latest)
    if next_air:
        dates.append(next_air)
    for airing in media.airings:
        air_date = _parse_ymd(airing.date)
        if air_date:
            dates.append(air_date)
    return dates


def _movie_release_dates(media: MediaFullInfo) -> list[date]:
    values = [
        media.premiere_release_date,
        media.theatrical_limited_release_date,
        media.theatrical_release_date,
        media.digital_release_date,
        media.physical_release_date,
        media.tv_release_date,
        media.release_date,
    ]
    dates = [_parse_ymd(value) for value in values]
    for release in media.release_dates:
        dates.append(_parse_ymd(release.release_date))
    return [release_date for release_date in dates if release_date]


def _parse_ymd(value: str | None) -> date | None:
    if not value:
        return None
    try:
        text = str(value).strip()
        if len(text) >= 10:
            text = text[:10]
        year, month, day = text.split("-")
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


class MediaServerSyncConfigService:
    def list_enabled_servers(self) -> list[JellyfinConfig]:
        return [
            media_server
            for media_server in settings_service.list_media_servers()
            if media_server.enabled and media_server.sync.enabled
        ]

    def resolve_server_for_directory_id(self, directory_id: str) -> JellyfinConfig | None:
        if not directory_id:
            return None
        directory = settings_service.get_directory_by_id(directory_id)
        if not directory or not directory.media_server_id:
            return None
        return next(
            (
                media_server
                for media_server in self.list_enabled_servers()
                if media_server.id == directory.media_server_id
            ),
            None,
        )

    def directory_ids_for_media_server(self, media_server_id: str) -> list[str]:
        return [
            directory.id
            for directory in settings_service.list_directories()
            if directory.enabled and directory.media_server_id == media_server_id
        ]

    def get_incremental_sync_scheduler_interval_seconds(self) -> int:
        enabled_servers = self.list_enabled_servers()
        if not enabled_servers:
            return 3600
        min_interval_hours = min(max(1, int(media_server.sync.interval_hours)) for media_server in enabled_servers)
        return min_interval_hours * 3600


media_server_sync_config = MediaServerSyncConfigService()
