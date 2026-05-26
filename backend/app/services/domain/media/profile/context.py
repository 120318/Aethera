from __future__ import annotations

from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media import MediaFullInfo, MediaSimpleInfo
from app.schemas.domain.media_context import (
    MediaCapabilities,
    MediaPrimarySource,
    ResolvedMediaContext,
)
from app.schemas.domain.media_types import MediaType


class MediaProfileContextService:
    def _has_any_capability(self, media_capabilities: MediaCapabilities | None) -> bool:
        if not media_capabilities:
            return False
        return any(bool(value) for value in media_capabilities.model_dump(mode="python").values())

    def resolve_primary_source(self, tmdb_id: int | None) -> MediaPrimarySource:
        return "tmdb" if tmdb_id else "douban"

    def build_capabilities(
        self,
        media_type: MediaType,
        primary_metadata_source: MediaPrimarySource,
    ) -> MediaCapabilities:
        if primary_metadata_source != "tmdb":
            return MediaCapabilities()

        if media_type == MediaType.movie:
            return MediaCapabilities(
                has_enhanced_detail=True,
                has_movie_release_window=True,
                has_watch_providers=True,
                can_generate_enhanced_nfo=True,
            )

        if media_type == MediaType.tv:
            return MediaCapabilities(
                has_enhanced_detail=True,
                has_schedule=True,
                has_season_episode_detail=True,
                can_generate_enhanced_nfo=True,
            )

        return MediaCapabilities()

    def resolve_context(
        self,
        *,
        media_id,
        media_type: MediaType,
        title: str,
        year: int,
        douban_id: str | None,
        imdb_id: str | None,
        tmdb_id: int | None,
        season_number: int | None,
        primary_metadata_source: MediaPrimarySource | None = None,
        metadata_capabilities: MediaCapabilities | None = None,
    ) -> ResolvedMediaContext:
        source = self.resolve_primary_source(tmdb_id)
        capabilities = metadata_capabilities
        if capabilities is None or source != primary_metadata_source or (source == "tmdb" and not self._has_any_capability(capabilities)):
            capabilities = self.build_capabilities(media_type, source)
        return ResolvedMediaContext(
            media_id=media_id,
            media_type=media_type,
            title=title,
            year=year,
            douban_id=douban_id,
            imdb_id=imdb_id,
            tmdb_id=tmdb_id,
            season_number=season_number,
            primary_metadata_source=source,
            metadata_capabilities=capabilities,
        )

    def resolve_context_from_media(self, media: MediaFullInfo) -> ResolvedMediaContext:
        return self.resolve_context(
            media_id=media.media_id,
            media_type=media.media_type,
            title=media.title,
            year=media.year,
            douban_id=media.douban_id,
            imdb_id=media.imdb_id,
            tmdb_id=media.tmdb_id,
            season_number=media.season_number,
            primary_metadata_source=media.primary_metadata_source,
            metadata_capabilities=media.metadata_capabilities,
        )

    def resolve_context_from_profile(self, profile: ManagedMediaProfile) -> ResolvedMediaContext | None:
        if profile.year is None:
            return None
        season_number = None
        if profile.media_type == MediaType.tv and len(profile.seasons) == 1:
            season_number = profile.seasons[0].season_number
        return self.resolve_context(
            media_id=profile.media_id,
            media_type=profile.media_type,
            title=profile.title,
            year=profile.year,
            douban_id=None,
            imdb_id=profile.imdb_id,
            tmdb_id=profile.tmdb_id,
            season_number=season_number,
            primary_metadata_source=profile.primary_metadata_source,
            metadata_capabilities=profile.metadata_capabilities,
        )

    def enrich_media(self, media: MediaFullInfo) -> MediaFullInfo:
        context = self.resolve_context_from_media(media)
        media.primary_metadata_source = context.primary_metadata_source
        media.metadata_capabilities = context.metadata_capabilities
        return media

    def enrich_simple_media(self, media: MediaSimpleInfo) -> MediaSimpleInfo:
        context = self.resolve_context(
            media_id=media.media_id,
            media_type=media.media_type,
            title=media.title,
            year=media.year,
            douban_id=media.douban_id,
            imdb_id=media.imdb_id,
            tmdb_id=media.tmdb_id,
            season_number=media.season_number,
            primary_metadata_source=media.primary_metadata_source,
            metadata_capabilities=media.metadata_capabilities,
        )
        media.primary_metadata_source = context.primary_metadata_source
        media.metadata_capabilities = context.metadata_capabilities
        return media

    def enrich_profile(self, profile: ManagedMediaProfile) -> ManagedMediaProfile:
        context = self.resolve_context_from_profile(profile)
        if not context:
            profile.primary_metadata_source = self.resolve_primary_source(profile.tmdb_id)
            profile.metadata_capabilities = self.build_capabilities(profile.media_type, profile.primary_metadata_source)
            return profile
        profile.primary_metadata_source = context.primary_metadata_source
        profile.metadata_capabilities = context.metadata_capabilities
        return profile

    def tmdb_id_from_context(self, context: ResolvedMediaContext) -> int | None:
        if context.primary_metadata_source != "tmdb":
            return None
        try:
            return int(context.tmdb_id) if context.tmdb_id is not None else None
        except (TypeError, ValueError):
            return None


media_profile_context_service = MediaProfileContextService()
