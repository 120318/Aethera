from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from app.schemas.domain.schedule import SchedulePlatform
from app.schemas.domain.vendor import Vendor
from app.schemas.integration.media.provider import ProviderPlatformInfo, ProviderWatchProviders


class SchedulePlatformService:
    preferred_regions: list[str] = ["CN", "US"]
    online_provider_buckets: list[str] = ["flatrate", "free", "ads", "buy", "rent"]
    platform_aliases: dict[str, str] = {
        "qq": "tencent",
        "tencent": "tencent",
        "腾讯视频": "tencent",
        "腾讯视频平台": "tencent",
        "tencent video": "tencent",
        "tencent video platform": "tencent",
        "txvideo": "tencent",
        "iqiyi": "iqiyi",
        "爱奇艺": "iqiyi",
        "youku": "youku",
        "优酷": "youku",
        "优酷视频": "youku",
        "bilibili": "bilibili",
        "哔哩哔哩": "bilibili",
        "mgtv": "mgtv",
        "mango tv": "mgtv",
        "芒果tv": "mgtv",
        "芒果TV": "mgtv",
        "9": "amazon_prime_video",
        "119": "amazon_prime_video",
        "amazon prime video": "amazon_prime_video",
        "amazon prime video with ads": "amazon_prime_video",
        "amazon prime video free with ads": "amazon_prime_video",
        "prime video": "amazon_prime_video",
    }
    platform_overrides: dict[str, SchedulePlatform] = {
        "iqiyi": SchedulePlatform(name="爱奇艺", url="https://www.iqiyi.com/"),
        "iqiyi international": SchedulePlatform(name="爱奇艺国际版", url="https://www.iq.com/"),
        "tencent video": SchedulePlatform(name="腾讯视频", url="https://v.qq.com/"),
        "wetv": SchedulePlatform(name="WeTV", url="https://wetv.vip/"),
        "youku": SchedulePlatform(name="优酷", url="https://www.youku.com/"),
        "mango tv": SchedulePlatform(name="芒果TV", url="https://www.mgtv.com/"),
        "bilibili": SchedulePlatform(name="哔哩哔哩", url="https://www.bilibili.com/"),
        "netflix": SchedulePlatform(name="Netflix", url="https://www.netflix.com/"),
        "disney plus": SchedulePlatform(name="Disney+", url="https://www.disneyplus.com/"),
        "disney+": SchedulePlatform(name="Disney+", url="https://www.disneyplus.com/"),
        "hbo": SchedulePlatform(name="HBO", url="https://www.hbo.com/"),
        "max": SchedulePlatform(name="Max", url="https://www.max.com/"),
        "hulu": SchedulePlatform(name="Hulu", url="https://www.hulu.com/"),
        "apple tv+": SchedulePlatform(name="Apple TV+", url="https://tv.apple.com/"),
        "apple tv store": SchedulePlatform(name="Apple TV", url="https://tv.apple.com/"),
        "amazon prime video": SchedulePlatform(name="Prime Video", url="https://www.primevideo.com/"),
        "amazon prime video with ads": SchedulePlatform(name="Prime Video", url="https://www.primevideo.com/"),
        "amazon prime video free with ads": SchedulePlatform(name="Prime Video", url="https://www.primevideo.com/"),
        "prime video": SchedulePlatform(name="Prime Video", url="https://www.primevideo.com/"),
        "google play movies": SchedulePlatform(name="Google Play Movies", url="https://play.google.com/store/movies"),
        "youtube": SchedulePlatform(name="YouTube", url="https://www.youtube.com/"),
        "tving": SchedulePlatform(name="TVING", url="https://www.tving.com/"),
        "wavve": SchedulePlatform(name="Wavve", url="https://www.wavve.com/"),
        "u-next": SchedulePlatform(name="U-NEXT", url="https://video.unext.jp/"),
        "paramount plus": SchedulePlatform(name="Paramount+", url="https://www.paramountplus.com/"),
        "paramount+": SchedulePlatform(name="Paramount+", url="https://www.paramountplus.com/"),
        "peacock": SchedulePlatform(name="Peacock", url="https://www.peacocktv.com/"),
    }

    def platform_logo(self, logo_path: str | None) -> str | None:
        if not logo_path:
            return None
        return f"https://image.tmdb.org/t/p/original{logo_path}"

    def normalize(self, platform: SchedulePlatform) -> SchedulePlatform:
        key = str(platform.name or "").strip().lower()
        if key not in self.platform_overrides:
            return platform
        override = self.platform_overrides[key]
        normalized_url = platform.url
        if self.is_tmdb_watch_url(normalized_url):
            normalized_url = None
        return SchedulePlatform(
            id=platform.id,
            name=override.name or platform.name,
            logo=platform.logo,
            url=normalized_url or override.url,
            region=platform.region,
        )

    def canonical_key(self, *values: str | None) -> str | None:
        for value in values:
            normalized = str(value or "").strip()
            if not normalized:
                continue
            if normalized in self.platform_aliases:
                return self.platform_aliases[normalized]
            normalized_lower = normalized.lower()
            if normalized_lower in self.platform_aliases:
                return self.platform_aliases[normalized_lower]
            normalized_compact = "".join(normalized_lower.split())
            if normalized_compact in self.platform_aliases:
                return self.platform_aliases[normalized_compact]
        return None

    def provider_bucket(self, payload: ProviderWatchProviders, bucket: str) -> list[ProviderPlatformInfo]:
        if bucket == "flatrate":
            return payload.flatrate
        if bucket == "free":
            return payload.free
        if bucket == "ads":
            return payload.ads
        if bucket == "buy":
            return payload.buy
        if bucket == "rent":
            return payload.rent
        return []

    def network_platform(self, payload: ProviderPlatformInfo) -> SchedulePlatform | None:
        if not payload.name:
            return None
        return self.normalize(SchedulePlatform(id=payload.id, name=payload.name, logo=payload.logo))

    def provider_platform(self, payload: ProviderPlatformInfo, region: str, url: str | None) -> SchedulePlatform | None:
        if not payload.name:
            return None
        return self.normalize(
            SchedulePlatform(
                id=payload.id,
                name=payload.name,
                logo=payload.logo,
                url=payload.url or url,
                region=payload.region or region,
            )
        )

    def dedupe(self, platforms: list[SchedulePlatform]) -> list[SchedulePlatform]:
        seen: set[str] = set()
        deduped: list[SchedulePlatform] = []
        for raw_platform in platforms:
            platform = self.normalize(raw_platform)
            key = self.canonical_key(platform.id, platform.name) or str(platform.id or platform.name or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(platform)
        return deduped

    def merge(
        self,
        primary_platforms: list[SchedulePlatform],
        secondary_platforms: list[SchedulePlatform],
    ) -> list[SchedulePlatform]:
        return self.dedupe([*primary_platforms, *secondary_platforms])

    def exclude_matching(
        self,
        platforms: list[SchedulePlatform],
        excluded_platforms: list[SchedulePlatform],
    ) -> list[SchedulePlatform]:
        excluded_keys = {
            key
            for platform in excluded_platforms
            if (key := self.canonical_key(platform.id, platform.name))
        }
        if not excluded_keys:
            return platforms
        return [
            platform
            for platform in platforms
            if self.canonical_key(platform.id, platform.name) not in excluded_keys
        ]

    def apply_vendor_links(self, platforms: list[SchedulePlatform], vendors: list[Vendor]) -> list[SchedulePlatform]:
        vendor_urls = self._vendor_playback_urls_by_platform(vendors)
        if not vendor_urls:
            return platforms
        enriched: list[SchedulePlatform] = []
        for platform in platforms:
            key = self.canonical_key(platform.id, platform.name)
            url = vendor_urls[key] if key and key in vendor_urls else None
            enriched.append(platform.model_copy(update={"url": url}) if url else platform)
        return enriched

    def is_tmdb_watch_url(self, url: str | None) -> bool:
        if not url:
            return False
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        host = (parsed.netloc or "").lower()
        path = parsed.path or ""
        return "themoviedb.org" in host and path.endswith("/watch")

    def _is_web_url(self, url: str | None) -> bool:
        if not url:
            return False
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _first_query_value(self, values: dict[str, list[str]], key: str) -> str | None:
        items = values[key] if key in values else []
        for item in items:
            value = str(item or "").strip()
            if value:
                return value
        return None

    def _parse_tencent_play_url(self, url: str) -> str | None:
        try:
            parsed = urlparse(url)
        except ValueError:
            return None
        query = parse_qs(parsed.query)
        cid = self._first_query_value(query, "cid")
        vid = self._first_query_value(query, "vid")
        path = self._first_query_value(query, "path")
        if path:
            nested = urlparse(path)
            nested_query = parse_qs(nested.query)
            cid = cid or self._first_query_value(nested_query, "cid")
            vid = vid or self._first_query_value(nested_query, "vid")
        if not cid or not vid:
            return None
        return f"https://v.qq.com/x/cover/{cid}/{vid}.html"

    def _parse_nested_query(self, url: str) -> dict[str, list[str]]:
        try:
            parsed = urlparse(url)
        except ValueError:
            return {}
        query = parse_qs(parsed.query)
        path = self._first_query_value(query, "path")
        if not path:
            return query
        nested = urlparse(path)
        nested_query = parse_qs(nested.query)
        return {**query, **nested_query}

    def _parse_youku_play_url(self, url: str) -> str | None:
        query = self._parse_nested_query(url)
        show_id = self._first_query_value(query, "showId")
        if show_id:
            return f"https://v.youku.com/v_nextstage/id_{show_id}.html"
        video_id = self._first_query_value(query, "video_id") or self._first_query_value(query, "vid")
        if video_id:
            return f"https://v.youku.com/v_show/id_{video_id}.html"
        return None

    def _vendor_playback_url(self, vendor: Vendor) -> str | None:
        url = str(vendor.url or "").strip()
        if self._is_web_url(url):
            return url
        key = self.canonical_key(vendor.id, vendor.name)
        if key == "tencent":
            return self._parse_tencent_play_url(url)
        if key == "youku":
            return self._parse_youku_play_url(url)
        return None

    def _vendor_playback_urls_by_platform(self, vendors: list[Vendor]) -> dict[str, str]:
        urls: dict[str, str] = {}
        for vendor in vendors:
            key = self.canonical_key(vendor.id, vendor.name)
            if not key or key in urls:
                continue
            playback_url = self._vendor_playback_url(vendor)
            if playback_url:
                urls[key] = playback_url
        return urls
