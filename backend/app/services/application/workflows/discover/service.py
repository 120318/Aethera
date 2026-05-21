from __future__ import annotations

import logging

from app.schemas.domain.discover import DiscoverList, DiscoverListMeta
from app.schemas.config import BrowseSource
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID, Provider
from app.schemas.integration.media.provider import ProviderSearchItem
from app.schemas.domain.search_models import MediaSearchResult
from app.services.platform.cache_service import cache_service
from app.services.domain.media import media_service
from app.services.config.settings_service import settings_service

logger = logging.getLogger("app.services.discover")

DISCOVER_LIST_CACHE_VERSION = "20260425_light_cards_single_line"

DOUBAN_LIST_KEYS = [
    "movie_showing",
    "movie_hot_gaia",
    "movie_soon",
    "movie_top250",
    "movie_scifi",
    "movie_comedy",
    "movie_action",
    "movie_love",
    "tv_hot",
    "tv_domestic",
    "tv_american",
    "tv_japanese",
    "tv_korean",
    "tv_animation",
    "tv_variety_show",
    "tv_chinese_best_weekly",
    "tv_global_best_weekly",
    "show_domestic",
    "show_foreign",
]

TMDB_LIST_KEYS = [
    "movie_popular",
    "movie_top_rated",
    "movie_now_playing",
    "movie_upcoming",
    "tv_popular",
    "tv_top_rated",
    "tv_on_the_air",
    "trending_movie_week",
    "trending_tv_week",
]

def _split_card_subtitle(raw: str | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    parts = [p.strip() for p in raw.split(" / ") if p.strip()]
    if parts and len(parts[0]) == 4 and parts[0].isdigit():
        parts = parts[1:]
    if parts:
        first_country = parts[0].replace("/", " ").split()
        if first_country:
            parts[0] = first_country[0]
    if len(parts) < 2:
        return None, None
    line1 = " / ".join(parts[:2]) if parts[0] or parts[1] else None
    line2 = None
    if len(parts) >= 4:
        director = parts[2]
        actors = parts[3]
        pieces = [p for p in [actors, director] if p]
        line2 = " / ".join(pieces) if pieces else None
    elif len(parts) == 3:
        line2 = parts[2] or None
    return line1 or None, line2 or None
class DiscoverService:
    def _media_type_for_key(self, key: str) -> MediaType:
        if key.startswith("tv_") or key.startswith("show_"):
            return MediaType.tv
        return MediaType.movie

    def _tmdb_media_type_for_key(self, key: str) -> MediaType:
        if key.startswith("tv_") or key.startswith("trending_tv_"):
            return MediaType.tv
        return MediaType.movie

    def _list_title_key(self, source: BrowseSource, key: str) -> str:
        source_name = "tmdb" if source == BrowseSource.tmdb else "douban"
        return f"discover.listTitles.{source_name}.{key}"

    def _get_source(self) -> BrowseSource:
        return settings_service.get_base_services_config().browse_source

    def _get_default_discover_keys(self, source: BrowseSource | None = None) -> list[str]:
        services = settings_service.get_base_services_config()
        source = source or services.browse_source
        source_config = services.themoviedb if source == BrowseSource.tmdb else services.douban
        discover_lists = list(source_config.discover_lists)
        if discover_lists:
            return discover_lists
        if source == BrowseSource.tmdb:
            return [
                "movie_popular",
                "tv_popular",
                "trending_movie_week",
                "trending_tv_week",
            ]
        return [
            "movie_hot_gaia",
            "tv_hot",
            "tv_animation",
            "tv_variety_show",
        ]

    def list_options(self, source: BrowseSource | None = None) -> list[DiscoverListMeta]:
        source = source or self._get_source()
        enabled_keys = set(self._get_default_discover_keys(source))
        list_keys = TMDB_LIST_KEYS if source == BrowseSource.tmdb else DOUBAN_LIST_KEYS
        return [
            DiscoverListMeta(key=key, title_key=self._list_title_key(source, key), enabled=key in enabled_keys)
            for key in list_keys
        ]

    def _map_item_to_search_result(self, key: str, item: ProviderSearchItem) -> MediaSearchResult | None:
        if not item.provider_id:
            return None
        if item.year is None:
            logger.debug("Skipping discover item without valid year: key=%s subject_id=%s title=%s", key, item.provider_id, item.title)
            return None

        media_type = self._media_type_for_key(key)
        title = item.title
        line1, line2 = _split_card_subtitle(item.subtitle)

        try:
            return MediaSearchResult(
                title=title,
                year=item.year,
                vote_average=item.rating.value,
                media_type=media_type,
                source="douban",
                source_id=item.provider_id,
                douban_id=item.provider_id,
                poster_path=item.poster_path,
                rating_count=item.rating.count,
                subtitle=item.subtitle,
                subtitle_line1=line1,
                subtitle_line2=line2,
            )
        except ValueError:
            logger.debug("Skipping invalid discover item: key=%s subject_id=%s title=%s", key, item.provider_id, item.title)
            return None

    def _map_tmdb_item_to_search_result(self, key: str, item: ProviderSearchItem) -> MediaSearchResult | None:
        if not item.provider_id or item.year is None:
            return None
        try:
            media_type = self._tmdb_media_type_for_key(key)
            return MediaSearchResult(
                media_id=MediaID(provider=Provider.tmdb, media_type=media_type, id=item.provider_id),
                source="tmdb",
                source_id=item.provider_id,
                title=item.title,
                year=item.year,
                vote_average=item.rating.value,
                media_type=media_type,
                poster_path=item.poster_path,
                overview=item.overview,
                original_language=item.original_language,
                genre_ids=item.genre_ids,
                rating_count=item.rating.count,
                subtitle=item.subtitle,
                subtitle_line1=item.subtitle,
                subtitle_line2=None,
            )
        except ValueError:
            logger.debug("Skipping invalid tmdb discover item: key=%s tmdb_id=%s title=%s", key, item.provider_id, item.title)
            return None

    async def _load_cached_list(self, source: BrowseSource, key: str, count: int) -> list[MediaSearchResult] | None:
        cache_id = self._discover_list_cache_key(key=key, count=count)
        try:
            cached = await cache_service.read(provider=source.value, cache_type="discover_list", identifier=cache_id)
        except (OSError, RuntimeError, ValueError):
            return None
        if not cached:
            return None
        try:
            return [MediaSearchResult.model_validate(item) for item in cached]
        except ValueError:
            return None

    async def _cache_list(self, source: BrowseSource, key: str, count: int, items: list[MediaSearchResult]) -> None:
        if not items:
            return
        cache_id = self._discover_list_cache_key(key=key, count=count)
        try:
            await cache_service.set(
                provider=source.value,
                cache_type="discover_list",
                identifier=cache_id,
                data=items,
                expire_seconds=3600,
            )
        except (OSError, RuntimeError, ValueError):
            return

    def _discover_list_cache_key(self, *, key: str, count: int) -> str:
        return f"{DISCOVER_LIST_CACHE_VERSION}:{key}:{count}"

    async def get_lists(self, keys: str | None, count: int) -> list[DiscoverList]:
        source = self._get_source()
        default_keys = self._get_default_discover_keys(source)
        wanted = [key.strip() for key in (keys.split(",") if keys else default_keys) if key.strip()]
        has_credentials = media_service.discover_available(source)
        results: list[DiscoverList] = []

        for key in wanted:
            supports_key = media_service.supports_discover_key(source, key)
            if not supports_key:
                raise ValueError(f"unsupported key: {key}")

            if not has_credentials:
                results.append(
                    DiscoverList(
                        key=key,
                        title_key=self._list_title_key(source, key),
                        items=[],
                        error="TMDB discovery service is currently unavailable" if source == BrowseSource.tmdb else "Douban discovery service is currently unavailable",
                    )
                )
                continue

            cached_items = await self._load_cached_list(source, key, count)
            if cached_items is not None:
                results.append(DiscoverList(key=key, title_key=self._list_title_key(source, key), items=cached_items))
                continue

            try:
                mapped: list[MediaSearchResult] = []
                raw_items = await media_service.discover_items(source, key, start=0, count=count)
                for raw_item in raw_items:
                    item = self._map_tmdb_item_to_search_result(key, raw_item) if source == BrowseSource.tmdb else self._map_item_to_search_result(key, raw_item)
                    if item:
                        mapped.append(item)

                await self._cache_list(source, key, count, mapped)
                results.append(DiscoverList(key=key, title_key=self._list_title_key(source, key), items=mapped))
            except (RuntimeError, ValueError) as exc:
                logger.error("Failed to fetch %s list %s: %s", source.value, key, exc)
                results.append(DiscoverList(key=key, title_key=self._list_title_key(source, key), items=[], error=str(exc)))

        all_items = [item for result in results for item in result.items]
        media_service.mark_viewed_search_results(all_items)
        return results


discover_service = DiscoverService()
