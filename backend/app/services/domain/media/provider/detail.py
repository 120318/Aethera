import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import TypeVar

import httpx

from app.schemas.domain.media import MediaFullInfo, MediaIdentity, SeasonDetails
from app.schemas.domain.media_source import MediaSourceLookup, MediaSourceName
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MovieReleaseDateDetail
from app.schemas.domain.vendor import Vendor
from app.schemas.exception import MediaNotFoundException
from app.schemas.integration.media.provider import ProviderMediaBundle, ProviderRating
from app.schemas.integration.media.provider import ProviderReleaseDateEntry, ProviderReleaseRegion
from app.schemas.media_id import MediaID, Provider
from app.services.domain.media.profile.context import media_profile_context_service
from app.services.domain.media.provider.clients import MediaProviderClients
from app.services.domain.media.provider.mapping import MediaProviderMapping
from app.services.domain.media.provider.normalization import (
    build_tmdb_media_info,
    dedupe_vendors,
    normalize_tmdb_vendors,
    resolve_tmdb_selected_season,
    subject_type,
)
from app.services.domain.media.provider.search import get_source_vendors
from app.services.integration.tmdb.schedule import tmdb_schedule_gateway
from app.utils import build_loose_tmdb_search_title, build_tmdb_search_title


logger = logging.getLogger("app.services.media.provider.detail")
T = TypeVar("T")


@dataclass(frozen=True)
class DoubanMediaContext:
    vendors: list[Vendor]
    rating: ProviderRating


class MediaProviderDetail:
    def __init__(
        self,
        *,
        clients: MediaProviderClients,
        mapping: MediaProviderMapping,
    ) -> None:
        self.clients = clients
        self.mapping = mapping

    async def info(
        self,
        mid: MediaID,
        *,
        season_number: int | None = None,
        include_default_season_details: bool = False,
        default_season_year: int | None = None,
    ) -> MediaFullInfo | None:
        started_at = time.perf_counter()
        timings: dict[str, float] = {}
        subject_type_value = subject_type(mid.media_type)
        if mid.provider != Provider.tmdb:
            return await self.info_from_source(MediaSourceLookup(source=MediaSourceName.douban, source_id=mid.id, media_type=mid.media_type))

        phase_started_at = time.perf_counter()
        cached_tmdb_id, cached_imdb_id, cached_douban_id, cached_season_number, cached_episode_count_override = await self.mapping.get_cached_tmdb_mapping(mid, season_number)
        effective_episode_count_override = (
            cached_episode_count_override
            if (
                mid.media_type == MediaType.tv
                and cached_season_number is not None
                and season_number is not None
                and int(cached_season_number) == int(season_number)
            )
            else None
        )
        timings["mapping_read"] = (time.perf_counter() - phase_started_at) * 1000
        effective_douban_id = cached_douban_id
        if mid.media_type == MediaType.tv:
            effective_douban_id = (
                cached_douban_id
                if (
                    season_number is not None
                    and cached_season_number is not None
                    and int(cached_season_number) == int(season_number)
                )
                else None
            )
        tmdb_id = cached_tmdb_id or self.mapping.parse_tmdb_media_id(mid)
        tmdb_bundle_task = asyncio.create_task(
            self._timed(
                timings,
                "tmdb_detail_bundle",
                self.get_tmdb_detail_bundle(
                    tmdb_id,
                    subject_type_value,
                    season_number=season_number if mid.media_type == MediaType.tv else None,
                    include_default_season_details=include_default_season_details if mid.media_type == MediaType.tv else False,
                    default_season_year=default_season_year if mid.media_type == MediaType.tv else None,
                ),
            )
        )
        douban_context_task = asyncio.create_task(
            self._load_douban_context(
                timings,
                douban_id=effective_douban_id,
                media_type=mid.media_type,
            )
        )
        try:
            details, tmdb_vendors = await tmdb_bundle_task
        except Exception:
            douban_context_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await douban_context_task
            raise
        if not details or not details.provider_id:
            douban_context_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await douban_context_task
            raise MediaNotFoundException()
        phase_started_at = time.perf_counter()
        external = details.external_ids or await self.clients.get_tmdb_client().get_external_ids(tmdb_id, subject_type_value)
        resolved_imdb_id = cached_imdb_id or (external.imdb_id if external else None)
        await self.mapping.set_cached_tmdb_mapping(mid, tmdb_id, resolved_imdb_id, cached_douban_id, cached_season_number, cached_episode_count_override)
        timings["mapping_write"] = (time.perf_counter() - phase_started_at) * 1000
        douban_context = await douban_context_task
        rating = douban_context.rating
        has_douban_rating = self.has_rating(rating)
        phase_started_at = time.perf_counter()
        media = media_profile_context_service.enrich_media(build_tmdb_media_info(
            mid=mid,
            details=details,
            imdb_id=resolved_imdb_id,
            vote_average=rating.value if effective_douban_id and has_douban_rating else (None if effective_douban_id else details.rating.value),
            rating_count=rating.count if effective_douban_id and has_douban_rating else (None if effective_douban_id else details.rating.count),
            rating_source="douban" if effective_douban_id else "tmdb",
            season_number=season_number if mid.media_type == MediaType.tv else None,
            vendors=dedupe_vendors(list(douban_context.vendors) + list(tmdb_vendors)),
            douban_id=effective_douban_id,
            episode_count_override=effective_episode_count_override,
        ))
        timings["build_enrich_media"] = (time.perf_counter() - phase_started_at) * 1000
        self._log_provider_timing(
            operation="info",
            started_at=started_at,
            media_id=mid,
            subject_type_value=subject_type_value,
            season_number=season_number,
            timings=timings,
        )
        return media

    async def info_from_source(self, lookup: MediaSourceLookup) -> MediaFullInfo | None:
        client = self.clients.get_douban_client()
        if not client:
            raise MediaNotFoundException()
        subject_type_value = subject_type(lookup.media_type)
        existing_mapping = self.mapping.mapping_repo.find_by_douban_id(lookup.source_id, lookup.media_type.value)
        if existing_mapping and existing_mapping.tmdb_id:
            canonical_media_id = self.mapping.canonical_tmdb_media_id(lookup.media_type, existing_mapping.tmdb_id)
            await self.mapping.set_cached_tmdb_mapping(
                canonical_media_id,
                existing_mapping.tmdb_id,
                existing_mapping.imdb_id,
                existing_mapping.douban_id,
                existing_mapping.season_number,
                existing_mapping.episode_count_override,
            )
            douban_context = await self._load_douban_context(
                {},
                douban_id=existing_mapping.douban_id or lookup.source_id,
                media_type=lookup.media_type,
            )
            has_douban_rating = self.has_rating(douban_context.rating)
            return await self.build_tmdb_detail_from_mapping(
                canonical_media_id,
                tmdb_id=existing_mapping.tmdb_id,
                imdb_id=existing_mapping.imdb_id,
                douban_id=existing_mapping.douban_id,
                season_number=existing_mapping.season_number,
                rating_value=douban_context.rating.value if has_douban_rating else None,
                rating_count=douban_context.rating.count if has_douban_rating else None,
                rating_source="douban",
                vendors=douban_context.vendors,
                episode_count_override=existing_mapping.episode_count_override if lookup.media_type == MediaType.tv else None,
            )
        try:
            detail = await client.get_subject_detail(lookup.source_id, subject_type_value)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            raise MediaNotFoundException() from exc
        if not detail:
            raise MediaNotFoundException()

        year = detail.year
        display_title = detail.title or ""
        title, season_number = build_tmdb_search_title(display_title, is_tv=lookup.media_type == MediaType.tv)
        loose_search_query = build_loose_tmdb_search_title(title)

        source_media_id = MediaID(provider=Provider.douban, media_type=lookup.media_type, id=lookup.source_id)
        media_identity = self.require_media_identity(source_media_id, title, year)
        title = media_identity.title
        year = media_identity.year

        tmdb_id, imdb_id, season_number = await self.mapping.resolve_tmdb_mapping(source_media_id, title, year, lookup.media_type, season_number)
        if not tmdb_id:
            self.mapping.raise_tmdb_mapping_required(
                lookup,
                title=display_title or title,
                year=year,
                search_query=loose_search_query,
                season_number=season_number,
            )
            return None

        tmdb_details, tmdb_vendors = await self.get_tmdb_detail_bundle(
            tmdb_id,
            subject_type_value,
            season_number=season_number if lookup.media_type == MediaType.tv else None,
        )
        if tmdb_details:
            if lookup.media_type == MediaType.tv:
                season_number = resolve_tmdb_selected_season(tmdb_details.seasons, season_number, year)
            resolved_imdb_id = imdb_id or (tmdb_details.external_ids.imdb_id if tmdb_details.external_ids else None)
            canonical_media_id = self.mapping.canonical_tmdb_media_id(lookup.media_type, tmdb_id)
            await self.mapping.set_cached_tmdb_mapping(
                canonical_media_id,
                tmdb_id,
                resolved_imdb_id,
                detail.provider_id,
                season_number,
                None,
            )
        else:
            self.mapping.raise_tmdb_mapping_required(
                lookup,
                title=display_title or title,
                year=year,
                search_query=loose_search_query,
                season_number=season_number,
            )
            return None

        douban_vendors = dedupe_vendors(detail.vendors or [])
        merged_vendors = douban_vendors + [
            vendor for vendor in tmdb_vendors
            if vendor.name and vendor.name not in {existing.name for existing in douban_vendors if existing.name}
        ]
        if tmdb_details and tmdb_details.provider_id:
            has_douban_rating = self.has_rating(detail.rating)
            return media_profile_context_service.enrich_media(build_tmdb_media_info(
                mid=self.mapping.canonical_tmdb_media_id(lookup.media_type, tmdb_id),
                details=tmdb_details,
                imdb_id=resolved_imdb_id,
                vote_average=detail.rating.value if has_douban_rating else None,
                rating_count=detail.rating.count if has_douban_rating else None,
                rating_source="douban",
                season_number=season_number,
                vendors=dedupe_vendors(merged_vendors),
                douban_id=detail.provider_id,
                episode_count_override=None,
            ))

        raise MediaNotFoundException()

    def has_rating(self, rating: ProviderRating) -> bool:
        value = rating.value
        return value is not None and value > 0

    async def _timed(self, timings: dict[str, float], name: str, awaitable: Awaitable[T]) -> T:
        started_at = time.perf_counter()
        try:
            return await awaitable
        finally:
            timings[name] = (time.perf_counter() - started_at) * 1000

    async def _load_douban_context(
        self,
        timings: dict[str, float],
        *,
        douban_id: str | None,
        media_type: MediaType,
    ) -> DoubanMediaContext:
        if not douban_id:
            timings["source_vendors"] = 0.0
            timings["douban_rating"] = 0.0
            return DoubanMediaContext(vendors=[], rating=ProviderRating())
        douban_lookup = MediaSourceLookup(source=MediaSourceName.douban, source_id=douban_id, media_type=media_type)
        vendors, rating = await asyncio.gather(
            self._timed(timings, "source_vendors", get_source_vendors(self.clients.get_douban_client(), douban_lookup)),
            self._timed(timings, "douban_rating", self.resolve_douban_rating(douban_id, media_type)),
        )
        return DoubanMediaContext(vendors=list(vendors), rating=rating)

    async def resolve_douban_rating(self, douban_id: str | None, media_type: MediaType) -> ProviderRating:
        if not douban_id:
            return ProviderRating()
        client = self.clients.get_douban_client()
        if not client:
            return ProviderRating()
        try:
            detail = await client.get_subject_detail(douban_id, subject_type(media_type))
        except (httpx.HTTPError, RuntimeError, ValueError):
            return ProviderRating()
        if not detail:
            return ProviderRating()
        if self.has_rating(detail.rating):
            return detail.rating
        return ProviderRating()

    async def build_tmdb_detail_from_mapping(
        self,
        media_id: MediaID,
        *,
        tmdb_id: int,
        imdb_id: str | None,
        douban_id: str | None,
        season_number: int | None,
        rating_value: float | None,
        rating_count: int | None,
        rating_source: str,
        vendors,
        episode_count_override: int | None = None,
    ) -> MediaFullInfo:
        started_at = time.perf_counter()
        timings: dict[str, float] = {}
        phase_started_at = time.perf_counter()
        details, tmdb_vendors = await self.get_tmdb_detail_bundle(
            tmdb_id,
            subject_type(media_id.media_type),
            season_number=season_number if media_id.media_type == MediaType.tv else None,
        )
        timings["tmdb_detail_bundle"] = (time.perf_counter() - phase_started_at) * 1000
        if not details or not details.provider_id:
            raise MediaNotFoundException()
        phase_started_at = time.perf_counter()
        if rating_value is None and rating_source == "douban":
            resolved_rating_value = None
            resolved_rating_count = None
        else:
            resolved_rating_value = rating_value if rating_value is not None else details.rating.value
            resolved_rating_count = rating_count if rating_count is not None else details.rating.count
        media = media_profile_context_service.enrich_media(build_tmdb_media_info(
            mid=media_id,
            details=details,
            imdb_id=imdb_id or details.external_ids.imdb_id,
            vote_average=resolved_rating_value,
            rating_count=resolved_rating_count,
            rating_source=rating_source,
            season_number=season_number if media_id.media_type == MediaType.tv else None,
            vendors=dedupe_vendors(list(vendors or []) + list(tmdb_vendors or [])),
            douban_id=douban_id,
            episode_count_override=episode_count_override if media_id.media_type == MediaType.tv else None,
        ))
        timings["build_enrich_media"] = (time.perf_counter() - phase_started_at) * 1000
        self._log_provider_timing(
            operation="build_from_mapping",
            started_at=started_at,
            media_id=media_id,
            subject_type_value=subject_type(media_id.media_type),
            season_number=season_number,
            timings=timings,
        )
        return media

    async def get_tmdb_detail_bundle(
        self,
        tmdb_id: int | None,
        subject_type_value: str,
        *,
        season_number: int | None = None,
        include_default_season_details: bool = False,
        default_season_year: int | None = None,
    ) -> tuple[ProviderMediaBundle | None, list]:
        if not tmdb_id:
            return None, []
        started_at = time.perf_counter()
        timings: dict[str, float] = {}
        tmdb_client = self.clients.get_tmdb_client()
        media_type = MediaType(subject_type_value)
        release_dates_task = (
            tmdb_schedule_gateway.get_movie_release_dates(tmdb_id)
            if media_type == MediaType.movie
            else self._empty_release_dates()
        )
        season_details_task = (
            tmdb_schedule_gateway.get_season_details(tmdb_id, season_number)
            if media_type == MediaType.tv and season_number and season_number > 0
            else self._empty_season_details()
        )
        details, watch_provider_payloads_by_region, release_dates, season_details = await asyncio.gather(
            tmdb_client.get_details_with_fallback(tmdb_id, subject_type_value),
            tmdb_schedule_gateway.get_watch_provider_payloads(tmdb_id, media_type, ["CN", "US"]),
            release_dates_task,
            season_details_task,
        )
        timings["fetch"] = (time.perf_counter() - started_at) * 1000
        if not details:
            return None, []
        if media_type == MediaType.tv and not season_details and include_default_season_details:
            resolved_season = self._default_season_number(details, default_season_year)
            if resolved_season:
                phase_started_at = time.perf_counter()
                season_details = await tmdb_schedule_gateway.get_season_details(tmdb_id, resolved_season)
                timings["default_season_detail"] = (time.perf_counter() - phase_started_at) * 1000
        phase_started_at = time.perf_counter()
        cn_vendors = watch_provider_payloads_by_region.get("CN")
        us_vendors = watch_provider_payloads_by_region.get("US")
        vendors = normalize_tmdb_vendors(tmdb_id, subject_type_value, cn_vendors, us_vendors)
        details = details.model_copy(
            update={
                "vendors": vendors,
                "premiere_release_date": self._select_release_date(release_dates, {1}) if media_type == MediaType.movie else None,
                "theatrical_limited_release_date": self._select_release_date(release_dates, {2}) if media_type == MediaType.movie else None,
                "theatrical_release_date": self._select_release_date(release_dates, {2, 3}) if media_type == MediaType.movie else None,
                "digital_release_date": self._select_release_date(release_dates, {4}) if media_type == MediaType.movie else None,
                "physical_release_date": self._select_release_date(release_dates, {5}) if media_type == MediaType.movie else None,
                "tv_release_date": self._select_release_date(release_dates, {6}) if media_type == MediaType.movie else None,
                "release_dates": self._flatten_release_dates(release_dates) if media_type == MediaType.movie else [],
                "selected_season_details": season_details if media_type == MediaType.tv else None,
            }
        )
        timings["normalize"] = (time.perf_counter() - phase_started_at) * 1000
        self._log_bundle_timing(
            tmdb_id=tmdb_id,
            subject_type_value=subject_type_value,
            season_number=season_number,
            timings=timings,
            started_at=started_at,
        )
        return details, vendors

    def _default_season_number(self, details: ProviderMediaBundle, year: int | None = None) -> int | None:
        if year:
            for season in details.seasons:
                air_date = season.air_date or ""
                if len(air_date) >= 4 and air_date[:4].isdigit() and int(air_date[:4]) == year:
                    return int(season.season_number)
        if any(season.season_number == 1 for season in details.seasons):
            return 1
        available = sorted(
            int(season.season_number)
            for season in details.seasons
            if season.season_number is not None and season.season_number > 0
        )
        return available[0] if available else None

    def _log_provider_timing(
        self,
        *,
        operation: str,
        started_at: float,
        media_id: MediaID,
        subject_type_value: str,
        season_number: int | None,
        timings: dict[str, float],
    ) -> None:
        total_ms = (time.perf_counter() - started_at) * 1000
        timing_text = " ".join(f"{key}_ms={value:.1f}" for key, value in sorted(timings.items()))
        logger.info(
            "media_provider_detail_timing operation=%s total_ms=%.1f media_id=%s subject_type=%s season=%s %s",
            operation,
            total_ms,
            media_id,
            subject_type_value,
            season_number,
            timing_text,
        )

    def _log_bundle_timing(
        self,
        *,
        tmdb_id: int,
        subject_type_value: str,
        season_number: int | None,
        timings: dict[str, float],
        started_at: float,
    ) -> None:
        total_ms = (time.perf_counter() - started_at) * 1000
        timing_text = " ".join(f"{key}_ms={value:.1f}" for key, value in sorted(timings.items()))
        logger.info(
            "tmdb_detail_bundle_timing total_ms=%.1f tmdb_id=%s subject_type=%s season=%s %s",
            total_ms,
            tmdb_id,
            subject_type_value,
            season_number,
            timing_text,
        )

    async def _empty_release_dates(self) -> list[ProviderReleaseRegion]:
        return []

    async def _empty_season_details(self) -> SeasonDetails | None:
        return None

    def _release_region_weight(self, region: ProviderReleaseRegion) -> int:
        code = (region.iso_3166_1 or "").upper()
        preferred_regions = ["CN", "US"]
        if code in preferred_regions:
            return preferred_regions.index(code)
        return len(preferred_regions)

    def _release_item_weight(self, item: ProviderReleaseDateEntry, target_types: set[int]) -> tuple[int, str]:
        release_type = int(item.type or 0)
        type_weight = 0 if release_type in target_types else 1
        release_date = str(item.release_date or "")[:10] if item.release_date else "9999-12-31"
        return type_weight, release_date

    def _select_release_date(self, regions: list[ProviderReleaseRegion], target_types: set[int]) -> str | None:
        candidates: list[tuple[int, int, str]] = []
        for region in regions:
            region_weight = self._release_region_weight(region)
            for item in region.release_dates:
                release_type = int(item.type or 0)
                release_date = str(item.release_date or "")[:10] if item.release_date else None
                if release_type in target_types and release_date:
                    item_weight, item_date = self._release_item_weight(item, target_types)
                    candidates.append((region_weight, item_weight, item_date))
        if not candidates:
            return None
        candidates.sort(key=lambda candidate: (candidate[0], candidate[1], candidate[2]))
        return candidates[0][2]

    def _flatten_release_dates(self, regions: list[ProviderReleaseRegion]) -> list[MovieReleaseDateDetail]:
        details: list[MovieReleaseDateDetail] = []
        for region in regions:
            region_code = (region.iso_3166_1 or "").upper() or None
            for item in region.release_dates:
                release_date = str(item.release_date or "")[:10] if item.release_date else None
                if not release_date:
                    continue
                details.append(
                    MovieReleaseDateDetail(
                        region=region_code,
                        type=item.type,
                        release_date=release_date,
                        certification=item.certification,
                        note=item.note,
                        descriptors=list(item.descriptors or []),
                        language=item.iso_639_1,
                    )
                )
        details.sort(
            key=lambda item: (
                self._release_region_weight(ProviderReleaseRegion(iso_3166_1=item.region)),
                int(item.type or 0),
                item.release_date or "9999-12-31",
            )
        )
        return details

    def require_media_identity(self, media_id: MediaID, title: str | None, year: int | None) -> MediaIdentity:
        if title is None or not title.strip() or year is None or year <= 0:
            raise MediaNotFoundException()
        try:
            return MediaIdentity(media_id=media_id, title=title, year=year)
        except ValueError as exc:
            raise MediaNotFoundException() from exc
