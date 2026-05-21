from collections.abc import Callable
import logging

import httpx

from app.clients.douban import DoubanClient
from app.schemas.config import BrowseSource
from app.schemas.domain.media import MediaIdentity
from app.schemas.domain.media_source import MediaSourceLookup, MediaSourceName
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.search_models import MediaSearchResult
from app.schemas.domain.vendor import Vendor
from app.schemas.exception import ConfigurationException, MediaNotFoundException
from app.schemas.media_id import MediaID, Provider
from app.services.domain.media.provider.normalization import dedupe_vendors, subject_type

logger = logging.getLogger("app.services.media")


async def search_douban(
    *,
    client,
    query: str,
    media_type: MediaType | None,
    start: int,
    limit: int,
    year: int | None,
    require_media_identity: Callable[[MediaID, str | None, int | None], MediaIdentity],
    logger,
) -> list[MediaSearchResult]:
    try:
        if not client or not client.api_key:
            return []

        if year is None:
            items = await client.search_movie(q=query, start=start, count=limit)
        else:
            items = []
            required = start + limit
            batch_size = max(limit, 20)
            batch_start = 0
            while len(items) < required:
                batch_items = await client.search_movie(q=query, start=batch_start, count=batch_size)
                if not batch_items:
                    break
                for item in batch_items:
                    if item.year != year:
                        continue
                    if (
                        (media_type == MediaType.tv and item.media_type != MediaType.tv)
                        or (media_type == MediaType.movie and item.media_type != MediaType.movie)
                    ):
                        continue
                    items.append(item)
                if len(batch_items) < batch_size:
                    break
                batch_start += batch_size

        mapped: list[MediaSearchResult] = []
        for item in items:
            if (
                (media_type == MediaType.tv and item.media_type != MediaType.tv)
                or (media_type == MediaType.movie and item.media_type != MediaType.movie)
            ):
                continue
            sub = item.subtitle or ""
            s1, s2 = None, None
            if sub:
                pts = [part.strip() for part in sub.split(" / ") if part.strip()]
                if pts and len(pts[0]) == 4 and pts[0].isdigit():
                    pts = pts[1:]
                if pts:
                    fc = pts[0].replace("/", " ").split()
                    if fc:
                        pts[0] = fc[0]
                if len(pts) >= 2:
                    s1 = " / ".join(pts[:2])
                if len(pts) >= 4:
                    s2 = " / ".join([part for part in [pts[3], pts[2]] if part])
                elif len(pts) == 3:
                    s2 = pts[2]
            try:
                source_media_id = MediaID(provider=Provider.douban, id=item.provider_id, media_type=item.media_type)
                media_identity = require_media_identity(source_media_id, item.title, item.year)
            except MediaNotFoundException:
                continue
            mapped.append(
                MediaSearchResult(
                    source=BrowseSource.douban.value,
                    source_id=item.provider_id,
                    douban_id=item.provider_id,
                    title=media_identity.title,
                    year=media_identity.year,
                    vote_average=item.rating.value,
                    media_type=item.media_type,
                    poster_path=item.poster_path,
                    rating_count=item.rating.count,
                    subtitle=sub,
                    subtitle_line1=s1,
                    subtitle_line2=s2,
                )
            )
        return mapped[:limit] if year is None else mapped[start:start + limit]
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.warning("Douban search failed: query=%s media_type=%s error=%s", query, media_type.value if media_type else "all", exc)
        raise ConfigurationException("backendErrors.config.doubanSearchUnavailable") from exc


async def search_tmdb(
    *,
    client,
    query: str,
    media_type: MediaType | None,
    start: int,
    limit: int,
    year: int | None,
    canonical_tmdb_media_id: Callable[[MediaType, int], MediaID],
) -> list[MediaSearchResult]:
    try:
        if not client.api_key:
            return []
        search_types = [media_type] if media_type in {MediaType.movie, MediaType.tv} else [MediaType.movie, MediaType.tv]
        collected: list[MediaSearchResult] = []
        for search_type in search_types:
            items = await client.search(search_type.value, query, year=year)
            for item in items:
                if item.year is None or not item.title.strip():
                    continue
                media_id = canonical_tmdb_media_id(item.media_type, int(item.provider_id))
                collected.append(
                    MediaSearchResult(
                        media_id=media_id,
                        source=BrowseSource.tmdb.value,
                        source_id=item.provider_id,
                        title=item.title,
                        year=item.year,
                        vote_average=item.rating.value,
                        media_type=item.media_type,
                        poster_path=item.poster_path,
                        overview=item.overview,
                        original_language=item.original_language,
                        genre_ids=item.genre_ids,
                        rating_count=item.rating.count,
                        subtitle=item.subtitle,
                        subtitle_line1=item.subtitle,
                        subtitle_line2=None,
                    )
                )
        collected.sort(key=lambda item: item.vote_average or 0, reverse=True)
        return collected[start:start + limit]
    except (httpx.HTTPError, RuntimeError, ValueError):
        return []


async def get_source_vendors(client: DoubanClient | None, lookup: MediaSourceLookup) -> list[Vendor]:
    if lookup.source != MediaSourceName.douban or not client:
        return []
    try:
        detail = await client.get_subject_detail(lookup.source_id, subject_type(lookup.media_type))
    except (httpx.HTTPError, RuntimeError, ValueError):
        logger.warning("Failed to get douban vendors for %s:%s", lookup.media_type.value, lookup.source_id)
        return []
    return dedupe_vendors(detail.vendors or []) if detail else []
