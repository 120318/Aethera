from __future__ import annotations

import re
from collections.abc import Mapping

import httpx

from app.schemas.domain.vendor import Vendor
from app.schemas.domain.media_types import MediaType
from app.services.integration.danmu.base import BaseDanmuProvider
from app.services.integration.danmu.episode_matching import danmu_episode_matcher
from app.services.integration.danmu.models import DanmuEpisodeCandidate, DanmuFetchInput, DanmuFetchResult
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
            candidate = self._select_episode(episodes, ep_id, request)
            if not candidate:
                return None
            cid = candidate.external_id
            if not cid:
                return None
            danmu_response = await client.get("https://api.bilibili.com/x/v1/dm/list.so", params={"oid": cid})
            danmu_response.raise_for_status()
            comments = parse_bilibili_xml(danmu_response.content)
            return DanmuFetchResult(
                provider=self.provider_id,
                comments=comments,
                source_id=cid,
                source_duration_seconds=candidate.duration_seconds or self._comments_duration_seconds(comments),
            )

    def _select_episode(self, episodes: list, ep_id: str, request: DanmuFetchInput) -> DanmuEpisodeCandidate | None:
        if request.episode_number:
            return danmu_episode_matcher.select(self._episode_candidates(episodes), request.episode_number).candidate
        if request.media_type != MediaType.movie:
            return None
        for item in episodes:
            item_mapping: dict = item
            if str(item_mapping.get("id") or item_mapping.get("ep_id") or "") == ep_id:
                return self._episode_candidates([item])[0]
        if len(episodes) == 1:
            return self._episode_candidates(episodes)[0]
        return None

    def _episode_candidates(self, episodes: list) -> list[DanmuEpisodeCandidate]:
        candidates: list[DanmuEpisodeCandidate] = []
        for index, episode_map in enumerate(episodes):
            order = str(episode_map.get("title") or "")
            candidates.append(DanmuEpisodeCandidate(
                external_id=str(episode_map.get("cid") or ""),
                titles=[str(episode_map.get(key) or "") for key in ("title", "long_title", "share_copy")],
                sequence_index=int(order) if order.isdecimal() else index + 1,
                duration_seconds=self._candidate_duration_seconds(episode_map),
            ))
        return candidates

    def _extract_ep_id(self, url: str) -> str | None:
        match = re.search(r"/ep(\d+)", url)
        return match.group(1) if match else None

    def _candidate_duration_seconds(self, candidate_map: Mapping[str, str]) -> float | None:
        value = candidate_map.get("duration")
        try:
            duration = float(value or 0)
        except (TypeError, ValueError):
            return None
        if duration <= 0:
            return None
        return duration / 1000 if duration > 86400 else duration

    def _comments_duration_seconds(self, comments) -> float | None:
        return max((float(comment.time_seconds) for comment in comments), default=0.0) or None
