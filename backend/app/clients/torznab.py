from __future__ import annotations

import logging
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.integration.site_models import SiteSearchCapabilities
from app.schemas.integration.torznab import TorznabEnclosure, TorznabItem

logger = logging.getLogger("app.clients.torznab")


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024**3:
        return f"{size_bytes / (1024**2):.1f} MB"
    return f"{size_bytes / (1024**3):.1f} GB"


def truncate_text(value: str | None, limit: int = 300) -> str:
    if not value:
        return ""
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def build_torznab_search_params(
    *,
    api_key: str,
    query: str,
    search_param: str,
    category: str | None = None,
    search_type: str = "search",
    season_number: int | None = None,
) -> dict[str, str]:
    params: dict[str, str] = {"apikey": api_key, "t": search_type}
    if search_param == "doubanid":
        params["doubanid"] = query
    elif search_param == "imdbid" or (search_param == "auto" and re.match(r"^tt\d{7,8}$", query)):
        params["imdbid"] = query
    else:
        params["q"] = query

    category_map = {"movie": "2000", "tv": "5000", "anime": "5070"}
    if category in category_map:
        params["cat"] = category_map[category]
    if season_number is not None and season_number > 0:
        params["season"] = str(season_number)
    return params


def parse_torznab_xml(xml_text: str, *, default_site: str = "unknown") -> list[ResourceSearchResult]:
    results: list[ResourceSearchResult] = []
    if not xml_text:
        return results

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error("Failed to parse Torznab XML: %s", exc)
        return results

    ns = {"torznab": "http://torznab.com/schemas/2015/feed"}
    for item_el in root.findall(".//item"):
        try:
            attributes: dict[str, str] = {}
            attr_elements = list(item_el.findall("torznab:attr", ns)) + [
                element for element in item_el if element.tag.endswith("attr")
            ]
            for attr_el in attr_elements:
                name = attr_el.attrib.get("name") or attr_el.attrib.get("{http://www.w3.org/2005/Atom}name")
                value = attr_el.attrib.get("value")
                if name and value:
                    attributes[name.lower()] = value

            enclosure_el = item_el.find("enclosure")
            enclosure = None
            if enclosure_el is not None:
                enclosure = TorznabEnclosure(
                    url=enclosure_el.get("url") or "",
                    length=int(enclosure_el.get("length")) if enclosure_el.get("length") else None,
                    type=enclosure_el.get("type"),
                )

            item = TorznabItem(
                title=(item_el.findtext("title") or "").strip(),
                guid=(item_el.findtext("guid") or "").strip(),
                link=(item_el.findtext("link") or "").strip(),
                comments=(item_el.findtext("comments") or "").strip(),
                pubDate=item_el.findtext("pubDate"),
                description=(item_el.findtext("description") or "").strip(),
                jackettindexer=(item_el.findtext("jackettindexer") or "").strip().lower() or default_site,
                enclosure=enclosure,
                attributes=attributes,
            )

            try:
                publish_date = parsedate_to_datetime(item.pubDate) if item.pubDate else datetime.now(timezone.utc)
            except (TypeError, ValueError):
                publish_date = datetime.now(timezone.utc)

            site = item.jackettindexer or default_site
            torrent_url = ""
            download_url = ""
            if item.enclosure and item.enclosure.url.endswith(".torrent"):
                download_url = item.enclosure.url
            if item.link and item.link.startswith("magnet:"):
                torrent_url = item.link
            elif not download_url and item.enclosure:
                download_url = item.enclosure.url
            elif not download_url and item.link:
                download_url = item.link

            detail_url = item.comments or item.link or (item.enclosure.url if item.enclosure else "")
            indexer_guid = item.guid or str(hash(item.title + site))

            results.append(
                ResourceSearchResult(
                    id=indexer_guid,
                    title=item.title or "",
                    description=truncate_text(item.description),
                    site=site,
                    site_name=site,
                    category="other",
                    size=format_size(item.size),
                    seeders=item.seeders,
                    leechers=item.peers,
                    publish_date=publish_date,
                    torrent_url=torrent_url,
                    download_url=download_url,
                    detail_url=detail_url,
                    result_id=str(uuid.uuid4()),
                    download_volume_factor=item.download_volume_factor,
                    upload_volume_factor=item.upload_volume_factor,
                    source_imdbid=item.attributes.get("imdbid"),
                    source_doubanid=item.attributes.get("doubanid"),
                )
            )
        except (AttributeError, TypeError, ValueError) as exc:
            logger.error("Error parsing Torznab item: %s", exc)
            continue

    return results


def parse_torznab_caps_xml(xml_text: str) -> SiteSearchCapabilities:
    if not xml_text:
        return SiteSearchCapabilities()

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("Failed to parse Torznab caps XML: %s", exc)
        return SiteSearchCapabilities()

    params_by_search_type: dict[str, set[str]] = {}
    available_search_types: set[str] = set()
    declared_search_types: set[str] = set()
    searching = root.find(".//searching")
    if searching is not None:
        for child in list(searching):
            search_type = child.tag.rsplit("}", 1)[-1].lower()
            declared_search_types.add(search_type)
            available = str(child.attrib.get("available", "")).strip().lower()
            if available in {"no", "false", "0"}:
                continue
            available_search_types.add(search_type)
            search_type_params: set[str] = set()
            supported = child.attrib.get("supportedParams", "") or ""
            for param in supported.split(","):
                normalized = param.strip().lower()
                if normalized:
                    search_type_params.add(normalized)
            params_by_search_type[search_type] = search_type_params
    params = set().union(*params_by_search_type.values()) if params_by_search_type else set()

    category_ids: set[str] = set()
    for category in root.findall(".//categories//category"):
        raw_id = str(category.attrib.get("id", "")).strip()
        if raw_id:
            category_ids.add(raw_id)
    supports_movie = any(category_id.startswith("2") for category_id in category_ids)
    supports_tv = any(category_id.startswith("5") for category_id in category_ids)
    if not category_ids:
        supports_movie = True
        supports_tv = True

    return SiteSearchCapabilities(
        supports_search="search" in available_search_types if declared_search_types else True,
        supports_movie_search="movie-search" in available_search_types if declared_search_types else True,
        supports_tv_search="tv-search" in available_search_types if declared_search_types else True,
        search_params=params_by_search_type.get("search", set()),
        movie_search_params=params_by_search_type.get("movie-search", set()),
        tv_search_params=params_by_search_type.get("tv-search", set()),
        supports_doubanid="doubanid" in params,
        supports_imdbid="imdbid" in params,
        supports_q="q" in params if params else True,
        supports_movie=supports_movie,
        supports_tv=supports_tv,
    )
