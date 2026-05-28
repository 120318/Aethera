from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from types import TracebackType
from urllib.parse import urlencode, urlsplit, urlunsplit

import aiohttp

from app.clients.base import IndexerClient
from app.schemas.config import IndexerProviderConfig
from app.schemas.constants.indexer import SITE_SEARCH_TIMEOUT_SECONDS
from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.integration.site_models import SiteInfo, SiteSearchCapabilities
from app.schemas.runtime.indexer_site_health import IndexerSiteHealthStatus
from app.clients.torznab import build_torznab_search_params, parse_torznab_caps_xml, parse_torznab_xml

logger = logging.getLogger("app.clients.prowlarr")


class ProwlarrClient(IndexerClient):
    def __init__(self, config: IndexerProviderConfig | None = None) -> None:
        self.config = config
        raw_url = self.config.url if self.config else "http://prowlarr:9696"
        self.base_url = self._normalize_base_url(raw_url)
        self.api_key = (self.config.api_key if self.config else "").strip()
        self.session: aiohttp.ClientSession | None = None
        self.search_timeout = SITE_SEARCH_TIMEOUT_SECONDS

    def _normalize_base_url(self, raw_url: str) -> str:
        url = (raw_url or "").strip()
        if not url:
            return "http://prowlarr:9696"
        parts = urlsplit(url)
        path = parts.path or ""
        normalized = urlunsplit((parts.scheme, parts.netloc, path.rstrip("/"), "", ""))
        return normalized.rstrip("/") if normalized else "http://prowlarr:9696"

    def get_id(self) -> str:
        if self.config and self.config.id:
            return self.config.id
        return "prowlarr_default"

    def _ensure_session(self) -> None:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def __aenter__(self) -> ProwlarrClient:
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

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self.api_key} if self.api_key else {}

    def _is_torrent_indexer(self, item: dict) -> bool:
        protocol = str(item.get("protocol") or "").strip().lower()
        return protocol in {"", "torrent"}

    def _site_id(self, item: dict) -> str:
        value = item.get("id")
        return str(value).strip() if value is not None else ""

    def _to_site(self, item: dict) -> SiteInfo | None:
        if not self._is_torrent_indexer(item):
            return None
        if item.get("enable") is False:
            return None
        site_id = self._site_id(item)
        if not site_id:
            return None
        name = str(item.get("name") or item.get("definitionName") or site_id).strip()
        implementation = str(item.get("implementation") or item.get("indexerType") or "").strip()
        return SiteInfo(
            id=site_id,
            name=name,
            description=str(item.get("description") or implementation or name).strip(),
            language=str(item.get("language") or "").strip(),
            type=str(item.get("privacy") or item.get("protocol") or "torrent").strip(),
        )

    def _to_metadata_capabilities(self, item: dict | None) -> SiteSearchCapabilities:
        if item is None:
            return SiteSearchCapabilities()
        categories = item.get("categories") or item.get("capabilities", {}).get("categories") or []
        category_ids: set[str] = set()
        for category in categories:
            raw_id = category.get("id") if type(category) is dict else category
            category_id = str(raw_id).strip()
            if category_id:
                category_ids.add(category_id)
        supports_movie = any(category_id.startswith("2") for category_id in category_ids)
        supports_tv = any(category_id.startswith("5") for category_id in category_ids)
        if not category_ids:
            supports_movie = True
            supports_tv = True
        supports = item.get("supportsSearch")
        return SiteSearchCapabilities(
            supports_search=bool(supports) if supports is not None else True,
            supports_movie_search=bool(supports) if supports is not None else True,
            supports_tv_search=bool(supports) if supports is not None else True,
            supports_q=bool(supports) if supports is not None else True,
            supports_imdbid=False,
            supports_doubanid=False,
            supports_movie=supports_movie,
            supports_tv=supports_tv,
        )

    async def _get_json_dict(self, path: str) -> dict | None:
        self._ensure_session()
        url = f"{self.base_url}{path}"
        async with self.session.get(url, headers=self._headers(), timeout=10) as response:
            if response.status != 200:
                return None
            payload = await response.json()
            if type(payload) is dict:
                return payload
            return None

    async def _get_json_list(self, path: str) -> list[dict] | None:
        self._ensure_session()
        url = f"{self.base_url}{path}"
        async with self.session.get(url, headers=self._headers(), timeout=10) as response:
            if response.status != 200:
                return None
            payload = await response.json()
            if type(payload) is list:
                return [item for item in payload if type(item) is dict]
            return None

    async def test_connection(self) -> bool:
        try:
            payload = await self._get_json_dict("/api/v1/system/status")
            if payload is not None:
                return True
            return await self._get_json_list("/api/v1/indexer") is not None
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return False

    async def _list_indexer_payloads(self) -> list[dict]:
        started_at = time.perf_counter()
        try:
            payload = await self._get_json_list("/api/v1/indexer")
            if payload is None:
                return []
            logger.debug(
                "Prowlarr get_indexers completed: client=%s sites=%s duration_ms=%.1f",
                self.get_id(),
                len(payload),
                (time.perf_counter() - started_at) * 1000,
            )
            return payload
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            logger.warning(
                "Failed to get Prowlarr indexers: client=%s duration_ms=%.1f error=%s",
                self.get_id(),
                (time.perf_counter() - started_at) * 1000,
                exc,
            )
            return []

    async def get_indexers(self) -> list[SiteInfo]:
        payloads = await self._list_indexer_payloads()
        sites = [site for item in payloads if (site := self._to_site(item)) is not None]
        return sites

    async def get_indexer_caps(self, indexer: str) -> SiteSearchCapabilities:
        payloads = await self._list_indexer_payloads()
        item = next((payload for payload in payloads if self._site_id(payload) == str(indexer)), None)
        caps = await self._get_torznab_caps(indexer)
        if caps is not None:
            return caps
        return self._to_metadata_capabilities(item)

    async def _get_torznab_caps(self, indexer: str) -> SiteSearchCapabilities | None:
        self._ensure_session()
        url = f"{self.base_url}/{indexer}/api"
        params = {"apikey": self.api_key, "t": "caps"}
        started_at = time.perf_counter()
        try:
            async with self.session.get(url, params=params, headers=self._headers(), timeout=10) as response:
                if response.status != 200:
                    logger.debug(
                        "Prowlarr get_indexer_caps non-200: client=%s site=%s status=%s duration_ms=%.1f",
                        self.get_id(),
                        indexer,
                        response.status,
                        (time.perf_counter() - started_at) * 1000,
                    )
                    return None
                text = await response.text()
                capabilities = parse_torznab_caps_xml(text)
                logger.debug(
                    "Prowlarr get_indexer_caps completed: client=%s site=%s capabilities=%s duration_ms=%.1f",
                    self.get_id(),
                    indexer,
                    capabilities.model_dump(mode="json"),
                    (time.perf_counter() - started_at) * 1000,
                )
                return capabilities
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            logger.warning(
                "Failed to get Prowlarr caps: client=%s site=%s duration_ms=%.1f error=%s",
                self.get_id(),
                indexer,
                (time.perf_counter() - started_at) * 1000,
                exc,
            )
            return None

    async def get_site_health(self) -> list[IndexerSiteHealthStatus]:
        payloads = await self._list_indexer_payloads()
        site_names = {
            site.id: site.name
            for item in payloads
            if (site := self._to_site(item)) is not None
        }
        try:
            payload = await self._get_json_list("/api/v1/indexerstatus")
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            payload = None
        statuses_by_site: dict[str, IndexerSiteHealthStatus] = {}
        if payload is not None:
            for item in payload:
                if type(item) is not dict:
                    continue
                site_id = str(item.get("indexerId") or item.get("id") or "").strip()
                if not site_id or site_id not in site_names:
                    continue
                disabled_till = item.get("disabledTill")
                last_error = str(item.get("mostRecentFailure") or item.get("lastError") or "").strip() or None
                status = "unhealthy" if disabled_till or last_error else "healthy"
                statuses_by_site[site_id] = IndexerSiteHealthStatus(
                    indexer_id=self.config.id if self.config else "",
                    indexer_name=self.config.name if self.config else "",
                    site_id=site_id,
                    site_name=site_names[site_id],
                    status=status,
                    checked_at=datetime.now(),
                    last_error_message=last_error,
                    client_type="prowlarr",
                )
        return [
            statuses_by_site.get(
                site_id,
                IndexerSiteHealthStatus(
                    indexer_id=self.config.id if self.config else "",
                    indexer_name=self.config.name if self.config else "",
                    site_id=site_id,
                    site_name=site_name,
                    status="healthy" if payload is not None else "unknown",
                    checked_at=datetime.now() if payload is not None else None,
                    client_type="prowlarr",
                ),
            )
            for site_id, site_name in site_names.items()
        ]

    async def search_all_torznab(
        self,
        query: str,
        category: str | None = None,
        indexers: list[str] | None = None,
    ) -> list[ResourceSearchResult]:
        sites = indexers or [site.id for site in await self.get_indexers()]
        results: list[ResourceSearchResult] = []
        for site_id in sites:
            results.extend(await self.search_indexer_torznab(site_id, query, category=category))
        return results

    def build_torznab_feed(self, query: str, indexers: list[str] | None = None) -> str:
        if not indexers:
            return ""
        base = f"{self.base_url}/{indexers[0]}/api"
        params = {"apikey": self.api_key, "t": "search", "q": query}
        return f"{base}?{urlencode(params)}"

    async def search_indexer_torznab(
        self,
        indexer: str,
        query: str,
        category: str | None = None,
        search_param: str = "auto",
        season_number: int | None = None,
    ) -> list[ResourceSearchResult]:
        self._ensure_session()
        capabilities = await self.get_indexer_caps(indexer)
        params = self._build_torznab_search_params(query, category, search_param, season_number, capabilities)
        if params is None:
            logger.debug(
                "Prowlarr torznab single indexer skipped unsupported search mode: indexer=%s query=%s category=%s search_param=%s",
                indexer,
                query,
                category,
                search_param,
            )
            return []

        url = f"{self.base_url}/{indexer}/api"
        try:
            async with self.session.get(url, params=params, headers=self._headers(), timeout=self.search_timeout) as resp:
                if resp.status != 200:
                    body = (await resp.text()).strip()
                    detail = f" status={resp.status}"
                    if body:
                        detail += f" body={body[:200]}"
                    raise RuntimeError(f"prowlarr_http_error:{indexer}{detail}")
                text = await resp.text()
                return [
                    result.model_copy(update={"site": str(indexer), "site_name": str(indexer)})
                    for result in parse_torznab_xml(text, default_site=str(indexer))
                ]
        except asyncio.TimeoutError as exc:
            message = f"prowlarr_timeout:{indexer}"
            logger.warning("Prowlarr torznab single indexer timeout: indexer=%s query=%s search_param=%s", indexer, query, search_param)
            raise RuntimeError(message) from exc
        except aiohttp.ClientError as exc:
            message = f"prowlarr_client_error:{indexer}:{exc}"
            logger.warning(
                "Prowlarr torznab single indexer client error: indexer=%s query=%s search_param=%s error=%s",
                indexer,
                query,
                search_param,
                exc,
            )
            raise RuntimeError(message) from exc
        except ValueError as exc:
            message = f"prowlarr_parse_error:{indexer}:{exc}"
            logger.warning(
                "Prowlarr torznab single indexer parse error: indexer=%s query=%s search_param=%s error=%s",
                indexer,
                query,
                search_param,
                exc,
            )
            raise RuntimeError(message) from exc

    def _torznab_search_type(
        self,
        category: str | None,
        search_param: str,
        capabilities: SiteSearchCapabilities,
    ) -> str | None:
        if category == "tv":
            if capabilities.supports_tv_search:
                return "tvsearch"
            if search_param == "q" and capabilities.supports_search:
                return "search"
            return None
        if category == "movie":
            if capabilities.supports_movie_search:
                return "movie"
            if search_param == "q" and capabilities.supports_search:
                return "search"
            return None
        if capabilities.supports_search:
            return "search"
        return None

    def _build_torznab_search_params(
        self,
        query: str,
        category: str | None,
        search_param: str,
        season_number: int | None,
        capabilities: SiteSearchCapabilities | None = None,
    ) -> dict[str, str] | None:
        resolved_capabilities = capabilities or SiteSearchCapabilities()
        search_type = self._torznab_search_type(category, search_param, resolved_capabilities)
        if search_type is None:
            return None
        return build_torznab_search_params(
            api_key=self.api_key,
            query=query,
            search_param=search_param,
            category=category,
            search_type=search_type,
            season_number=season_number if search_type == "tvsearch" else None,
        )
