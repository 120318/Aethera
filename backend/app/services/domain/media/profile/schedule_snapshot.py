import time
from collections.abc import Awaitable, Callable

from app.db.repositories.managed_media_profile_repository import ManagedMediaProfileRepository
from app.db.repositories.media_profile_scope_repository import MediaProfileScopeRepository
from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_profile_scope import MediaProfileScope
from app.schemas.domain.media_types import MediaType
from app.schemas.exception import SearchMissingSeasonInfoException
from app.schemas.media_id import MediaID
from app.services.domain.media.profile.read_model import MediaProfileReadModel
from app.services.domain.media.profile.scope_projection import (
    apply_scopes_to_profile,
    build_scope_from_media,
    select_scope,
    scope_airing_from_schedule,
)
from app.services.domain.media.schedule.service import MediaScheduleService


class MediaProfileScheduleSnapshot:
    def __init__(
        self,
        *,
        profile_repo: ManagedMediaProfileRepository,
        scope_repo: MediaProfileScopeRepository,
        read_model: MediaProfileReadModel,
        schedule_service: MediaScheduleService,
    ) -> None:
        self.profile_repo = profile_repo
        self.scope_repo = scope_repo
        self.read_model = read_model
        self.schedule_service = schedule_service

    def apply_schedule_snapshot(
        self,
        profile: ManagedMediaProfile,
        scope: MediaProfileScope,
        summary,
        airings,
        *,
        season_number: int | None = None,
    ) -> MediaProfileScope:
        now = time.time()
        platforms = {platform.key: platform for platform in scope.platforms}
        scope_airings = [
            scope_airing_from_schedule(airing, platforms)
            for airing in airings
            if profile.media_type != MediaType.tv or airing.season_number == season_number
        ]
        updated = build_scope_from_media(
            self.read_model.to_full(profile.media_id, profile).model_copy(update={
                "season_number": season_number if profile.media_type == MediaType.tv else None,
                "schedule": summary,
                "airings": list(airings),
            }),
            existing=scope,
        )
        if not updated:
            return scope
        return updated.model_copy(update={
            "status_label": summary.status_label,
            "aired_episode_count": summary.aired_episode_count,
            "latest_aired_episode": summary.latest_aired_episode,
            "next_episode_to_air": summary.next_episode_to_air,
            "premiere_release_date": summary.premiere_release_date,
            "theatrical_limited_release_date": summary.theatrical_limited_release_date,
            "theatrical_release_date": summary.theatrical_release_date,
            "digital_release_date": summary.digital_release_date,
            "physical_release_date": summary.physical_release_date,
            "tv_release_date": summary.tv_release_date,
            "release_dates": list(summary.release_dates),
            "airings": scope_airings,
            "updated_at": now,
        })

    async def build_profile_schedule_snapshot(
        self,
        media: MediaFullInfo,
        profile: ManagedMediaProfile,
        *,
        season_number: int | None = None,
    ):
        if profile.media_type != MediaType.tv:
            return await self.schedule_service.build_schedule_bundle(media)
        if season_number is None or season_number <= 0:
            raise SearchMissingSeasonInfoException()

        season_media = media.model_copy(update={"season_number": season_number})
        return await self.schedule_service.build_schedule_bundle(
            season_media,
            network_platforms=list(profile.networks),
        )

    async def refresh_schedule_snapshot(
        self,
        media_id: MediaID,
        *,
        existing: ManagedMediaProfile | None = None,
        season_number: int | None = None,
        refresh_profile: Callable[..., Awaitable[ManagedMediaProfile | None]],
    ) -> ManagedMediaProfile | None:
        if media_id.media_type == MediaType.tv and (season_number is None or season_number <= 0):
            raise SearchMissingSeasonInfoException()
        profile = existing or await self.profile_repo.find_by_media_id(media_id)
        if not profile or not profile.detail_ready:
            return await refresh_profile(media_id, existing=profile, season_number=season_number)
        scopes = await self.scope_repo.find_by_media_id(media_id)
        scoped_profile = apply_scopes_to_profile(profile, scopes, season_number=season_number)
        selected_scope = select_scope(profile, scopes, season_number=season_number)
        media = self.read_model.snapshot_to_full(media_id, scoped_profile, selected_scope=selected_scope)
        if not media:
            return None
        summary, airings = await self.build_profile_schedule_snapshot(media, profile, season_number=season_number)
        scope_number = season_number if media_id.media_type == MediaType.tv else 0
        scope = await self.scope_repo.find_by_media_id_and_season(media_id, int(scope_number or 0))
        if not scope:
            scope = build_scope_from_media(media)
        if not scope:
            return scoped_profile
        updated_scope = self.apply_schedule_snapshot(scoped_profile, scope, summary, airings, season_number=season_number)
        await self.scope_repo.upsert_scope(updated_scope)
        updated_profile = profile.model_copy(update={"schedule_updated_at": time.time(), "updated_at": time.time()})
        await self.profile_repo.upsert_profile(updated_profile)
        return apply_scopes_to_profile(updated_profile, await self.scope_repo.find_by_media_id(media_id), season_number=season_number)
