"""
Jackett APItext
textPTtext
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from types import TracebackType
from urllib.parse import urlencode, urlsplit, urlunsplit

import aiohttp
from app.clients.base import IndexerClient
from app.schemas.config import IndexerProviderConfig
from app.schemas.constants.indexer import SITE_SEARCH_TIMEOUT_SECONDS
from app.schemas.domain.resource_search import JackettSearchResponse, JackettSearchResult, ResourceSearchResult
from app.schemas.integration.site_models import SiteInfo, SiteSearchCapabilities
from app.clients.torznab import format_size, parse_torznab_caps_xml, parse_torznab_xml, truncate_text

logger = logging.getLogger("app.clients.jackett")


class JackettClient(IndexerClient):
    def __init__(self, config: IndexerProviderConfig | None = None) -> None:
        self.config = config
        raw_url = self.config.url if self.config else "http://jackett:9117"
        self.base_url = self._normalize_base_url(raw_url)
        self.api_key = (self.config.api_key if self.config else "").strip()
        self.session: aiohttp.ClientSession | None = None
        self.search_timeout = SITE_SEARCH_TIMEOUT_SECONDS

    def _normalize_base_url(self, raw_url: str) -> str:
        url = (raw_url or "").strip()
        if not url:
            return "http://jackett:9117"
        parts = urlsplit(url)
        path = parts.path or ""
        idx = path.lower().find("/ui")
        if idx >= 0:
            path = path[:idx]
        normalized = urlunsplit((parts.scheme, parts.netloc, path.rstrip("/"), "", ""))
        return normalized.rstrip("/") if normalized else "http://jackett:9117"
    
    def get_id(self) -> str:
        """Internal helper."""
        if self.config and self.config.id:
            return self.config.id
        return "jackett_default"

    def _ensure_session(self) -> None:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def __aenter__(self) -> JackettClient:
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self.session:
            await self.session.close()
    
    def _parse_results(self, results: list[JackettSearchResult]) -> list[ResourceSearchResult]:
        """
        textJackett APItext
        """
        parsed_results: list[ResourceSearchResult] = []
        
        for result in results:
            try:
                # Internal note.
                size_bytes = result.Size
                size_str = format_size(size_bytes)
                
                # Internal note.
                tracker = result.Tracker or "unknown"
                
                # Internal note.
                category = self._parse_category(result.CategoryDesc or "")
                
                # Internal note.
                link_url = result.Link or ""
                magnet_uri = result.MagnetUri or ""
                torrent_url = magnet_uri if magnet_uri.startswith('magnet:') else ""
                download_url = link_url
                
                # Internal note.
                detail_url = result.Details or result.Link or ""
                
                # Internal note.
                indexer_guid = result.Guid or str(hash(result.Title + tracker))
                
                parsed_result = ResourceSearchResult(
                    id=indexer_guid,
                    title=result.Title or "",
                    description=truncate_text(result.Description),
                    site=tracker.lower(),
                    category=category,
                    size=str(size_str),
                    seeders=result.Seeders,
                    leechers=result.Peers,
                    publish_date=result.PublishDate,
                    torrent_url=torrent_url,
                    download_url=download_url,
                    detail_url=detail_url,
                    result_id=indexer_guid,
                    download_volume_factor=result.DownloadVolumeFactor,
                    upload_volume_factor=result.UploadVolumeFactor,
                )
                parsed_results.append(parsed_result)
            except (AttributeError, TypeError, ValueError) as exc:
                logger.error("Failed to parse model result: %s", exc)
                continue
        
        return parsed_results

    def _parse_torznab_xml(self, xml_text: str) -> list[ResourceSearchResult]:
        """
        text Jackett Torznab (RSS/XML) text，text TorznabItem text.
        """
        return parse_torznab_xml(xml_text)

    def _parse_indexers_xml(self, xml_text: str) -> list[SiteInfo]:
        sites: list[SiteInfo] = []
        if not xml_text:
            return sites

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("Failed to parse Jackett indexers XML: %s", exc)
            return sites

        elements = root.findall("indexer") if root.tag == "indexers" else root.findall(".//indexer")

        for element in elements:
            configured = str(element.attrib.get("configured", "")).strip().lower()
            if configured not in {"true", "1", "yes"}:
                continue

            site_id = (element.attrib.get("id") or "").strip()
            if not site_id:
                continue

            sites.append(
                SiteInfo(
                    id=site_id,
                    name=(element.findtext("title") or site_id).strip(),
                    description=(element.findtext("description") or "").strip(),
                    language=(element.findtext("language") or "").strip(),
                    type=(element.findtext("type") or "").strip(),
                )
            )

        return sites

    def _parse_caps_xml(self, xml_text: str) -> SiteSearchCapabilities:
        return parse_torznab_caps_xml(xml_text)

    def _parse_category(self, category_desc: str) -> str:
        if not category_desc:
            return 'other'
        cat = category_desc.lower()
        if 'movie' in cat or '电影' in cat:
            return 'movie'
        if 'tv' in cat or '电视剧' in cat or '剧集' in cat or 'series' in cat:
            return 'tv'
        if 'anime' in cat or '动画' in cat or '动漫' in cat:
            return 'anime'
        if 'documentary' in cat or '纪录' in cat:
            return 'documentary'
        if 'music' in cat or '音乐' in cat or 'audio' in cat:
            return 'music'
        if 'software' in cat or '软件' in cat or 'app' in cat:
            return 'software'
        if 'game' in cat or '游戏' in cat:
            return 'game'
        return 'other'
    
    async def test_connection(self) -> bool:
        self._ensure_session()
        try:
            url = f"{self.base_url}/api/v2.0/indexers/all/results/torznab/api"
            params = {"t": "indexers", "apikey": self.api_key}
            headers = {"X-Api-Key": self.api_key} if self.api_key else {}
            async with self.session.get(url, params=params, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    return False
                xml_text = await resp.text()
                return xml_text.lstrip().startswith("<?xml") or "<indexers" in xml_text
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    async def get_indexers(self) -> list[SiteInfo]:
        self._ensure_session()
        url = f"{self.base_url}/api/v2.0/indexers/all/results/torznab/api"
        params = {"t": "indexers", "apikey": self.api_key}
        headers = {"X-Api-Key": self.api_key} if self.api_key else {}
        started_at = time.perf_counter()
        try:
            async with self.session.get(url, params=params, headers=headers, timeout=10) as response:
                if response.status == 200:
                    text = await response.text()
                    if "<!DOCTYPE html" in text or "<html" in text.lower():
                        logger.debug(
                            "Jackett get_indexers returned html: client=%s status=%s duration_ms=%.1f",
                            self.get_id(),
                            response.status,
                            (time.perf_counter() - started_at) * 1000,
                        )
                        return []
                    sites = self._parse_indexers_xml(text)
                    logger.debug(
                        "Jackett get_indexers completed: client=%s status=%s sites=%s duration_ms=%.1f",
                        self.get_id(),
                        response.status,
                        len(sites),
                        (time.perf_counter() - started_at) * 1000,
                    )
                    return sites
                logger.debug(
                    "Jackett get_indexers non-200: client=%s status=%s duration_ms=%.1f",
                    self.get_id(),
                    response.status,
                    (time.perf_counter() - started_at) * 1000,
                )
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            logger.warning(
                "Failed to get indexers: client=%s duration_ms=%.1f error=%s",
                self.get_id(),
                (time.perf_counter() - started_at) * 1000,
                exc,
            )
        return []

    async def get_indexer_caps(self, indexer: str) -> SiteSearchCapabilities:
        self._ensure_session()
        url = f"{self.base_url}/api/v2.0/indexers/{indexer}/results/torznab/api"
        params = {"t": "caps", "apikey": self.api_key}
        headers = {"X-Api-Key": self.api_key} if self.api_key else {}
        started_at = time.perf_counter()
        try:
            async with self.session.get(url, params=params, headers=headers, timeout=10) as response:
                if response.status != 200:
                    logger.debug(
                        "Jackett get_indexer_caps non-200: client=%s site=%s status=%s duration_ms=%.1f",
                        self.get_id(),
                        indexer,
                        response.status,
                        (time.perf_counter() - started_at) * 1000,
                    )
                    return SiteSearchCapabilities()
                text = await response.text()
                if "<!DOCTYPE html" in text or "<html" in text.lower():
                    logger.debug(
                        "Jackett get_indexer_caps returned html: client=%s site=%s duration_ms=%.1f",
                        self.get_id(),
                        indexer,
                        (time.perf_counter() - started_at) * 1000,
                    )
                    return SiteSearchCapabilities()
                capabilities = self._parse_caps_xml(text)
                logger.debug(
                    "Jackett get_indexer_caps completed: client=%s site=%s capabilities=%s duration_ms=%.1f",
                    self.get_id(),
                    indexer,
                    capabilities.model_dump(mode="json"),
                    (time.perf_counter() - started_at) * 1000,
                )
                return capabilities
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            logger.warning(
                "Failed to get caps for indexer: client=%s site=%s duration_ms=%.1f error=%s",
                self.get_id(),
                indexer,
                (time.perf_counter() - started_at) * 1000,
                exc,
            )
            return SiteSearchCapabilities()

    async def search_all(self, query: str, category: str | None = None, indexers: list[str] | None = None) -> list[JackettSearchResult]:
        self._ensure_session()
        params: dict[str, str] = {"apikey": self.api_key, "Query": query}
        if category:
            category_map = {"movie": "2000", "tv": "5000", "anime": "5070"}
            if category in category_map:
                params["cat"] = category_map[category]
        if indexers:
            params["tracker"] = ",".join(indexers)

        url = f"{self.base_url}/api/v2.0/indexers/all/results"
        try:
            async with self.session.get(url, params=params, timeout=self.search_timeout) as resp:
                if resp.status != 200: return []
                data_json = await resp.json()
                data = JackettSearchResponse.model_validate(data_json)
                return data.Results
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            logger.error("Jackett search_all error: %s", exc)
            return []

    async def search_all_torznab(self, query: str, category: str | None = None, indexers: list[str] | None = None) -> list[ResourceSearchResult]:
        self._ensure_session()
        params: dict[str, str] = {"apikey": self.api_key, "t": "search"}
        if re.match(r"^tt\d{7,8}$", query):
            params["imdbid"] = query
        else:
            params["q"] = query
        
        if category:
            category_map = {"movie": "2000", "tv": "5000", "anime": "5070"}
            if category in category_map:
                params["cat"] = category_map[category]
        if indexers:
            params["tracker"] = ",".join(indexers)

        url = f"{self.base_url}/api/v2.0/indexers/all/results/torznab"
        try:
            async with self.session.get(url, params=params, timeout=self.search_timeout) as resp:
                if resp.status != 200: return []
                text = await resp.text()
                return self._parse_torznab_xml(text)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            logger.error("Jackett torznab search_all error: %s", exc)
            return []

    def build_torznab_feed(self, query: str, indexers: list[str] | None = None) -> str:
        base = f"{self.base_url}/api/v2.0/indexers/all/results/torznab"
        params = {"apikey": self.api_key, "t": "search", "q": query}
        if indexers:
            params["tracker"] = ",".join(indexers)
        return f"{base}?{urlencode(params)}"

    async def search_indexer_torznab(
        self,
        indexer: str,
        query: str,
        category: str | None = None,
        search_param: str = "auto",
    ) -> list[ResourceSearchResult]:
        self._ensure_session()
        params: dict[str, str] = {"apikey": self.api_key, "t": "search"}
        if search_param == "doubanid":
            params["doubanid"] = query
        elif search_param == "imdbid" or (search_param == "auto" and re.match(r"^tt\d{7,8}$", query)):
            params["imdbid"] = query
        else:
            params["q"] = query

        if category:
            category_map = {"movie": "2000", "tv": "5000", "anime": "5070"}
            if category in category_map:
                params["cat"] = category_map[category]

        url = f"{self.base_url}/api/v2.0/indexers/{indexer}/results/torznab"
        try:
            async with self.session.get(url, params=params, timeout=self.search_timeout) as resp:
                if resp.status != 200:
                    body = (await resp.text()).strip()
                    body_preview = body[:200] if body else ""
                    detail = f" status={resp.status}"
                    if body_preview:
                        detail += f" body={body_preview}"
                    raise RuntimeError(f"jackett_http_error:{indexer}{detail}")
                text = await resp.text()
                return self._parse_torznab_xml(text)
        except asyncio.TimeoutError as exc:
            message = f"jackett_timeout:{indexer}"
            logger.warning("Jackett torznab single indexer timeout: indexer=%s query=%s search_param=%s", indexer, query, search_param)
            raise RuntimeError(message) from exc
        except aiohttp.ClientError as exc:
            message = f"jackett_client_error:{indexer}:{exc}"
            logger.warning(
                "Jackett torznab single indexer client error: indexer=%s query=%s search_param=%s error=%s",
                indexer,
                query,
                search_param,
                exc,
            )
            raise RuntimeError(message) from exc
        except ValueError as exc:
            message = f"jackett_parse_error:{indexer}:{exc}"
            logger.warning(
                "Jackett torznab single indexer parse error: indexer=%s query=%s search_param=%s error=%s",
                indexer,
                query,
                search_param,
                exc,
            )
            raise RuntimeError(message) from exc

    async def search_indexer(self, indexer: str, query: str, category: str | None = None) -> list[JackettSearchResult]:
        self._ensure_session()
        params: dict[str, str] = {"apikey": self.api_key, "Query": query}
        if category:
            category_map = {"movie": "2000", "tv": "5000"}
            if category in category_map:
                params["cat"] = category_map[category]
        url = f"{self.base_url}/api/v2.0/indexers/{indexer}/results"
        try:
            async with self.session.get(url, params=params, timeout=self.search_timeout) as resp:
                if resp.status != 200: return []
                data_json = await resp.json()
                data = JackettSearchResponse.model_validate(data_json)
                return data.Results
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            logger.error("Jackett search_indexer error: %s", exc)
            return []

# Internal note.
jackett_client = JackettClient()
