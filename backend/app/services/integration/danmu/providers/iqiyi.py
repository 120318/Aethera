from __future__ import annotations

import re

import httpx

from app.schemas.domain.vendor import Vendor
from app.schemas.domain.media_types import MediaType
from app.services.integration.danmu.base import BaseDanmuProvider
from app.services.integration.danmu.models import DanmuFetchInput, DanmuFetchResult
from app.services.integration.danmu.utils import parse_iqiyi_xml, vendor_text


class IqiyiDanmuProvider(BaseDanmuProvider):
    provider_id = "iqiyi"

    def supports(self, vendor: Vendor) -> bool:
        text = " ".join([vendor_text(vendor.id), vendor_text(vendor.name), vendor_text(vendor.url)])
        return "iqiyi" in text or "爱奇艺" in text

    def can_fetch(self, vendor: Vendor) -> bool:
        return self.supports(vendor) and self._extract_page_id(vendor.url or "") is not None

    async def fetch(self, vendor: Vendor, request: DanmuFetchInput) -> DanmuFetchResult | None:
        page_id = self._extract_page_id(vendor.url or "")
        if not page_id:
            return None
        tv_id = self._page_id_to_tvid(page_id)
        if not request.episode_number:
            if request.media_type != MediaType.movie:
                return None
            async with httpx.AsyncClient(timeout=15.0) as client:
                comments = await self._fetch_segments(client, str(tv_id))
                return DanmuFetchResult(
                    provider=self.provider_id,
                    comments=comments,
                    source_id=str(tv_id),
                    source_duration_seconds=self._comments_duration_seconds(comments),
                )
        async with httpx.AsyncClient(timeout=15.0) as client:
            base_response = await client.get(f"https://pcw-api.iqiyi.com/video/video/baseinfo/{tv_id}")
            base_response.raise_for_status()
            base_mapping: dict = base_response.json()
            base_data_mapping: dict = base_mapping.get("data", {})
            album_id = str(base_data_mapping.get("albumId") or base_mapping.get("albumId") or "")
            video_count = int(base_data_mapping.get("videoCount") or base_mapping.get("videoCount") or 0)
            if not album_id:
                return None
            if request.episode_count and video_count and video_count != int(request.episode_count):
                return None
            list_response = await client.get(
                "https://pcw-api.iqiyi.com/albums/album/avlistinfo",
                params={"aid": album_id, "page": 1, "size": request.episode_count or video_count or 100},
            )
            list_response.raise_for_status()
            list_mapping: dict = list_response.json()
            list_data_mapping: dict = list_mapping.get("data", {})
            items = list_data_mapping.get("epsodelist") or []
            target = None
            for item in items:
                item_mapping: dict = item
                if int(item_mapping.get("order") or 0) == int(request.episode_number):
                    target = item_mapping
                    break
            if not target:
                return None
            target_mapping: dict = target
            target_tv_id = str(target_mapping.get("tvId") or "")
            if not target_tv_id:
                return None
            comments = await self._fetch_segments(client, target_tv_id)
            return DanmuFetchResult(
                provider=self.provider_id,
                comments=comments,
                source_id=target_tv_id,
                source_duration_seconds=self._comments_duration_seconds(comments),
            )

    def _extract_page_id(self, url: str) -> str | None:
        match = re.search(r"/[vwp]_([^/?#]+)\.html", url)
        return match.group(1) if match else None

    def _page_id_to_tvid(self, page_id: str) -> int:
        mask = list(reversed(bin(0x75706971676C)[2:]))
        bits = list(reversed(bin(int(page_id, 36))[2:]))
        result: list[str] = []
        for index in range(max(len(bits), len(mask))):
            left = int(bits[index]) if index < len(bits) else 0
            right = int(mask[index]) if index < len(mask) else 0
            result.append(str(left ^ right))
        tv_id = int("".join(reversed(result)), 2)
        return 100 * (tv_id + 900000) if tv_id < 900000 else tv_id

    async def _fetch_segments(self, client: httpx.AsyncClient, tv_id: str):
        comments = []
        suffix = tv_id[-4:].zfill(4)
        prefix = f"http://cmts.iqiyi.com/bullet/{suffix[:2]}/{suffix[2:]}"
        for segment in range(1, 61):
            response = await client.get(f"{prefix}/{tv_id}_300_{segment}.z")
            if response.status_code == 404:
                break
            response.raise_for_status()
            parsed = parse_iqiyi_xml(response.content)
            if not parsed:
                break
            comments.extend(parsed)
        return comments

    def _comments_duration_seconds(self, comments) -> float | None:
        return max((float(comment.time_seconds) for comment in comments), default=0.0) or None
