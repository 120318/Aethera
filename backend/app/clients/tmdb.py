import asyncio
import logging
import time
from collections.abc import Callable
from typing import TypeVar

import httpx
from app.clients.base import BaseClient
from app.schemas.config import TMDBConfig
from app.schemas.domain.media import Avatar, EpisodeInfo, MediaSeasonInfo, PersonInfo, SeasonDetails
from app.schemas.domain.media_types import MediaType
from app.schemas.integration.media.provider import (
    ProviderExternalIds,
    ProviderMediaBundle,
    ProviderPlatformInfo,
    ProviderRating,
    ProviderReleaseDateEntry,
    ProviderReleaseRegion,
    ProviderSearchItem,
    ProviderWatchProviders,
)
from app.schemas.integration.media.tmdb import (
    TMDBAggregateCast,
    TMDBCast,
    TMDBCreator,
    TMDBCrew,
    TMDBDetails,
    TMDBEpisode,
    TMDBExternalIDs,
    TMDBRegionWatchProviders,
    TMDBSearchResponse,
    TMDBSeasonDetails,
    TMDBReleaseDatesResponse,
    TMDBWatchProvidersResponse,
)
from app.schemas.domain.vendor import Vendor

T = TypeVar("T")

class TMDBClient(BaseClient):
    def __init__(self, config: TMDBConfig | None) -> None:
        self.config = config
        self.api_key = config.api_key if config else ""
        self.base_url = "https://api.themoviedb.org/3"
        self.timeout = 10
        self.watch_provider_timeout = 2

    def get_id(self) -> str:
        return "tmdb"

    def _safe_log_params(self, params: dict | None) -> dict:
        if not params:
            return {}
        return {key: ("***" if key == "api_key" else value) for key, value in params.items()}

    async def _get_response(self, operation: str, url: str, params: dict | None = None, *, timeout: float | None = None) -> httpx.Response:
        logger = logging.getLogger("app.clients.tmdb")
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
                response = await client.get(url, params=params)
        except httpx.HTTPError:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "TMDB request failed operation=%s elapsed_ms=%.1f url=%s params=%s",
                operation,
                elapsed_ms,
                url,
                self._safe_log_params(params),
            )
            raise
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.debug(
            "TMDB request completed operation=%s status=%s elapsed_ms=%.1f url=%s params=%s",
            operation,
            response.status_code,
            elapsed_ms,
            url,
            self._safe_log_params(params),
        )
        return response

    def _subject_type(self, media_type: str) -> MediaType:
        return MediaType.movie if media_type == "movie" else MediaType.tv

    def _avatar(self, profile_path: str | None) -> Avatar | None:
        if not profile_path:
            return None
        return Avatar(
            large=f"https://image.tmdb.org/t/p/w500{profile_path}",
            normal=f"https://image.tmdb.org/t/p/w185{profile_path}",
        )

    def _provider_logo(self, logo_path: str | None) -> str | None:
        if not logo_path:
            return None
        return f"https://image.tmdb.org/t/p/original{logo_path}"

    def _runtime_string(self, details: TMDBDetails, media_type: str) -> str | None:
        if media_type == "movie":
            return str(details.runtime) if details.runtime is not None else None
        if details.episode_run_time:
            return str(details.episode_run_time[0])
        return None

    def _normalize_cast(self, cast_members: list[TMDBCast] | None, limit: int | None = None) -> list[PersonInfo]:
        members = cast_members or []
        people = members if limit is None else members[:limit]
        return [
            PersonInfo(
                name=member.name,
                id=str(member.id),
                avatar=self._avatar(member.profile_path),
                character=member.character,
            )
            for member in people
            if member and member.name
        ]

    def _normalize_aggregate_cast(self, cast_members: list[TMDBAggregateCast] | None, limit: int | None = None) -> list[PersonInfo]:
        members = cast_members or []
        people = members if limit is None else members[:limit]
        normalized: list[PersonInfo] = []
        for member in people:
            if not member or not member.name:
                continue
            character = next((role.character for role in (member.roles or []) if role and role.character), None)
            normalized.append(
                PersonInfo(
                    name=member.name,
                    id=str(member.id),
                    avatar=self._avatar(member.profile_path),
                    character=character,
                )
            )
        return normalized

    def _normalize_directors(self, crew_members: list[TMDBCrew] | None) -> list[PersonInfo]:
        directors = [
            member
            for member in (crew_members or [])
            if member and member.name and ((member.job or "") == "Director" or (member.department or "") == "Directing")
        ]
        deduped: list[PersonInfo] = []
        seen: set[str] = set()
        for member in directors:
            key = str(member.id)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(
                PersonInfo(
                    name=member.name,
                    id=key,
                    avatar=self._avatar(member.profile_path),
                    roles=[member.job] if member.job else [],
                )
            )
        return deduped

    def _normalize_creators(self, creators: list[TMDBCreator] | None) -> list[PersonInfo]:
        normalized: list[PersonInfo] = []
        seen: set[str] = set()
        for creator in creators or []:
            if not creator or not creator.name:
                continue
            key = str(creator.id or creator.name)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                PersonInfo(
                    name=creator.name,
                    id=str(creator.id) if creator.id is not None else key,
                    avatar=self._avatar(creator.profile_path),
                    roles=["Creator"],
                )
            )
        return normalized

    def _normalize_studios(self, details: TMDBDetails) -> list[str]:
        return [company.name for company in (details.production_companies or []) if company.name]

    def _normalize_seasons(self, details: TMDBDetails) -> list[MediaSeasonInfo]:
        seasons: list[MediaSeasonInfo] = []
        for season in details.seasons or []:
            if season.season_number is None or season.season_number <= 0:
                continue
            seasons.append(
                MediaSeasonInfo(
                    season_number=season.season_number,
                    name=season.name,
                    air_date=season.air_date,
                    episode_count=season.episode_count,
                    poster_path=season.poster_path,
                )
            )
        seasons.sort(key=lambda item: item.season_number)
        return seasons

    def _to_episode_info(self, episode: TMDBEpisode | None) -> EpisodeInfo | None:
        if not episode or episode.season_number is None or episode.season_number <= 0:
            return None
        if episode.episode_number is None or episode.episode_number <= 0:
            return None
        return EpisodeInfo(
            id=int(episode.id) if episode.id is not None else None,
            season_number=episode.season_number,
            episode_number=episode.episode_number,
            air_date=episode.air_date,
            title=episode.name,
            overview=episode.overview,
            runtime=episode.runtime,
            still_path=episode.still_path,
            vote_average=episode.vote_average,
            vote_count=episode.vote_count,
        )

    def _to_season_details(self, season: TMDBSeasonDetails | None) -> SeasonDetails | None:
        if not season or season.season_number is None or season.season_number <= 0:
            return None
        episodes = [episode for episode in (self._to_episode_info(item) for item in (season.episodes or [])) if episode]
        return SeasonDetails(
            id=int(season.id) if season.id is not None else None,
            season_number=season.season_number,
            name=season.name,
            overview=season.overview,
            air_date=season.air_date,
            poster_path=season.poster_path,
            episode_count=len(episodes) if episodes else None,
            episodes=episodes,
        )

    def _to_external_ids(self, external: TMDBExternalIDs | None) -> ProviderExternalIds:
        if not external:
            return ProviderExternalIds()
        return ProviderExternalIds(
            imdb_id=external.imdb_id,
            tvdb_id=str(external.tvdb_id) if external.tvdb_id is not None else None,
        )

    def _to_watch_providers(self, payload: TMDBRegionWatchProviders | None, region: str) -> ProviderWatchProviders:
        if not payload:
            return ProviderWatchProviders()

        def convert(item) -> ProviderPlatformInfo | None:
            if not item.provider_name:
                return None
            return ProviderPlatformInfo(
                id=str(item.provider_id) if item.provider_id is not None else None,
                name=item.provider_name,
                logo=self._provider_logo(item.logo_path),
                url=payload.link,
                region=region.upper(),
            )

        return ProviderWatchProviders(
            link=payload.link,
            flatrate=[platform for platform in (convert(item) for item in payload.flatrate) if platform],
            ads=[platform for platform in (convert(item) for item in payload.ads) if platform],
            free=[platform for platform in (convert(item) for item in payload.free) if platform],
            buy=[platform for platform in (convert(item) for item in payload.buy) if platform],
            rent=[platform for platform in (convert(item) for item in payload.rent) if platform],
        )

    def _to_release_regions(self, payload: TMDBReleaseDatesResponse) -> list[ProviderReleaseRegion]:
        return [
            ProviderReleaseRegion(
                iso_3166_1=region.iso_3166_1,
                release_dates=[
                    ProviderReleaseDateEntry(
                        type=item.type,
                        release_date=item.release_date,
                        certification=item.certification,
                        note=item.note,
                        descriptors=list(item.descriptors or []),
                        iso_639_1=item.iso_639_1,
                    )
                    for item in region.release_dates
                ],
            )
            for region in payload.results
        ]

    def _details_need_fallback(self, details: TMDBDetails, media_type: str) -> bool:
        common_missing = any(
            value in (None, "", [])
            for value in (
                details.overview,
                details.poster_path,
                details.backdrop_path,
                details.status,
                details.genres,
                details.external_ids,
                details.credits,
            )
        )
        if common_missing:
            return True

        if media_type == "movie":
            return any(
                value in (None, "", [])
                for value in (
                    details.title,
                    details.release_date,
                )
            )

        return any(
            value in (None, "", [])
            for value in (
                details.name,
                details.first_air_date,
                details.number_of_episodes,
                details.seasons,
                details.seasons_count,
            )
        )

    def _primary_logo_path(self, details: TMDBDetails) -> str | None:
        logos = details.images.logos if details.images else []
        if not logos:
            return None

        def sort_key(item):
            zh_priority = 0 if item.iso_639_1 in ("zh", "cn", "zh-CN") else 1
            return (
                zh_priority,
                -(item.vote_average or 0),
                -(item.vote_count or 0),
            )

        best = sorted(logos, key=sort_key)[0]
        return best.file_path

    def _primary_backdrop_path(self, details: TMDBDetails) -> str | None:
        if details.backdrop_path:
            return details.backdrop_path
        backdrops = details.images.backdrops if details.images else []
        if not backdrops:
            return None

        def sort_key(item):
            zh_priority = 0 if item.iso_639_1 in ("zh", "cn", "zh-CN", None) else 1
            return (
                zh_priority,
                -(item.vote_average or 0),
                -(item.vote_count or 0),
            )

        best = sorted(backdrops, key=sort_key)[0]
        return best.file_path

    def _merge_episode(self, primary: TMDBEpisode, fallback: TMDBEpisode) -> TMDBEpisode:
        updates = {}
        if not primary.name and fallback.name:
            updates["name"] = fallback.name
        if not primary.overview and fallback.overview:
            updates["overview"] = fallback.overview
        if not primary.air_date and fallback.air_date:
            updates["air_date"] = fallback.air_date
        if not primary.still_path and fallback.still_path:
            updates["still_path"] = fallback.still_path
        if not primary.runtime and fallback.runtime:
            updates["runtime"] = fallback.runtime
        if not primary.vote_average and fallback.vote_average:
            updates["vote_average"] = fallback.vote_average
        if not primary.vote_count and fallback.vote_count:
            updates["vote_count"] = fallback.vote_count
        if not primary.crew and fallback.crew:
            updates["crew"] = fallback.crew
        if not primary.guest_stars and fallback.guest_stars:
            updates["guest_stars"] = fallback.guest_stars
        if not primary.id and fallback.id:
            updates["id"] = fallback.id
        return primary.model_copy(update=updates)

    def _merge_season(self, primary: TMDBSeasonDetails, fallback: TMDBSeasonDetails) -> TMDBSeasonDetails:
        updates = {}
        if not primary.name and fallback.name:
            updates["name"] = fallback.name
        if not primary.overview and fallback.overview:
            updates["overview"] = fallback.overview
        if not primary.air_date and fallback.air_date:
            updates["air_date"] = fallback.air_date
        if not primary.poster_path and fallback.poster_path:
            updates["poster_path"] = fallback.poster_path
        if not primary.season_number and fallback.season_number:
            updates["season_number"] = fallback.season_number
        if not primary.id and fallback.id:
            updates["id"] = fallback.id
        if not primary.episodes and fallback.episodes:
            updates["episodes"] = fallback.episodes
        return primary.model_copy(update=updates)

    def _merge_details(self, primary: TMDBDetails, fallback: TMDBDetails) -> TMDBDetails:
        updates = {}
        for field in (
            "title",
            "name",
            "original_title",
            "original_name",
            "overview",
            "poster_path",
            "backdrop_path",
            "vote_average",
            "vote_count",
            "status",
            "original_language",
            "runtime",
            "episode_run_time",
            "number_of_episodes",
            "production_companies",
            "networks",
            "created_by",
            "genres",
            "seasons",
            "seasons_count",
            "release_date",
            "first_air_date",
            "next_episode_to_air",
            "external_ids",
            "images",
            "credits",
            "aggregate_credits",
        ):
            if getattr(primary, field) in (None, "", []) and getattr(fallback, field) not in (None, "", []):
                updates[field] = getattr(fallback, field)
        return primary.model_copy(update=updates)

    async def _request_tmdb_payload(
        self,
        request: Callable[[], object],
        *,
        failure_log: str,
    ) -> tuple[object | None, bool]:
        logger = logging.getLogger("app.clients.tmdb")
        try:
            return await request(), False
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("%s: %s", failure_log, exc)
            return None, True

    async def get_details_with_fallback(self, tmdb_id: int, media_type: str) -> ProviderMediaBundle | None:
        zh_result, fallback_result = await asyncio.gather(
            self._get_details_raw(tmdb_id, media_type, language="zh-CN"),
            self._get_details_raw(tmdb_id, media_type, language="en-US"),
        )
        details, failed = zh_result
        fallback, fallback_failed = fallback_result
        if failed and fallback_failed:
            return None
        if not details or not details.id:
            details = fallback
        elif fallback and fallback.id and self._details_need_fallback(details, media_type):
            details = self._merge_details(details, fallback)
        if not details or not details.id:
            return None
        return self._to_media_bundle(details, media_type)

    async def get_episode_details_with_fallback(self, tmdb_id: int, season_number: int, episode_number: int) -> EpisodeInfo | None:
        episode, failed = await self._get_episode_details_raw(tmdb_id, season_number, episode_number, language="zh-CN")
        if failed:
            return None
        if not episode:
            fallback, fallback_failed = await self._get_episode_details_raw(tmdb_id, season_number, episode_number, language="en-US")
            if fallback_failed:
                return None
            return self._to_episode_info(fallback)
        if episode.name and episode.overview:
            return self._to_episode_info(episode)
        fallback, fallback_failed = await self._get_episode_details_raw(tmdb_id, season_number, episode_number, language="en-US")
        if fallback_failed:
            return None
        return self._to_episode_info(self._merge_episode(episode, fallback) if fallback else episode)

    async def get_season_details_with_fallback(self, tmdb_id: int, season_number: int) -> SeasonDetails | None:
        zh_result, fallback_result = await asyncio.gather(
            self._get_season_details_raw(tmdb_id, season_number, language="zh-CN"),
            self._get_season_details_raw(tmdb_id, season_number, language="en-US"),
        )
        season, failed = zh_result
        fallback, fallback_failed = fallback_result
        if failed and fallback_failed:
            return None
        if not season:
            return self._to_season_details(fallback)
        if fallback and fallback.id and (not season.name or not season.overview):
            season = self._merge_season(season, fallback)
        return self._to_season_details(season)

    def _to_search_item(self, item, media_type: str) -> ProviderSearchItem:
        year = int(str((item.release_date or item.first_air_date or ""))[:4]) if (item.release_date or item.first_air_date or "")[:4].isdigit() else None
        return ProviderSearchItem(
            provider_id=str(item.id),
            title=item.title or item.name or "",
            year=year,
            media_type=self._subject_type(media_type),
            rating=ProviderRating(value=item.vote_average, count=item.vote_count),
            poster_path=item.poster_path,
            overview=item.overview,
            original_language=item.original_language,
            genre_ids=item.genre_ids,
            subtitle=None,
        )

    def _to_media_bundle(self, details: TMDBDetails, media_type: str, vendors: list[Vendor] | None = None) -> ProviderMediaBundle:
        credits = details.credits or None
        aggregate_credits = details.aggregate_credits or None
        directors = self._normalize_directors(credits.crew if credits else [])
        if not directors and media_type == "tv":
            directors = self._normalize_creators(details.created_by)
        actors = self._normalize_cast(credits.cast if credits else [])
        if media_type == "tv" and aggregate_credits and aggregate_credits.cast:
            actors = self._normalize_aggregate_cast(aggregate_credits.cast)
        return ProviderMediaBundle(
            provider_id=str(details.id or ""),
            title=details.title or details.name or "",
            original_title=details.original_title or details.original_name,
            media_type=self._subject_type(media_type),
            overview=details.overview,
            poster_path=details.poster_path,
            backdrop_path=self._primary_backdrop_path(details),
            logo_path=self._primary_logo_path(details),
            rating=ProviderRating(value=details.vote_average, count=details.vote_count),
            status=details.status,
            original_language=details.original_language,
            runtime=self._runtime_string(details, media_type),
            episodes_count=details.number_of_episodes,
            seasons_count=details.seasons_count,
            release_date=details.release_date,
            first_air_date=details.first_air_date,
            genres=[genre.name for genre in (details.genres or []) if genre.name],
            actors=actors,
            directors=directors,
            studios=self._normalize_studios(details),
            networks=[
                ProviderPlatformInfo(
                    id=str(network.id) if network.id is not None else None,
                    name=network.name,
                    logo=self._provider_logo(network.logo_path),
                )
                for network in (details.networks or [])
                if network.name
            ],
            seasons=self._normalize_seasons(details),
            next_episode_to_air=self._to_episode_info(details.next_episode_to_air),
            external_ids=self._to_external_ids(details.external_ids),
            vendors=vendors or [],
        )

    async def _get_episode_details_raw(self, tmdb_id: int, season_number: int, episode_number: int, language: str = "zh-CN") -> tuple[TMDBEpisode | None, bool]:
        logger = logging.getLogger("app.clients.tmdb")
        url = f"{self.base_url}/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}"
        params = {"api_key": self.api_key, "language": language}
        logger.debug("TMDB episode details url=%s params=%s", url, self._safe_log_params(params))
        async def request() -> TMDBEpisode | None:
            resp = await self._get_response("episode_details", url, params)
            if resp.status_code != 200:
                logger.warning(f"TMDB get episode details failed: {resp.status_code} {url}")
                return None
            return TMDBEpisode.model_validate(resp.json())
        payload, failed = await self._request_tmdb_payload(request, failure_log="Failed to get episode details")
        return payload, failed

    async def _get_season_details_raw(self, tmdb_id: int, season_number: int, language: str = "zh-CN") -> tuple[TMDBSeasonDetails | None, bool]:
        logger = logging.getLogger("app.clients.tmdb")
        url = f"{self.base_url}/tv/{tmdb_id}/season/{season_number}"
        params = {"api_key": self.api_key, "language": language}
        logger.debug("TMDB season details url=%s params=%s", url, self._safe_log_params(params))
        async def request() -> TMDBSeasonDetails | None:
            resp = await self._get_response("season_details", url, params)
            if resp.status_code != 200:
                logger.warning(f"TMDB get season details failed: {resp.status_code} {url}")
                return None
            return TMDBSeasonDetails.model_validate(resp.json())
        payload, failed = await self._request_tmdb_payload(request, failure_log="Failed to get season details")
        return payload, failed

    async def _search_raw(self, media_type: str, query: str, year: int | None = None):
        logger = logging.getLogger("app.clients.tmdb")
        if not query:
            raise ValueError("query is required")
        if media_type not in ("movie", "tv"):
            raise ValueError("media_type must be 'movie' or 'tv'")
        url = f"{self.base_url}/search/{media_type}"
        params = {"api_key": self.api_key, "query": query, "language": "zh-CN"}
        if year:
            params["first_air_date_year" if media_type == "tv" else "year"] = year
        logger.debug("TMDB search url=%s params=%s", url, self._safe_log_params(params))
        resp = await self._get_response("search", url, params)
        if resp.status_code != 200:
            logger.warning(f"TMDB search failed: {resp.status_code} {url}")
            return []
        data = TMDBSearchResponse.model_validate(resp.json())
        return data.results

    async def _discover_page_raw(self, key: str, media_type: str, url: str, page: int) -> tuple[str, list]:
        params = {"api_key": self.api_key, "language": "zh-CN", "page": page}
        resp = await self._get_response(f"discover:{key}:page:{page}", url, params)
        if resp.status_code != 200:
            logging.getLogger("app.clients.tmdb").warning("TMDB discover failed: %s %s page=%s", resp.status_code, url, page)
            return media_type, []
        data = TMDBSearchResponse.model_validate(resp.json())
        return media_type, data.results

    async def _discover_raw(self, key: str, start: int = 0, count: int = 20) -> tuple[str, list]:
        endpoints = {
            "movie_popular": ("movie", "/movie/popular"),
            "movie_top_rated": ("movie", "/movie/top_rated"),
            "movie_now_playing": ("movie", "/movie/now_playing"),
            "movie_upcoming": ("movie", "/movie/upcoming"),
            "tv_popular": ("tv", "/tv/popular"),
            "tv_top_rated": ("tv", "/tv/top_rated"),
            "tv_on_the_air": ("tv", "/tv/on_the_air"),
            "trending_movie_week": ("movie", "/trending/movie/week"),
            "trending_tv_week": ("tv", "/trending/tv/week"),
        }
        if key not in endpoints:
            raise ValueError(f"unsupported tmdb discover key: {key}")
        if count <= 0:
            return endpoints[key][0], []
        media_type, path = endpoints[key]
        url = f"{self.base_url}{path}"
        page_size = 20
        first_page = start // page_size + 1
        last_page = (start + count - 1) // page_size + 1
        page_results = await asyncio.gather(
            *(self._discover_page_raw(key, media_type, url, page) for page in range(first_page, last_page + 1))
        )
        items = [item for _, results in page_results for item in results]
        offset = start % page_size
        return media_type, items[offset:offset + count]

    async def _get_external_ids_raw(self, tmdb_id: int, media_type: str) -> TMDBExternalIDs:
        logger = logging.getLogger("app.clients.tmdb")
        if media_type not in ("movie", "tv"):
            raise ValueError("media_type must be 'movie' or 'tv'")
        url = f"{self.base_url}/{ 'tv' if media_type == 'tv' else 'movie' }/{tmdb_id}/external_ids"
        params = {"api_key": self.api_key}
        logger.debug("TMDB external_ids url=%s params=%s", url, self._safe_log_params(params))
        resp = await self._get_response("external_ids", url, params)
        if resp.status_code != 200:
            logger.warning(f"TMDB external_ids failed: {resp.status_code} {url}")
            return TMDBExternalIDs()
        return TMDBExternalIDs.model_validate(resp.json())

    async def _get_details_raw(self, tmdb_id: int, media_type: str, language: str = "zh-CN") -> tuple[TMDBDetails | None, bool]:
        logger = logging.getLogger("app.clients.tmdb")
        if media_type not in ("movie", "tv"):
            raise ValueError("media_type must be 'movie' or 'tv'")
        url = f"{self.base_url}/{ 'tv' if media_type == 'tv' else 'movie' }/{tmdb_id}"
        append_to_response = "external_ids,images,credits"
        if media_type == "tv":
            append_to_response = f"{append_to_response},aggregate_credits"
        image_languages = [language]
        if "en" not in language.lower():
            image_languages.append("en")
        image_languages.append("null")
        params = {
            "api_key": self.api_key,
            "append_to_response": append_to_response,
            "language": language,
            "include_image_language": ",".join(image_languages),
        }
        logger.debug("TMDB details url=%s params=%s", url, self._safe_log_params(params))
        async def request() -> TMDBDetails:
            resp = await self._get_response("details", url, params)
            if resp.status_code != 200:
                logger.warning(f"TMDB get details failed: {resp.status_code} {url}")
                return TMDBDetails()
            return TMDBDetails.model_validate(resp.json())
        payload, failed = await self._request_tmdb_payload(request, failure_log="TMDB get details failed")
        return payload, failed

    async def _get_watch_providers_response_raw(self, tmdb_id: int, media_type: str) -> TMDBWatchProvidersResponse:
        logger = logging.getLogger("app.clients.tmdb")
        if media_type not in ("movie", "tv"):
            raise ValueError("media_type must be 'movie' or 'tv'")
        url = f"{self.base_url}/{ 'tv' if media_type == 'tv' else 'movie' }/{tmdb_id}/watch/providers"
        params = {"api_key": self.api_key}
        logger.debug("TMDB watch providers url=%s params=%s", url, self._safe_log_params(params))
        try:
            resp = await self._get_response("watch_providers", url, params, timeout=self.watch_provider_timeout)
            if resp.status_code != 200:
                logger.warning(f"TMDB watch providers failed: {resp.status_code} {url}")
                return TMDBWatchProvidersResponse()
            return TMDBWatchProvidersResponse.model_validate(resp.json())
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("TMDB watch providers failed: %s", exc)
            return TMDBWatchProvidersResponse()

    async def _get_watch_providers_raw(self, tmdb_id: int, media_type: str, region: str) -> TMDBRegionWatchProviders | None:
        data = await self._get_watch_providers_response_raw(tmdb_id, media_type)
        region_key = region.upper()
        return data.results[region_key] if region_key in data.results else None

    async def _get_movie_release_dates_raw(self, tmdb_id: int) -> TMDBReleaseDatesResponse:
        logger = logging.getLogger("app.clients.tmdb")
        url = f"{self.base_url}/movie/{tmdb_id}/release_dates"
        params = {"api_key": self.api_key}
        logger.debug(f"TMDB movie release dates url={url}")
        resp = await self._get_response("movie_release_dates", url, params)
        if resp.status_code != 200:
            logger.warning(f"TMDB movie release dates failed: {resp.status_code} {url}")
            return TMDBReleaseDatesResponse()
        return TMDBReleaseDatesResponse.model_validate(resp.json())

    async def get_episode_details(self, tmdb_id: int, season_number: int, episode_number: int, language: str = "zh-CN") -> EpisodeInfo | None:
        return self._to_episode_info(await self._get_episode_details_raw(tmdb_id, season_number, episode_number, language))

    async def get_season_details(self, tmdb_id: int, season_number: int, language: str = "zh-CN") -> SeasonDetails | None:
        return self._to_season_details(await self._get_season_details_raw(tmdb_id, season_number, language))

    async def search(self, media_type: str, query: str, year: int | None = None) -> list[ProviderSearchItem]:
        return [self._to_search_item(item, media_type) for item in await self._search_raw(media_type, query, year)]

    def supports_discover_key(self, key: str) -> bool:
        return key in {
            "movie_popular",
            "movie_top_rated",
            "movie_now_playing",
            "movie_upcoming",
            "tv_popular",
            "tv_top_rated",
            "tv_on_the_air",
            "trending_movie_week",
            "trending_tv_week",
        }

    async def discover_items(self, key: str, start: int = 0, count: int = 20) -> list[ProviderSearchItem]:
        media_type, items = await self._discover_raw(key, start=start, count=count)
        return [self._to_search_item(item, media_type) for item in items]

    async def get_external_ids(self, tmdb_id: int, media_type: str) -> ProviderExternalIds:
        return self._to_external_ids(await self._get_external_ids_raw(tmdb_id, media_type))

    async def get_details(self, tmdb_id: int, media_type: str, language: str = "zh-CN") -> ProviderMediaBundle | None:
        details, failed = await self._get_details_raw(tmdb_id, media_type, language)
        if failed:
            return None
        if not details or not details.id:
            return None
        return self._to_media_bundle(details, media_type)

    async def get_watch_providers(self, tmdb_id: int, media_type: str, region: str) -> ProviderWatchProviders | None:
        return self._to_watch_providers(await self._get_watch_providers_raw(tmdb_id, media_type, region), region)

    async def get_watch_providers_by_regions(
        self,
        tmdb_id: int,
        media_type: str,
        regions: list[str],
    ) -> dict[str, ProviderWatchProviders]:
        data = await self._get_watch_providers_response_raw(tmdb_id, media_type)
        payloads: dict[str, ProviderWatchProviders] = {}
        for region in regions:
            region_key = region.upper()
            payloads[region_key] = self._to_watch_providers(data.results.get(region_key), region_key)
        return payloads

    async def get_movie_release_dates(self, tmdb_id: int) -> list[ProviderReleaseRegion]:
        return self._to_release_regions(await self._get_movie_release_dates_raw(tmdb_id))

    async def test_connection(self) -> bool:
        logger = logging.getLogger("app.clients.tmdb")
        url = f"{self.base_url}/configuration"
        params = {"api_key": self.api_key}
        logger.debug("TMDB test connection url=%s", url)
        try:
            resp = await self._get_response("test_connection", url, params)
            return resp.status_code == 200
        except httpx.HTTPError as exc:
            logger.warning("TMDB test connection failed: %s", exc)
            return False
