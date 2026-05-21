from __future__ import annotations

import asyncio
import hashlib
import json
import time

import httpx

from app.schemas.domain.vendor import Vendor
from app.schemas.domain.media_types import MediaType
from app.services.integration.danmu.base import BaseDanmuProvider
from app.services.integration.danmu.models import DanmuComment, DanmuFetchInput, DanmuFetchResult
from app.services.integration.danmu.utils import extract_youku_show_id, extract_youku_video_id, vendor_text


class YoukuDanmuProvider(BaseDanmuProvider):
    provider_id = "youku"
    _client_id = "53e6cc67237fc59a"
    _app_key = "24679788"
    _msg_secret = "kZJ^&xLQdW2W"
    _max_danmu_segments = 180
    _danmu_segment_concurrency = 8

    def supports(self, vendor: Vendor) -> bool:
        text = " ".join([vendor_text(vendor.id), vendor_text(vendor.name), vendor_text(vendor.url)])
        return "youku" in text or "优酷" in text

    def can_fetch(self, vendor: Vendor) -> bool:
        url = vendor.url or ""
        return self.supports(vendor) and (extract_youku_video_id(url) is not None or extract_youku_show_id(url) is not None)

    async def fetch(self, vendor: Vendor, request: DanmuFetchInput) -> DanmuFetchResult | None:
        url = vendor.url or ""
        video_id = extract_youku_video_id(url)
        show_id = extract_youku_show_id(url)
        if not video_id and not show_id:
            return None
        if not request.episode_number:
            if request.media_type != MediaType.movie or not video_id:
                return None
            async with httpx.AsyncClient(timeout=15.0) as client:
                comments = await self._fetch_danmu(client, video_id)
                return DanmuFetchResult(
                    provider=self.provider_id,
                    comments=comments,
                    source_id=video_id,
                    source_duration_seconds=self._comments_duration_seconds(comments),
                )
        async with httpx.AsyncClient(timeout=15.0) as client:
            resolved_show_id = show_id or await self._resolve_show_id(client, video_id or "")
            if not resolved_show_id:
                return None
            target_video_id = await self._resolve_episode_video_id(client, resolved_show_id, request)
            if not target_video_id:
                return None
            comments = await self._fetch_danmu(client, target_video_id)
            return DanmuFetchResult(
                provider=self.provider_id,
                comments=comments,
                source_id=target_video_id,
                source_duration_seconds=self._comments_duration_seconds(comments),
            )

    async def _resolve_show_id(self, client: httpx.AsyncClient, video_id: str) -> str | None:
        response = await client.get(
            "https://openapi.youku.com/v2/videos/show_basic.json",
            params={"client_id": self._client_id, "package": "com.huawei.hwvplayer.youku", "video_id": video_id},
        )
        response.raise_for_status()
        response_mapping: dict = response.json()
        show_mapping: dict = response_mapping.get("show", {})
        return str(show_mapping.get("id") or response_mapping.get("show_id") or "")

    async def _resolve_episode_video_id(
        self,
        client: httpx.AsyncClient,
        show_id: str,
        request: DanmuFetchInput,
    ) -> str | None:
        response = await client.get(
            "https://openapi.youku.com/v2/shows/videos.json",
            params={
                "client_id": self._client_id,
                "package": "com.huawei.hwvplayer.youku",
                "ext": "show",
                "show_id": show_id,
                "page": 1,
                "count": request.episode_count or 100,
            },
        )
        response.raise_for_status()
        response_mapping: dict = response.json()
        videos = response_mapping.get("videos") or []
        index = int(request.episode_number or 0) - 1
        if index < 0 or index >= len(videos):
            return None
        video_mapping: dict = videos[index]
        return str(video_mapping.get("id") or video_mapping.get("video_id") or "")

    async def _fetch_danmu(self, client: httpx.AsyncClient, video_id: str) -> list[DanmuComment]:
        token = await self._ensure_mtop_token(client, video_id)
        if not token:
            return []
        semaphore = asyncio.Semaphore(self._danmu_segment_concurrency)
        segment_results = await asyncio.gather(
            *(
                self._fetch_danmu_segment_with_limit(semaphore, client, token, video_id, segment)
                for segment in range(self._max_danmu_segments)
            )
        )
        return [comment for segment_comments in segment_results for comment in segment_comments]

    async def _fetch_danmu_segment_with_limit(
        self,
        semaphore: asyncio.Semaphore,
        client: httpx.AsyncClient,
        token: str,
        video_id: str,
        segment: int,
    ) -> list[DanmuComment]:
        async with semaphore:
            return await self._fetch_danmu_segment(client, token, video_id, segment)

    async def _fetch_danmu_segment(
        self,
        client: httpx.AsyncClient,
        token: str,
        video_id: str,
        segment: int,
    ) -> list[DanmuComment]:
        timestamp = str(int(time.time() * 1000))
        data_text = self._build_danmu_data(video_id, int(timestamp), segment)
        sign = hashlib.md5(f"{token}&{timestamp}&{self._app_key}&{data_text}".encode("utf-8")).hexdigest()
        response = await client.get(
            "https://acs.youku.com/h5/mopen.youku.danmu.list/1.0/",
            params={"jsv": "2.7.0", "appKey": self._app_key, "t": timestamp, "sign": sign, "data": data_text},
        )
        response.raise_for_status()
        return self._parse_danmu_payload(response.text)

    async def _ensure_mtop_token(self, client: httpx.AsyncClient, video_id: str) -> str:
        raw_token = client.cookies.get("_m_h5_tk")
        token = str(raw_token or "").split("_", 1)[0]
        if token:
            return token
        timestamp = str(int(time.time() * 1000))
        response = await client.get(
            "https://acs.youku.com/h5/mopen.youku.danmu.list/1.0/",
            params={
                "jsv": "2.7.0",
                "appKey": self._app_key,
                "t": timestamp,
                "sign": "",
                "data": self._build_danmu_data(video_id, int(timestamp), 0),
            },
        )
        response.raise_for_status()
        raw_token = client.cookies.get("_m_h5_tk")
        return str(raw_token or "").split("_", 1)[0]

    def _build_danmu_data(self, video_id: str, timestamp: int, segment: int) -> str:
        data = {"ctime": timestamp, "ctype": 10004, "mat": segment, "mcount": 1, "pid": 0, "sver": "3.1.0", "type": 1, "vid": video_id}
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    def _parse_danmu_payload(self, payload: str) -> list[DanmuComment]:
        if payload.startswith("mtopjsonp"):
            payload = payload[payload.find("(") + 1 : payload.rfind(")")]
        parsed_mapping: dict = json.loads(payload)
        comments: list[DanmuComment] = []
        data_mapping: dict = parsed_mapping.get("data", {})
        raw_result = data_mapping.get("result") or []
        if type(raw_result) is str:
            result_mapping: dict = json.loads(raw_result)
            raw_data = result_mapping.get("data", {})
            if type(raw_data) is dict:
                result_data_mapping: dict = raw_data
                result = result_data_mapping.get("result") or []
            else:
                result = []
        else:
            result = raw_result
        for item in result:
            if type(item) is not dict:
                continue
            item_mapping: dict = item
            text = str(item_mapping.get("content") or item_mapping.get("text") or "").strip()
            if not text:
                continue
            try:
                time_seconds = float(item_mapping.get("playat") or item_mapping.get("time") or 0) / 1000
            except (TypeError, ValueError):
                time_seconds = 0.0
            comments.append(DanmuComment(time_seconds=time_seconds, text=text))
        return comments

    def _comments_duration_seconds(self, comments: list[DanmuComment]) -> float | None:
        return max((float(comment.time_seconds) for comment in comments), default=0.0) or None
