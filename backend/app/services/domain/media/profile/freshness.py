import time

from app.schemas.config import MediaServerSyncConfig
from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media_types import MediaType
from app.services.config.settings_service import settings_service


def _profile_refresh_config() -> MediaServerSyncConfig:
    media_servers = settings_service.list_media_servers()
    if not media_servers:
        return MediaServerSyncConfig()
    default_media_server_id = settings_service.get_default_media_server_id()
    if default_media_server_id:
        default_media_server = next(
            (media_server for media_server in media_servers if media_server.id == default_media_server_id),
            None,
        )
        if default_media_server:
            return default_media_server.sync
    return media_servers[0].sync


def _profile_stale_after_days(profile: ManagedMediaProfile) -> int:
    sync_cfg = _profile_refresh_config()
    days = sync_cfg.stale_after_days_movie if profile.media_type == MediaType.movie else sync_cfg.stale_after_days_tvshow
    if profile.media_type == MediaType.tv and profile.next_episode_to_air:
        days = min(days, sync_cfg.stale_after_days_ongoing_tv)
    return days


def is_profile_stale(profile: ManagedMediaProfile) -> bool:
    if not profile.detail_updated_at:
        return True
    return (time.time() - profile.detail_updated_at) > _profile_stale_after_days(profile) * 86400
