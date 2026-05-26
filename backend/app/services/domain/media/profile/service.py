from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from app.db.repositories.library_episode_repository import LibraryEpisodeRepository
from app.db.repositories.library_file_repository import LibraryFileRepository
from app.db.repositories.library_meta_repository import LibraryMetaRepository
from app.db.repositories.managed_media_profile_repository import ManagedMediaProfileRepository
from app.db.repositories.media_external_mapping_repository import MediaExternalMappingRepository
from app.db.repositories.media_profile_scope_repository import MediaProfileScopeRepository
from app.db.repositories.task_repository import TaskRepository
from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media import MediaFullInfo, MediaIdentity, MediaSimpleInfo
from app.schemas.domain.media_profile_scope import MediaProfileScope
from app.schemas.domain.media_source import MediaSourceLookup, MediaSourceName
from app.schemas.domain.media_types import MediaType
from app.schemas.exception import AppException, MediaNotFoundException, SearchMissingSeasonInfoException
from app.schemas.media_id import MediaID
from app.services.domain.media.profile.access import model_field_list, model_field_value
from app.services.domain.media.profile.builders import build_profile_from_media
from app.services.domain.media.profile.lifecycle import MediaProfileLifecycle
from app.services.domain.media.profile.context import media_profile_context_service
from app.services.domain.media.profile.read_model import MediaProfileReadModel
from app.services.domain.media.profile.refresh import fetch_profile_refresh_media
from app.services.domain.media.profile.refresh_policy import profile_refresh_decision
from app.services.domain.media.profile.schedule_snapshot import MediaProfileScheduleSnapshot
from app.services.domain.media.profile.scope_projection import (
    apply_scopes_to_profile,
    build_scopes_from_media,
    has_scope_detail,
    select_scope,
)
from app.services.domain.media.profile.season_metadata import (
    profile_episode_count,
    with_cached_season_metadata,
    with_season_external_ids,
)
from app.services.domain.media.schedule.service import MediaScheduleService
from app.services.platform.domain_lock_service import domain_lock_service

if TYPE_CHECKING:
    from app.services.domain.media.provider.service import MediaProviderService

logger = logging.getLogger("app.services.media")


class MediaProfileService:
    def __init__(self, provider_service: MediaProviderService, schedule_service: MediaScheduleService) -> None:
        self.provider_service = provider_service
        self.schedule_service = schedule_service
        self.profile_repo = ManagedMediaProfileRepository()
        self.mapping_repo = MediaExternalMappingRepository()
        self.scope_repo = MediaProfileScopeRepository()
        self.task_repo = TaskRepository()
        self.episode_repo = LibraryEpisodeRepository()
        self.file_repo = LibraryFileRepository()
        self.meta_repo = LibraryMetaRepository()
        self.read_model = MediaProfileReadModel()
        self.lifecycle = MediaProfileLifecycle(
            profile_repo=self.profile_repo,
            task_repo=self.task_repo,
            episode_repo=self.episode_repo,
            file_repo=self.file_repo,
            meta_repo=self.meta_repo,
        )
        self.schedule_snapshot = MediaProfileScheduleSnapshot(
            profile_repo=self.profile_repo,
            scope_repo=self.scope_repo,
            read_model=self.read_model,
            schedule_service=self.schedule_service,
        )

    def profile_to_simple(self, media_id: MediaID, profile: ManagedMediaProfile) -> MediaSimpleInfo:
        return self.read_model.to_simple(media_id, profile)

    def profile_to_full(self, media_id: MediaID, profile: ManagedMediaProfile) -> MediaFullInfo:
        return self.read_model.to_full(media_id, profile)

    async def _profile_with_scopes(
        self,
        profile: ManagedMediaProfile,
        *,
        season_number: int | None = None,
    ) -> ManagedMediaProfile:
        scopes = await self.scope_repo.find_by_media_id(profile.media_id)
        return apply_scopes_to_profile(profile, scopes, season_number=season_number)

    async def _profile_scope_context(
        self,
        profile: ManagedMediaProfile,
        *,
        season_number: int | None = None,
    ) -> tuple[ManagedMediaProfile, MediaProfileScope | None]:
        scopes = await self.scope_repo.find_by_media_id(profile.media_id)
        scoped = apply_scopes_to_profile(profile, scopes, season_number=season_number)
        return scoped, select_scope(profile, scopes, season_number=season_number)

    async def _has_cached_scope_detail(
        self,
        profile: ManagedMediaProfile,
        *,
        season_number: int | None,
    ) -> bool:
        scopes = await self.scope_repo.find_by_media_id(profile.media_id)
        return has_scope_detail(profile, scopes, season_number)

    async def apply_source_mapping_snapshot(
        self,
        media_id: MediaID,
        *,
        season_number: int | None,
        douban_id: str | None = None,
        episode_count_override: int | None = None,
    ) -> None:
        if media_id.media_type != MediaType.tv or not season_number or season_number <= 0:
            return
        profile = await self.profile_repo.find_by_media_id(media_id)
        if not profile or not profile.detail_ready:
            return
        scope = await self.scope_repo.find_by_media_id_and_season(media_id, season_number)
        if not scope:
            return
        await self.scope_repo.upsert_scope(
            scope.model_copy(update={
                "douban_id": douban_id or scope.douban_id,
                "episode_count_override": episode_count_override
                if episode_count_override is not None
                else scope.episode_count_override,
                "updated_at": time.time(),
            })
        )

    def _build_placeholder_profile(
        self,
        media_id: MediaID,
        *,
        title: str | None = None,
        year: int | None = None,
        existing: ManagedMediaProfile | None = None,
        is_active: bool = True,
    ) -> ManagedMediaProfile:
        now = time.time()
        placeholder_title = str(title).strip() if title and str(title).strip() else (existing.title if existing and existing.title else "")
        placeholder_year = year if year and year > 0 else (existing.year if existing else None)
        if not placeholder_title or placeholder_year is None:
            raise MediaNotFoundException()
        media_type = existing.media_type if existing else media_id.media_type
        return ManagedMediaProfile(
            media_id=media_id,
            media_type=media_type,
            title=placeholder_title,
            original_title=existing.original_title if existing else None,
            poster_path=existing.poster_path if existing else None,
            backdrop_path=existing.backdrop_path if existing else None,
            logo_path=existing.logo_path if existing else None,
            year=placeholder_year,
            overview=existing.overview if existing else None,
            genres=list(existing.genres) if existing else [],
            imdb_id=existing.imdb_id if existing else None,
            tmdb_id=existing.tmdb_id if existing else None,
            primary_metadata_source=existing.primary_metadata_source if existing else "douban",
            metadata_capabilities=existing.metadata_capabilities if existing else media_profile_context_service.build_capabilities(media_type, "douban"),
            tvdb_id=existing.tvdb_id if existing else None,
            actors=list(existing.actors) if existing else [],
            directors=list(existing.directors) if existing else [],
            studios=list(existing.studios) if existing else [],
            vendors=list(existing.vendors) if existing else [],
            duration=existing.duration if existing else None,
            tmdb_vote_average=existing.tmdb_vote_average if existing else None,
            tmdb_rating_count=existing.tmdb_rating_count if existing else None,
            release_date=existing.release_date if existing else None,
            first_air_date=existing.first_air_date if existing else None,
            seasons_count=existing.seasons_count if existing else None,
            episodes_count=existing.episodes_count if existing else None,
            seasons=list(existing.seasons) if existing else [],
            status=existing.status if existing else None,
            original_language=existing.original_language if existing else None,
            status_label=None,
            aired_episode_count=0,
            latest_aired_episode=None,
            next_episode_to_air=None,
            premiere_release_date=model_field_value(existing, "premiere_release_date"),
            theatrical_limited_release_date=model_field_value(existing, "theatrical_limited_release_date"),
            theatrical_release_date=None,
            digital_release_date=None,
            physical_release_date=model_field_value(existing, "physical_release_date"),
            tv_release_date=model_field_value(existing, "tv_release_date"),
            release_dates=model_field_list(existing, "release_dates"),
            networks=list(existing.networks) if existing else [],
            online_platforms=list(existing.online_platforms) if existing else [],
            airings=[],
            is_active=is_active,
            last_seen_at=now,
            inactive_since=None if is_active else now,
            detail_ready=bool(existing.detail_ready) if existing else False,
            simple_info_updated_at=existing.simple_info_updated_at if existing else None,
            detail_updated_at=existing.detail_updated_at if existing else None,
            schedule_updated_at=None,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )

    async def _upsert_profile_from_media(
        self,
        media: MediaFullInfo,
        *,
        existing: ManagedMediaProfile | None = None,
    ) -> ManagedMediaProfile:
        is_active = await self._resolve_upsert_active_state(
            media.media_id,
            existing=existing,
        )
        profile = build_profile_from_media(
            media,
            existing=existing,
            is_active=is_active,
            episodes_count=profile_episode_count(media),
        )
        profile = media_profile_context_service.enrich_profile(profile)
        existing_scopes = await self.scope_repo.find_by_media_id(media.media_id)
        scopes = build_scopes_from_media(media, existing_scopes)
        if scopes:
            await self.scope_repo.upsert_scopes(scopes)
        await self.profile_repo.upsert_profile(profile)
        return profile

    async def _resolve_upsert_active_state(
        self,
        media_id: MediaID,
        *,
        existing: ManagedMediaProfile | None,
    ) -> bool:
        if existing and existing.is_active:
            return True
        return await self.lifecycle.is_managed_media(media_id)

    async def refresh_schedule_snapshot(
        self,
        media_id: MediaID,
        *,
        existing: ManagedMediaProfile | None = None,
        season_number: int | None = None,
    ) -> ManagedMediaProfile | None:
        return await self.schedule_snapshot.refresh_schedule_snapshot(
            media_id,
            existing=existing,
            season_number=season_number,
            refresh_profile=self.refresh_profile,
        )

    async def list_profiles_by_media_ids(self, media_ids: list[MediaID]) -> list[ManagedMediaProfile]:
        profiles = await self.profile_repo.find_by_media_ids(media_ids)
        scopes_by_media_id = await self.scope_repo.find_by_media_ids(media_ids)
        return [
            apply_scopes_to_profile(profile, scopes_by_media_id.get(str(profile.media_id), []))
            for profile in profiles
        ]

    async def list_profiles_by_media_targets(self, targets: list[tuple[MediaID, int | None]]) -> dict[str, ManagedMediaProfile]:
        media_ids_by_key = {str(media_id): media_id for media_id, _season_number in targets}
        if not media_ids_by_key:
            return {}
        profiles = await self.profile_repo.find_by_media_ids(list(media_ids_by_key.values()))
        profile_by_media_id = {str(profile.media_id): profile for profile in profiles}
        scopes_by_media_id = await self.scope_repo.find_by_media_ids(list(media_ids_by_key.values()))
        result: dict[str, ManagedMediaProfile] = {}
        for media_id, season_number in targets:
            profile = profile_by_media_id.get(str(media_id))
            if not profile:
                continue
            result[f"{media_id}:{season_number or ''}"] = apply_scopes_to_profile(
                profile,
                scopes_by_media_id.get(str(media_id), []),
                season_number=season_number,
            )
        return result

    async def upsert_active_profile_from_identity(self, media: MediaIdentity) -> ManagedMediaProfile:
        existing = await self.profile_repo.find_by_media_id(media.media_id)
        if existing:
            now = time.time()
            updated = existing.model_copy(
                update={"is_active": True, "inactive_since": None, "last_seen_at": now, "updated_at": now}
            )
            if media.title != updated.title:
                updated.title = media.title
            if media.year != updated.year:
                updated.year = media.year
            await self.profile_repo.upsert_profile(updated)
            return updated

        placeholder = self._build_placeholder_profile(
            media.media_id,
            title=media.title,
            year=media.year,
            existing=None,
            is_active=True,
        )
        await self.profile_repo.upsert_profile(placeholder)
        return placeholder

    async def activate_existing_profile(self, media_id: MediaID) -> None:
        existing = await self.profile_repo.find_by_media_id(media_id)
        if existing:
            now = time.time()
            updated = existing.model_copy(
                update={"is_active": True, "inactive_since": None, "last_seen_at": now, "updated_at": now}
            )
            await self.profile_repo.upsert_profile(updated)

    async def info(
        self,
        media_id: MediaID,
        *,
        season_number: int | None = None,
        include_default_season_details: bool = False,
        default_season_year: int | None = None,
    ) -> MediaFullInfo | None:
        media, _cache_mode = await self.info_with_cache_status(
            media_id,
            season_number=season_number,
            include_default_season_details=include_default_season_details,
            default_season_year=default_season_year,
        )
        return media

    def _default_season_number(
        self,
        media: MediaFullInfo,
        *,
        preferred_year: int | None = None,
    ) -> int | None:
        if media.media_type != MediaType.tv:
            return None
        if preferred_year:
            for season in media.seasons:
                air_date = season.air_date or ""
                if len(air_date) >= 4 and air_date[:4].isdigit() and int(air_date[:4]) == preferred_year:
                    return int(season.season_number)
        if any(season.season_number == 1 for season in media.seasons):
            return 1
        available = sorted(
            int(season.season_number)
            for season in media.seasons
            if season.season_number is not None and season.season_number > 0
        )
        return available[0] if available else None

    async def info_with_cache_status(
        self,
        media_id: MediaID,
        *,
        season_number: int | None = None,
        include_default_season_details: bool = False,
        default_season_year: int | None = None,
    ) -> tuple[MediaFullInfo | None, str]:
        if (
            media_id.media_type == MediaType.tv
            and (season_number is None or season_number <= 0)
            and not include_default_season_details
        ):
            raise SearchMissingSeasonInfoException()
        profile = await self.profile_repo.find_by_media_id(media_id)
        if profile and self.read_model.has_complete_detail(profile):
            scoped_profile, selected_scope = await self._profile_scope_context(profile, season_number=season_number)
            cached = self.read_model.snapshot_to_full(media_id, scoped_profile, selected_scope=selected_scope)
            if cached:
                effective_season = season_number
                if include_default_season_details and media_id.media_type == MediaType.tv and effective_season is None:
                    effective_season = self._default_season_number(cached, preferred_year=default_season_year)
                cached = with_season_external_ids(cached, effective_season, self.mapping_repo)
                if not include_default_season_details or await self._has_cached_scope_detail(profile, season_number=effective_season):
                    return with_cached_season_metadata(cached, effective_season), "hit"

        media = await self.provider_service.info(
            media_id,
            season_number=season_number,
            include_default_season_details=include_default_season_details,
            default_season_year=default_season_year,
        )
        if not media:
            return None, "miss"
        media = with_season_external_ids(media, season_number or media.season_number, self.mapping_repo)
        updated_profile = await self._upsert_profile_from_media(media, existing=profile)
        updated_profile, selected_scope = await self._profile_scope_context(
            updated_profile,
            season_number=season_number or media.season_number,
        )
        result = self.read_model.snapshot_to_full(media_id, updated_profile, selected_scope=selected_scope)
        enriched = result or media
        effective_season = season_number
        if include_default_season_details and media_id.media_type == MediaType.tv and effective_season is None:
            effective_season = media.season_number or enriched.season_number or self._default_season_number(
                enriched,
                preferred_year=default_season_year,
            )
        return with_cached_season_metadata(enriched, effective_season), "miss"

    async def cached_info(self, media_id: MediaID) -> MediaFullInfo | None:
        profile = await self.profile_repo.find_by_media_id(media_id)
        if not profile or not self.read_model.has_complete_detail(profile):
            return None
        scoped_profile, selected_scope = await self._profile_scope_context(profile)
        return self.read_model.snapshot_to_full(media_id, scoped_profile, selected_scope=selected_scope)

    async def info_from_source(self, lookup: MediaSourceLookup) -> MediaFullInfo | None:
        mapping = self._resolve_source_mapping(lookup)
        if mapping and mapping.media_id.media_type == lookup.media_type:
            profile = await self.profile_repo.find_by_media_id(mapping.media_id)
            if profile and self.read_model.has_complete_detail(profile):
                resolved_douban_id = mapping.douban_id or lookup.source_id
                scoped_profile, selected_scope = await self._profile_scope_context(profile, season_number=mapping.season_number)
                cached = self.read_model.snapshot_to_full(mapping.media_id, scoped_profile, selected_scope=selected_scope)
                if cached:
                    if lookup.source == MediaSourceName.douban:
                        self.mapping_repo.upsert(
                            media_id=mapping.media_id,
                            tmdb_id=mapping.tmdb_id,
                            imdb_id=mapping.imdb_id,
                            douban_id=resolved_douban_id,
                            season_number=mapping.season_number,
                            episode_count_override=mapping.episode_count_override,
                        )
                    if lookup.media_type != MediaType.tv:
                        return cached.model_copy(update={"douban_id": resolved_douban_id})
                    cached = cached.model_copy(update={
                        "douban_id": resolved_douban_id,
                        "season_number": mapping.season_number,
                    })
                    seasons = [
                        season.model_copy(update={
                            "douban_id": resolved_douban_id,
                            "episode_count_override": mapping.episode_count_override,
                        })
                        if mapping.season_number and int(season.season_number) == int(mapping.season_number)
                        else season
                        for season in cached.seasons
                    ]
                    return with_cached_season_metadata(
                        cached.model_copy(update={"seasons": seasons}),
                        mapping.season_number,
                    )

        media = await self.provider_service.info_from_source(lookup)
        if not media:
            return None
        if lookup.source == MediaSourceName.douban:
            resolved_douban_id = media.douban_id or lookup.source_id
            media = media.model_copy(update={"douban_id": resolved_douban_id})
            self.mapping_repo.upsert(
                media_id=media.media_id,
                tmdb_id=media.tmdb_id,
                imdb_id=media.imdb_id,
                douban_id=resolved_douban_id,
                season_number=media.season_number if media.media_type == MediaType.tv else None,
                episode_count_override=media.episode_count_override if media.media_type == MediaType.tv else None,
            )
        media = with_season_external_ids(media, media.season_number, self.mapping_repo)
        existing = await self.profile_repo.find_by_media_id(media.media_id)
        updated_profile = await self._upsert_profile_from_media(media, existing=existing)
        updated_profile, selected_scope = await self._profile_scope_context(updated_profile, season_number=media.season_number)
        result = self.read_model.snapshot_to_full(media.media_id, updated_profile, selected_scope=selected_scope)
        return result or media

    def _resolve_source_mapping(self, lookup: MediaSourceLookup):
        if lookup.source != MediaSourceName.douban:
            return None
        return self.mapping_repo.find_by_douban_id(lookup.source_id, lookup.media_type.value)

    async def simple_info(self, media_id: MediaID) -> MediaSimpleInfo | None:
        profile = await self.profile_repo.find_by_media_id(media_id)
        if profile and profile.detail_ready:
            try:
                scoped_profile, selected_scope = await self._profile_scope_context(profile)
                return self.read_model.to_simple(media_id, scoped_profile, selected_scope=selected_scope)
            except MediaNotFoundException:
                logger.warning("Managed media profile missing required title/year: %s", media_id)
        return None

    async def refresh_profile(
        self,
        media_id: MediaID,
        existing: ManagedMediaProfile | None = None,
        *,
        season_number: int | None = None,
    ) -> ManagedMediaProfile | None:
        existing_profile = existing or await self.profile_repo.find_by_media_id(media_id)
        source_scope_number = season_number if media_id.media_type == MediaType.tv else 0
        source_scope = await self.scope_repo.find_by_media_id_and_season(media_id, int(source_scope_number or 0))
        media = await fetch_profile_refresh_media(
            self.provider_service,
            media_id,
            existing_profile,
            season_number=season_number,
            source_douban_id=source_scope.douban_id if source_scope else None,
        )
        if not media:
            return None
        media = with_season_external_ids(media, season_number or media.season_number, self.mapping_repo)
        profile = await self._upsert_profile_from_media(media, existing=existing_profile)
        try:
            refreshed = await self.refresh_schedule_snapshot(media_id, existing=profile, season_number=season_number)
            return refreshed or profile
        except (AppException, RuntimeError, ValueError):
            logger.exception("Failed to refresh managed media schedule for %s", media_id)
            return await self._profile_with_scopes(profile, season_number=season_number)

    async def refresh_profile_safely(self, media_id: MediaID, season_number: int | None = None) -> None:
        async with domain_lock_service.acquire_profile_refresh(media_id, season_number) as acquired:
            if not acquired:
                logger.info(
                    "Managed media profile refresh skipped because another refresh is already running: media=%s season=%s",
                    media_id,
                    season_number,
                )
                return
            try:
                await self.refresh_profile(media_id, season_number=season_number)
            except (AppException, RuntimeError, ValueError):
                logger.exception("Failed to refresh managed media profile for %s", media_id)

    async def is_managed_media(self, media_id: MediaID) -> bool:
        return await self.lifecycle.is_managed_media(media_id)

    async def mark_profile_inactive_if_unmanaged(self, media_id: MediaID) -> bool:
        return await self.lifecycle.mark_profile_inactive_if_unmanaged(media_id)

    async def mark_inactive_profiles(self, active_media_ids: list[MediaID]) -> int:
        return await self.lifecycle.mark_inactive_profiles(active_media_ids)

    def _profile_refresh_season_numbers(self, profile: ManagedMediaProfile) -> list[int]:
        if profile.media_type != MediaType.tv:
            return []
        season_numbers = {
            int(season.season_number)
            for season in profile.seasons
            if season.season_number is not None and season.season_number > 0
        }
        for episode in (profile.latest_aired_episode, profile.next_episode_to_air):
            if episode and episode.season_number is not None and episode.season_number > 0:
                season_numbers.add(int(episode.season_number))
        return sorted(season_numbers)

    async def refresh_active_profiles(self) -> int:
        active_map = await self.lifecycle.build_active_media_map()
        await self.mark_inactive_profiles(list(active_map.keys()))
        profiles = await self.profile_repo.find_active()
        refreshed = 0
        for profile in profiles:
            media_id = profile.media_id
            try:
                scoped_profile = await self._profile_with_scopes(profile)
                decision = profile_refresh_decision(scoped_profile)
                if not decision.refresh_profile and not decision.refresh_schedule:
                    continue
                season_numbers = self._profile_refresh_season_numbers(scoped_profile)
                if season_numbers:
                    current_profile = scoped_profile
                    for season_number in season_numbers:
                        if decision.refresh_profile:
                            season_profile = await self.refresh_profile(
                                media_id,
                                existing=current_profile,
                                season_number=season_number,
                            )
                        else:
                            season_profile = await self.refresh_schedule_snapshot(
                                media_id,
                                existing=current_profile,
                                season_number=season_number,
                            )
                        if season_profile:
                            refreshed += 1
                            current_profile = season_profile
                    continue

                if decision.refresh_profile:
                    refreshed_profile = await self.refresh_profile(media_id, existing=scoped_profile)
                else:
                    refreshed_profile = await self.refresh_schedule_snapshot(media_id, existing=scoped_profile)
                if refreshed_profile:
                    refreshed += 1
            except (AppException, RuntimeError, ValueError):
                logger.exception("Failed to refresh managed media profile for %s", media_id)
        return refreshed

    async def cleanup_inactive_profiles(self) -> int:
        return await self.lifecycle.cleanup_inactive_profiles()
