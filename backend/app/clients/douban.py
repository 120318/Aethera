"""text Frodo API text.

text HTTP text，text.
"""
import base64
import hashlib
import hmac
import logging
import random
import time
from datetime import datetime
from typing import Literal
from urllib.parse import quote, urlparse

import httpx
from app.clients.base import BaseClient
from app.schemas.config import DoubanConfig
from app.schemas.domain.media import Avatar, PersonInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.integration.media.provider import ProviderCredits, ProviderMediaDetail, ProviderRating, ProviderSearchItem
from app.schemas.domain.vendor import Vendor
from app.schemas.integration.media.douban import (
    DoubanCelebritiesResponse,
    DoubanRawCollectionItemsResponse,
    DoubanDetail,
    DoubanIMDBLookupResponse,
    DoubanSearchResult,
)
from app.services.config.settings_service import settings_service

logger = logging.getLogger(__name__)


def _decode_segments(parts: list[str]) -> str:
    return "".join(base64.b64decode(part.encode("ascii")).decode("utf-8") for part in parts)


class DoubanClient(BaseClient):
    """Internal helper."""

    BASE_URL = "https://frodo.douban.com/api/v2"
    IMDB_URL = "https://api.douban.com/v2/movie/imdb"
    DISCOVER_COLLECTION_KEYS = frozenset(
        {
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
            "show_hot",
            "show_domestic",
            "show_foreign",
            "book_bestseller",
            "book_top250",
            "book_fiction_hot_weekly",
            "book_nonfiction_hot_weekly",
            "music_single",
        }
    )

    @staticmethod
    def _fallback_pair() -> tuple[str, str]:
        left = ["MGRhZA==", "NTUxZQ==", "YzBmOA==", "NGVkMA==", "MjkwNw==", "ZmY1Yw==", "NDJlOA==", "ZWM3MA=="]
        right = ["YmY3ZA==", "ZGRjNw==", "YzljZg==", "ZTZmNw=="]
        return _decode_segments(left), _decode_segments(right)

    def __init__(self, config: DoubanConfig | None = None) -> None:
        """text
        
        Args:
            config: text
        """
        self.config = config
        fallback_key, fallback_secret = self._fallback_pair()
        self.api_key = fallback_key
        self.api_secret = fallback_secret
        self.clients = [
            "api-client/1 com.douban.frodo/7.18.0(230) Android/22 product/MI 9 vendor/Xiaomi model/MI 9 brand/Android  rom/miui6  network/wifi  platform/mobile nd/1",
            "api-client/1 com.douban.frodo/7.1.0(205) Android/29 product/perseus vendor/Xiaomi model/Mi MIX 3  rom/miui6  network/wifi  platform/mobile nd/1",
            "api-client/1 com.douban.frodo/7.3.0(207) Android/22 product/MI 9 vendor/Xiaomi model/MI 9 brand/Android  rom/miui6  network/wifi  platform/mobile nd/1",
        ]
        self.timeout = 10

    def get_id(self) -> str:
        """identifier
        
        Returns:
            str: identifier
        """
        return 'douban'
    
    async def test_connection(self) -> bool:
        """textAPItext
        
        Returns:
            bool: textTrue，textFalse
        """
        if not self.api_key or not self.api_secret:
            return False
        
        try:
            # Internal note.
            result = await self.search_movie(q="test", count=1)
            return result is not None
        except (httpx.HTTPError, RuntimeError, ValueError):
            return False

    async def get_movie_by_imdbid(self, imdbid: str) -> DoubanIMDBLookupResponse | None:
        """Internal helper."""
        url = f"{self.IMDB_URL}/{imdbid}"
        
        # Internal note.
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "Cookie": "bid=J9zb1zA5sJc",  # Internal note.
            "User-Agent": random.choice(self.clients)
        }
        
        # Internal note.
        data = {
            "apikey": self.api_key
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Internal note.
                resp = await client.post(url, headers=headers, data=data)
                
                if resp.status_code == 404:
                    return None
                
                if resp.status_code != 200:
                    raise RuntimeError(f"Douban IMDb API error: status={resp.status_code}, body={resp.text[:200]}")
                
                return DoubanIMDBLookupResponse.model_validate(resp.json())
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            logger.error("Failed to get douban by imdb %s: %s", imdbid, exc)
            raise

    def _gen_udid(self) -> str:
        """Internal helper."""
        return ''.join(random.choices('abcdef0123456789', k=32))

    def _gen_sign(self, url: str, ts: str, method: str = 'GET') -> str:
        """Internal helper."""
        url_path = urlparse(url).path
        raw_sign = '&'.join([method.upper(), quote(url_path, safe=''), ts])
        sign = base64.b64encode(
            hmac.new(self.api_secret.encode(), raw_sign.encode(), hashlib.sha1).digest()
        ).decode()
        return sign

    def _build_common_params(self, url: str, ts: str, method: str = 'GET') -> tuple[dict[str, str], dict[str, str]]:
        """text
        
        Returns:
            tuple: (params, headers)
        """
        client_str = random.choice(self.clients)
        udid = self._gen_udid()
        sign = self._gen_sign(url, ts, method)
        
        params = {
            "apiKey": self.api_key,
            "_ts": ts,
            "os_rom": "android",
            "client": client_str,
            "udid": udid,
            "_sig": sign,
        }
        
        headers = {"User-Agent": client_str}
        
        return params, headers

    def supports_discover_key(self, key: str) -> bool:
        return key in self.DISCOVER_COLLECTION_KEYS

    def _parse_year(self, raw: object | None) -> int | None:
        if type(raw) is int and raw > 0:
            return raw
        if type(raw) is str and raw.isdigit():
            value = int(raw)
            return value if value > 0 else None
        return None

    def _media_type_from_target(self, target_type: str | None) -> MediaType | None:
        if target_type == "tv":
            return MediaType.tv
        if target_type == "movie":
            return MediaType.movie
        return None

    def _rating(self, value: float | None, count: int | None) -> ProviderRating:
        return ProviderRating(value=value, count=count)

    def _is_source_vendor(self, title: str | None, url: str | None, vendor_id: str | None = None) -> bool:
        normalized_title = (title or "").strip().lower()
        normalized_url = (url or "").strip().lower()
        normalized_vendor_id = (vendor_id or "").strip().lower()
        if (
            "douban" in normalized_title
            or "豆瓣" in normalized_title
            or normalized_title == "imdb"
            or "tmdb" in normalized_title
            or "themoviedb" in normalized_title
            or normalized_vendor_id in {"douban", "imdb", "tmdb", "themoviedb"}
        ):
            return True

        # Some real playback vendors use Douban deep links as jump URLs, for
        # example Tencent's goToWXMiniProgram URL. Keep those when the vendor
        # identity itself is external.
        return (
            not normalized_title
            and not normalized_vendor_id
            and (
                "douban.com" in normalized_url
                or "imdb.com" in normalized_url
                or "themoviedb.org" in normalized_url
                or "tmdb.org" in normalized_url
            )
        )

    def _to_vendor(self, title: str | None, icon: str | None, url: str | None, vendor_id: str | None) -> Vendor | None:
        if not (title or icon or url):
            return None
        if self._is_source_vendor(title, url, vendor_id):
            return None
        return Vendor(name=title, logo=icon, url=url, id=str(vendor_id) if vendor_id is not None else None)

    def _to_person(self, person) -> PersonInfo | None:
        if not person or not person.name:
            return None
        avatar = Avatar(large=person.avatar.large, normal=person.avatar.normal) if person.avatar else None
        character = person.character or (person.roles[0] if len(person.roles) > 0 else None)
        return PersonInfo(
            name=person.name,
            id=person.id,
            avatar=avatar,
            character=character,
            roles=person.roles,
            latin_name=person.latin_name,
        )

    def _search_item_to_provider(self, item) -> ProviderSearchItem | None:
        target = item.target
        if not target or not target.id or not target.title:
            return None
        media_type = self._media_type_from_target(item.target_type)
        if media_type is None:
            return None
        return ProviderSearchItem(
            provider_id=target.id,
            title=target.title,
            year=self._parse_year(target.year),
            media_type=media_type,
            rating=self._rating(target.rating.value if target.rating else None, target.rating.count if target.rating else None),
            poster_path=target.cover_url,
            subtitle=target.card_subtitle,
        )

    def _collection_item_to_provider(self, item) -> ProviderSearchItem | None:
        subject = item.subject or item.target
        if subject is not None:
            if not subject.id or not subject.title:
                return None
            title = subject.title
            provider_id = subject.id
            year = self._parse_year(subject.year)
            rating = self._rating(subject.rating.value if subject.rating else None, subject.rating.count if subject.rating else None)
            poster_path = subject.cover_url
            subtitle = subject.card_subtitle
        else:
            if not item.id or not item.title:
                return None
            title = item.title
            provider_id = item.id
            year = self._parse_year(item.year)
            rating = self._rating(item.rating.value if item.rating else None, item.rating.count if item.rating else None)
            poster_path = item.cover_url or (item.pic.large if item.pic else None) or (item.cover.url if item.cover else None)
            subtitle = item.card_subtitle
        target_type = item.type if subject is None else item.type
        normalized_target_type: str | None
        if target_type in ("tv", "movie"):
            normalized_target_type = target_type
        elif (item.type or "").startswith("tv_") or (item.type or "").startswith("show_"):
            normalized_target_type = "tv"
        else:
            normalized_target_type = None
        media_type = self._media_type_from_target(normalized_target_type)
        if media_type is None:
            return None
        return ProviderSearchItem(
            provider_id=provider_id,
            title=title,
            year=year,
            media_type=media_type,
            rating=rating,
            poster_path=poster_path,
            subtitle=subtitle,
        )

    def _build_api_url(self, path: str) -> str:
        return f"{self.BASE_URL}{path}"

    def _search_result_items(self, raw: DoubanSearchResult) -> list:
        items = [*raw.smart_box, *raw.items]
        if raw.subjects:
            items.extend(raw.subjects.items)
        return items

    async def _get(
        self,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
        error_message: str,
    ):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"{error_message}: status={resp.status_code}, body={resp.text[:500]}")
            return resp.json()

    async def search_movie(
        self,
        q: str,
        start: int = 0,
        count: int = 10
    ) -> list[ProviderSearchItem]:
        """text
        
        Args:
            q: text
            start: text
            count: text
            
        Returns:
            text API text JSON text
            
        Raises:
            RuntimeError: text API text 200 text
            Exception: text
        """
        url = self._build_api_url("/search")
        ts = str(int(time.time()))
        
        params, headers = self._build_common_params(url, ts)
        params.update({
            "q": q,
            "start": str(start),
            "count": str(count),
            "type": "movie",
        })
        data = await self._get(url, params, headers, "Douban search API error")
        raw = DoubanSearchResult.model_validate(data)
        seen: set[tuple[str, str]] = set()
        results: list[ProviderSearchItem] = []
        for entry in self._search_result_items(raw):
            item = self._search_item_to_provider(entry)
            if not item:
                continue
            key = (item.media_type.value, item.provider_id)
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
        return results

    async def subject_collection_items(self, key: str, start: int = 0, count: int = 20) -> list[ProviderSearchItem]:
        if not self.supports_discover_key(key):
            raise ValueError(f"unsupported douban discover key: {key}")

        url = self._build_api_url(f"/subject_collection/{key}/items")
        ts = datetime.now().strftime('%Y%m%d')
        params, headers = self._build_common_params(url, ts)
        params.update({"start": str(start), "count": str(count)})
        data = await self._get(url, params, headers, f"Douban discover API error: key={key}")
        raw_response = DoubanRawCollectionItemsResponse.model_validate(data)
        items = raw_response.items if raw_response.items else raw_response.subject_collection_items
        return [item for item in (self._collection_item_to_provider(entry) for entry in items) if item]

    async def get_subject_detail(
        self,
        subject_id: str,
        subject_type: Literal['movie', 'tv'], 
    ) -> ProviderMediaDetail:
        """text
        
        Args:
            subject_id: text ID
            subject_type: text (movie text tv)
            
        Returns:
            text API text JSON text
            
        Raises:
            ValueError: text
            RuntimeError: text API text 200 text
        """
        if not subject_id:
            raise ValueError("subject_id required")
        if subject_type not in ("movie", "tv"):
            raise ValueError("subject_type must be movie|tv")
        
        url = self._build_api_url(f"/{subject_type}/{subject_id}")
        ts = datetime.now().strftime('%Y%m%d')
        
        params, headers = self._build_common_params(url, ts)
        data = await self._get(
            url,
            params,
            headers,
            f"Douban detail API error: id={subject_id}, type={subject_type}",
        )
        detail = DoubanDetail.model_validate(data)
        rating = self._rating(detail.rating.value if detail.rating else None, detail.rating.count if detail.rating else None)
        vendors = [
            vendor
            for vendor in (
                self._to_vendor(entry.title, entry.icon or entry.grey_icon, entry.url or entry.uri, entry.id)
                for entry in (detail.vendors or [])
            )
            if vendor
        ]
        return ProviderMediaDetail(
            provider_id=detail.id or subject_id,
            title=detail.title or "",
            original_title=detail.original_title,
            media_type=MediaType.tv if subject_type == "tv" else MediaType.movie,
            year=self._parse_year(detail.year),
            overview=detail.intro,
            genres=list(detail.genres),
            poster_path=detail.cover_url or (detail.pic.large if detail.pic else None),
            rating=rating,
            duration=detail.durations[0] if detail.durations else None,
            vendors=vendors,
            release_date=detail.pubdate[0] if detail.pubdate else None,
            original_language=detail.languages[0] if detail.languages else None,
            episodes_count=detail.episodes_count,
        )

    async def get_celebrities(
        self,
        subject_id: str,
        subject_type: Literal['movie', 'tv']
    ) -> ProviderCredits | None:
        """text
        
        Args:
            subject_id: text ID
            subject_type: text (movie text tv)
            
        Returns:
            text JSON text，text None
        """
        if not subject_id:
            raise ValueError("subject_id required")
        if subject_type not in ("movie", "tv"):
            raise ValueError("subject_type must be movie|tv")
        
        url = self._build_api_url(f"/{subject_type}/{subject_id}/celebrities")
        ts = datetime.now().strftime('%Y%m%d')
        
        params, headers = self._build_common_params(url, ts)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers, params=params)
                
                if resp.status_code == 200:
                    data = resp.json()
                    raw = DoubanCelebritiesResponse.model_validate(data)
                    return ProviderCredits(
                        actors=[person for person in (self._to_person(item) for item in raw.actors) if person],
                        directors=[person for person in (self._to_person(item) for item in raw.directors) if person],
                    )
                else:
                    # Internal note.
                    return None
        except (httpx.HTTPError, ValueError):
            # Internal note.
            return None

# module-level client instance for convenient reuse

try:
    douban_client = DoubanClient(settings_service.get_base_services_config().douban)
except (RuntimeError, ValueError):
    # Graceful fallback in environments where config isn't ready during import
    douban_client = None
