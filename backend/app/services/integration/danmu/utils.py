from __future__ import annotations

import json
import re
import zlib
from urllib.parse import parse_qs, unquote, urlparse
from xml.etree import ElementTree

from app.services.integration.danmu.models import DanmuComment


def vendor_text(value: str | None) -> str:
    return (value or "").strip().lower()


def parse_query_from_deeplink(url: str) -> dict[str, list[str]]:
    parsed = urlparse(url or "")
    query_mapping: dict[str, list[str]] = parse_qs(parsed.query)
    path_values = query_mapping.get("path") or []
    if path_values:
        path = unquote(path_values[0])
        if "?" in path:
            nested_query = parse_qs(path.split("?", 1)[1])
            query_mapping.update(nested_query)
    return query_mapping


def first_query_value(query: dict[str, list[str]], key: str) -> str | None:
    query_mapping: dict[str, list[str]] = query
    values = query_mapping.get(key) or []
    return values[0] if values else None


def parse_bilibili_xml(payload: bytes) -> list[DanmuComment]:
    root = ElementTree.fromstring(payload)
    comments: list[DanmuComment] = []
    for node in root.findall(".//d"):
        text = (node.text or "").strip()
        if not text:
            continue
        attrs_mapping: dict[str, str] = node.attrib
        attrs = (attrs_mapping.get("p") or "").split(",")
        try:
            time_seconds = float(attrs[0])
        except (IndexError, TypeError, ValueError):
            time_seconds = 0.0
        comments.append(DanmuComment(time_seconds=time_seconds, text=text))
    return comments


def parse_iqiyi_xml(payload: bytes) -> list[DanmuComment]:
    try:
        xml_payload = zlib.decompress(payload)
    except zlib.error:
        xml_payload = payload
    root = ElementTree.fromstring(xml_payload)
    comments: list[DanmuComment] = []
    for node in root.findall(".//bulletInfo"):
        text = (node.findtext("content") or "").strip()
        if not text:
            continue
        try:
            time_seconds = float(node.findtext("showTime") or 0)
        except (TypeError, ValueError):
            time_seconds = 0.0
        comments.append(DanmuComment(time_seconds=time_seconds, text=text))
    return comments


def parse_qq_json(payload: bytes, *, offset_seconds: float = 0.0) -> list[DanmuComment]:
    data_mapping: dict = json.loads(payload.decode("utf-8"))
    comments: list[DanmuComment] = []
    for item in data_mapping.get("barrage_list") or []:
        if type(item) is not dict:
            continue
        item_mapping: dict = item
        text = str(item_mapping.get("content") or "").strip()
        if not text:
            continue
        try:
            time_seconds = float(item_mapping.get("time_offset") or 0) / 1000 + offset_seconds
        except (TypeError, ValueError):
            time_seconds = 0.0
        comments.append(DanmuComment(time_seconds=time_seconds, text=text))
    return comments


def extract_youku_video_id(url: str) -> str | None:
    match = re.search(r"/v_show/id_([^./?#]+)", url or "")
    return match.group(1) if match else None


def extract_youku_show_id(url: str) -> str | None:
    match = re.search(r"/v_nextstage/id_([^./?#]+)", url or "")
    if match:
        return match.group(1)
    query = parse_query_from_deeplink(url)
    return first_query_value(query, "showId") or first_query_value(query, "show_id")
