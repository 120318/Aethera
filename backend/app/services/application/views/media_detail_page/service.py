from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import TypeVar

from app.schemas.domain.command import CommandRecord
from app.schemas.domain.media import MediaFullInfo, MediaTarget
from app.schemas.domain.media_download_config import MediaDownloadConfig, MediaDownloadConfigView
from app.schemas.domain.media_subscription_state import MediaSubscriptionState, MediaSubscriptionStateView
from app.schemas.domain.media_source import MediaSourceLookup, MediaSourceName
from app.schemas.domain.media_types import MediaType
from app.schemas.exception import InvalidRequestException, MediaNotFoundException
from app.schemas.media_id import MediaID, Provider
from app.schemas.runtime.media_detail_page import MediaDetailPageResponse, MediaDetailPageTabData
from app.services.application.commands.service import command_service
from app.services.application.views.media_detail_overview import media_detail_overview_service
from app.services.application.views.task import task_view_service
from app.services.domain.library.service import MediaLibrarySnapshot, library_service
from app.services.domain.media import media_service
from app.services.domain.subscription.query_service import subscription_query_service
from app.utils import build_loose_tmdb_search_title, build_tmdb_search_title


logger = logging.getLogger("app.media_detail_page")
T = TypeVar("T")


@dataclass(frozen=True)
class _ResolvedDetailTarget:
    media_id: MediaID
    season_number: int | None
    source: MediaSourceName | None = None
    source_id: str | None = None
    source_year: int | None = None


@dataclass(frozen=True)
class _PageSideData:
    subscription_state: MediaSubscriptionState | None
    subscription: MediaSubscriptionStateView
    download_config: MediaDownloadConfig | None
    active_commands: list[CommandRecord]


@dataclass(frozen=True)
class _LoadedMedia:
    media: MediaFullInfo
    cache_mode: str


class MediaDetailPageApplicationService:
    async def _timed(self, timings: dict[str, float], name: str, awaitable: Awaitable[T]) -> T:
        started_at = time.perf_counter()
        try:
            return await awaitable
        finally:
            timings[name] = (time.perf_counter() - started_at) * 1000

    def _record_elapsed(self, timings: dict[str, float], name: str, started_at: float) -> None:
        timings[name] = (time.perf_counter() - started_at) * 1000

    def _log_timing(
        self,
        *,
        timings: dict[str, float],
        started_at: float,
        branch: str,
        active_tab: str,
        target: _ResolvedDetailTarget,
        effective_media_id: MediaID,
        effective_season_number: int | None,
        media_cache_mode: str,
    ) -> None:
        total_ms = (time.perf_counter() - started_at) * 1000
        timing_text = " ".join(f"{key}_ms={value:.1f}" for key, value in sorted(timings.items()))
        logger.info(
            "media_detail_page_timing total_ms=%.1f branch=%s active_tab=%s target_media_id=%s "
            "effective_media_id=%s target_season=%s effective_season=%s source=%s media_cache=%s %s",
            total_ms,
            branch,
            active_tab,
            target.media_id,
            effective_media_id,
            target.season_number,
            effective_season_number,
            target.source.value if target.source else "-",
            media_cache_mode,
            timing_text,
        )

    def _requested_season(self, media_type: MediaType | None, season_number: int | None) -> int | None:
        if media_type != MediaType.tv:
            return None
        if season_number and season_number > 0:
            return int(season_number)
        return None

    async def _resolve_target(
        self,
        *,
        media_id: MediaID | None,
        source: MediaSourceName | None,
        source_id: str | None,
        media_type: MediaType | None,
        title: str | None,
        year: int | None,
        season_number: int | None,
    ) -> _ResolvedDetailTarget:
        requested_media_type = media_id.media_type if media_id is not None else media_type
        requested_season = self._requested_season(requested_media_type, season_number)
        if media_id is not None:
            return _ResolvedDetailTarget(media_id=media_id, season_number=requested_season)
        if source == MediaSourceName.tmdb and source_id and media_type:
            resolved_season = requested_season or (1 if media_type == MediaType.tv else None)
            return _ResolvedDetailTarget(
                media_id=MediaID(provider=Provider.tmdb, media_type=media_type, id=source_id),
                season_number=resolved_season,
            )
        if source != MediaSourceName.douban or not source_id or not media_type:
            raise MediaNotFoundException()

        lookup = MediaSourceLookup(source=MediaSourceName.douban, source_id=source_id, media_type=media_type)
        raw_title = (title or "").strip()
        search_title = raw_title
        parsed_title_season = None
        if raw_title:
            search_title, parsed_title_season = build_tmdb_search_title(
                raw_title,
                is_tv=media_type == MediaType.tv,
            )
        explicit_season = season_number if media_type == MediaType.tv and season_number and season_number > 0 else None
        existing_mapping = media_service.provider_service.mapping.mapping_repo.find_by_douban_id(source_id, media_type.value)
        if existing_mapping and existing_mapping.tmdb_id:
            canonical_media_id = media_service.provider_service.mapping.canonical_tmdb_media_id(media_type, existing_mapping.tmdb_id)
            resolved_season = explicit_season or parsed_title_season or (existing_mapping.season_number if media_type == MediaType.tv else None)
            await media_service.provider_service.mapping.set_cached_tmdb_mapping(
                canonical_media_id,
                existing_mapping.tmdb_id,
                existing_mapping.imdb_id,
                existing_mapping.douban_id or source_id,
                resolved_season if media_type == MediaType.tv else None,
                existing_mapping.episode_count_override if media_type == MediaType.tv else None,
            )
            return _ResolvedDetailTarget(
                media_id=canonical_media_id,
                season_number=resolved_season,
                source=MediaSourceName.douban,
                source_id=source_id,
                source_year=year,
            )

        if not search_title or not year or year <= 0:
            raise MediaNotFoundException()
        tmdb_id = await media_service.provider_service.mapping.get_tmdb_id(search_title, year, media_type)
        if not tmdb_id:
            media_service.provider_service.mapping.raise_tmdb_mapping_required(
                lookup,
                title=raw_title or search_title,
                year=year,
                search_query=build_loose_tmdb_search_title(search_title),
                season_number=explicit_season or parsed_title_season or (requested_season if media_type == MediaType.tv else None),
            )
        canonical_media_id = media_service.provider_service.mapping.canonical_tmdb_media_id(media_type, tmdb_id)
        resolved_source_season = explicit_season or parsed_title_season or requested_season or (1 if media_type == MediaType.tv else None)
        await media_service.provider_service.mapping.set_cached_tmdb_mapping(
            canonical_media_id,
            tmdb_id,
            None,
            source_id,
            resolved_source_season if media_type == MediaType.tv else None,
        )
        return _ResolvedDetailTarget(
            media_id=canonical_media_id,
            season_number=resolved_source_season,
            source=source,
            source_id=source_id,
            source_year=year,
        )

    def _default_detail_season(self, media: MediaFullInfo, year: int | None = None) -> int | None:
        if media.media_type != MediaType.tv:
            return None
        if media.season_number and media.season_number > 0:
            return int(media.season_number)
        if year:
            for season in media.seasons:
                air_date = season.air_date or ""
                if len(air_date) >= 4 and air_date[:4].isdigit() and int(air_date[:4]) == year:
                    return int(season.season_number)
        preferred = next((season for season in media.seasons if season.season_number == 1), None)
        if preferred:
            return 1
        available = sorted(
            int(season.season_number)
            for season in media.seasons
            if season.season_number is not None and season.season_number > 0
        )
        return available[0] if available else None

    async def _load_media(self, target: _ResolvedDetailTarget) -> _LoadedMedia:
        if target.media_id.media_type == MediaType.tv and target.season_number is None:
            if target.source is None:
                raise InvalidRequestException("backendErrors.seasonRequired")
            media, cache_mode = await media_service.info_with_cache_status(
                target.media_id,
                season_number=None,
                include_default_season_details=True,
                default_season_year=target.source_year,
            )
            if not media:
                raise MediaNotFoundException()
            resolved_season = self._default_detail_season(media, target.source_year)
            media = media_service.apply_season_context(media, resolved_season)
            media.viewed = media_service.is_viewed_media(media.media_id)
            return _LoadedMedia(media=media, cache_mode=cache_mode)
        media, cache_mode = await media_service.info_with_cache_status(
            target.media_id,
            season_number=target.season_number,
            include_default_season_details=target.media_id.media_type == MediaType.tv,
            default_season_year=target.source_year,
        )
        if not media:
            raise MediaNotFoundException()
        media = media_service.apply_season_context(media, target.season_number or self._default_detail_season(media))
        if target.source == MediaSourceName.douban and target.source_id:
            douban_vote_average = media.douban_vote_average
            douban_rating_count = media.douban_rating_count
            media = media.model_copy(update={
                "douban_id": target.source_id,
                "vote_average": douban_vote_average,
                "rating_count": douban_rating_count,
                "vote_count": douban_rating_count,
                "rating_source": "douban",
            })
        media.viewed = media_service.is_viewed_media(media.media_id)
        return _LoadedMedia(media=media, cache_mode=cache_mode)

    async def _load_side_data(
        self,
        timings: dict[str, float],
        media_id: MediaID,
        season_number: int | None,
        *,
        name_suffix: str = "",
    ) -> _PageSideData:
        target = MediaTarget(media_id=media_id, season_number=season_number)
        suffix = f"_{name_suffix}" if name_suffix else ""
        subscription_result, active_commands = await asyncio.gather(
            self._timed(timings, f"subscription{suffix}", subscription_query_service.get_current_state_view_and_config(target)),
            self._timed(timings, f"commands{suffix}", command_service.list_media_active_commands(media_id, season_number=season_number)),
        )
        subscription_state, subscription, download_config = subscription_result
        return _PageSideData(
            subscription_state=subscription_state,
            subscription=subscription,
            download_config=download_config,
            active_commands=active_commands,
        )

    async def _load_library_snapshot(
        self,
        timings: dict[str, float],
        media_id: MediaID,
        season_number: int | None,
    ) -> MediaLibrarySnapshot:
        return await self._timed(
            timings,
            "library_snapshot",
            library_service.get_media_library_snapshot(media_id, season=season_number),
        )

    async def _build_response(
        self,
        *,
        timings: dict[str, float],
        media: MediaFullInfo,
        effective_season_number: int | None,
        side_data: _PageSideData,
        active_tab: str,
    ) -> MediaDetailPageResponse:
        effective_media_id = media.media_id
        library_snapshot_task = asyncio.create_task(
            self._load_library_snapshot(timings, effective_media_id, effective_season_number)
        )
        library_snapshot = await library_snapshot_task
        overview, tab_data = await asyncio.gather(
            self._timed(timings, "overview", media_detail_overview_service.get_overview_for_media(
                media,
                season_number=effective_season_number,
                subscription_state=side_data.subscription_state,
                subscription_state_loaded=True,
                download_config=side_data.download_config,
                download_config_loaded=True,
                active_commands=side_data.active_commands,
                active_commands_loaded=True,
                library_snapshot=library_snapshot,
            )),
            self._timed(
                timings,
                "tab_data",
                self._load_tab_data(
                    effective_media_id,
                    effective_season_number,
                    active_tab,
                ),
            ),
        )
        return MediaDetailPageResponse(
            media=media,
            effective_season_number=effective_season_number,
            overview=overview,
            subscription=side_data.subscription,
            download_config=self._build_download_config_view(effective_media_id, effective_season_number, side_data.download_config),
            active_commands=side_data.active_commands,
            tab_data=tab_data,
        )

    async def _store_resolved_source_season(self, target: _ResolvedDetailTarget, season_number: int | None) -> None:
        if target.source is None or not target.source_id or target.media_id.media_type != MediaType.tv:
            return
        if season_number is None or season_number <= 0:
            return
        try:
            tmdb_id = int(target.media_id.id)
        except ValueError:
            return
        existing_mapping = (
            media_service.provider_service.mapping.mapping_repo.find_by_douban_id(
                target.source_id,
                target.media_id.media_type.value,
            )
            if target.source == MediaSourceName.douban
            else None
        )
        await media_service.provider_service.mapping.set_cached_tmdb_mapping(
            target.media_id,
            tmdb_id,
            existing_mapping.imdb_id if existing_mapping else None,
            target.source_id if target.source == MediaSourceName.douban else None,
            season_number,
            existing_mapping.episode_count_override if existing_mapping else None,
        )

    async def get_page(
        self,
        *,
        media_id: MediaID | None,
        source: MediaSourceName | None,
        source_id: str | None,
        media_type: MediaType | None,
        title: str | None,
        year: int | None,
        season_number: int | None,
        active_tab: str = "resources",
    ) -> MediaDetailPageResponse:
        request_started_at = time.perf_counter()
        timings: dict[str, float] = {}

        phase_started_at = time.perf_counter()
        target = await self._resolve_target(
            media_id=media_id,
            source=source,
            source_id=source_id,
            media_type=media_type,
            title=title,
            year=year,
            season_number=season_number,
        )
        self._record_elapsed(timings, "resolve_target", phase_started_at)

        media_task = asyncio.create_task(self._timed(timings, "load_media", self._load_media(target)))

        side_data_task = None
        if target.season_number is not None or target.media_id.media_type != MediaType.tv:
            side_data_task = asyncio.create_task(
                self._load_side_data(timings, target.media_id, target.season_number)
            )

        loaded_media = await media_task
        media = loaded_media.media
        effective_media_id = media.media_id
        effective_season_number = media.season_number if media.media_type == MediaType.tv else None
        if target.source is not None:
            await self._timed(timings, "store_source_season", self._store_resolved_source_season(target, effective_season_number))

        if side_data_task and effective_media_id == target.media_id and effective_season_number == target.season_number:
            side_data = await side_data_task
        else:
            if side_data_task:
                side_data_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await side_data_task
            side_data = await self._load_side_data(
                timings,
                effective_media_id,
                effective_season_number,
                name_suffix="effective_target",
            )

        phase_started_at = time.perf_counter()
        response = await self._build_response(
            timings=timings,
            media=media,
            effective_season_number=effective_season_number,
            side_data=side_data,
            active_tab=active_tab,
        )
        self._record_elapsed(timings, "response_build", phase_started_at)
        self._log_timing(
            timings=timings,
            started_at=request_started_at,
            branch="direct" if target.season_number == effective_season_number else "resolved_effective_target",
            active_tab=active_tab,
            target=target,
            effective_media_id=effective_media_id,
            effective_season_number=effective_season_number,
            media_cache_mode=loaded_media.cache_mode,
        )
        return response

    async def _load_tab_data(
        self,
        media_id: MediaID,
        season_number: int | None,
        active_tab: str,
    ) -> MediaDetailPageTabData:
        if active_tab == "tasks":
            return MediaDetailPageTabData(
                tasks=await task_view_service.list_media_task_views(media_id, season_number=season_number)
            )
        return MediaDetailPageTabData()

    def _build_download_config_view(
        self,
        media_id: MediaID,
        season_number: int | None,
        config: MediaDownloadConfig | None,
    ) -> MediaDownloadConfigView:
        return MediaDownloadConfigView(
            sub_id=config.sub_id if config else None,
            media_id=media_id,
            season_number=season_number,
            directory_id=config.directory_id if config else None,
            filter_config_id=config.filter_config_id if config else None,
            quality_profile_id=config.quality_profile_id if config else None,
            filters=config.filters if config else None,
            sites=config.sites if config else None,
            unmatched_rules=list(config.unmatched_rules) if config else [],
        )


media_detail_page_application_service = MediaDetailPageApplicationService()
