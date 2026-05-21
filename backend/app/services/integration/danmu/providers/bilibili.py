from __future__ import annotations

import re
from collections.abc import Mapping

import httpx

from app.schemas.domain.vendor import Vendor
from app.schemas.domain.media_types import MediaType
from app.services.integration.danmu.base import BaseDanmuProvider
from app.services.integration.danmu.models import DanmuFetchInput, DanmuFetchResult
from app.services.integration.danmu.utils import parse_bilibili_xml, vendor_text


class BilibiliDanmuProvider(BaseDanmuProvider):
    provider_id = "bilibili"

    def supports(self, vendor: Vendor) -> bool:
        text = " ".join([vendor_text(vendor.id), vendor_text(vendor.name), vendor_text(vendor.url)])
        return "bilibili" in text or "哔哩哔哩" in text or "b站" in text

    def can_fetch(self, vendor: Vendor) -> bool:
        return self.supports(vendor) and self._extract_ep_id(vendor.url or "") is not None

    async def fetch(self, vendor: Vendor, request: DanmuFetchInput) -> DanmuFetchResult | None:
        ep_id = self._extract_ep_id(vendor.url or "")
        if not ep_id:
            return None
        async with httpx.AsyncClient(timeout=15.0) as client:
            episodes_response = await client.get("https://api.bilibili.com/pgc/view/web/ep/list", params={"ep_id": ep_id})
            episodes_response.raise_for_status()
            data_mapping: dict = episodes_response.json()
            result_mapping: dict = data_mapping.get("result", {})
            episodes = result_mapping.get("episodes") or []
            if request.episode_count and request.episode_number and len(episodes) != int(request.episode_count):
                return None
            candidate_mapping: dict | None = self._select_episode(episodes, ep_id, request)
            if not candidate_mapping:
                return None
            cid = str(candidate_mapping.get("cid") or "")
            if not cid:
                return None
            danmu_response = await client.get("https://api.bilibili.com/x/v1/dm/list.so", params={"oid": cid})
            danmu_response.raise_for_status()
            comments = parse_bilibili_xml(danmu_response.content)
            return DanmuFetchResult(
                provider=self.provider_id,
                comments=comments,
                source_id=cid,
                source_duration_seconds=self._candidate_duration_seconds(candidate_mapping) or self._comments_duration_seconds(comments),
            )

    def _select_episode(self, episodes: list, ep_id: str, request: DanmuFetchInput) -> dict | None:
        if request.episode_number:
            index = int(request.episode_number) - 1
            if index < 0 or index >= len(episodes):
                return None
            episode_mapping: dict = episodes[index]
            return episode_mapping
        if request.media_type != MediaType.movie:
            return None
        for item in episodes:
            item_mapping: dict = item
            if str(item_mapping.get("id") or item_mapping.get("ep_id") or "") == ep_id:
                return item_mapping
        if len(episodes) == 1:
            episode_mapping: dict = episodes[0]
            return episode_mapping
        return None

    def _extract_ep_id(self, url: str) -> str | None:
        match = re.search(r"/ep(\d+)", url)
        return match.group(1) if match else None

    def _candidate_duration_seconds(self, candidate_mapping: Mapping[str, str]) -> float | None:
        value = candidate_mapping.get("duration")
        try:
            duration = float(value or 0)
        except (TypeError, ValueError):
            return None
        if duration <= 0:
            return None
        return duration / 1000 if duration > 86400 else duration

    def _comments_duration_seconds(self, comments) -> float | None:
        return max((float(comment.time_seconds) for comment in comments), default=0.0) or None
