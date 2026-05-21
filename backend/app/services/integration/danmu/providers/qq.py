from __future__ import annotations

from dataclasses import dataclass
import re

import httpx

from app.schemas.domain.vendor import Vendor
from app.schemas.domain.media_types import MediaType
from app.services.integration.danmu.base import BaseDanmuProvider
from app.services.integration.danmu.models import DanmuFetchInput, DanmuFetchResult
from app.services.integration.danmu.utils import first_query_value, parse_qq_json, parse_query_from_deeplink, vendor_text


@dataclass(frozen=True)
class _QQSegment:
    path: str
    start_seconds: float = 0.0


class QQDanmuProvider(BaseDanmuProvider):
    provider_id = "qq"

    def supports(self, vendor: Vendor) -> bool:
        text = " ".join([vendor_text(vendor.id), vendor_text(vendor.name), vendor_text(vendor.url)])
        return "qq" in text or "tencent" in text or "腾讯" in text

    def can_fetch(self, vendor: Vendor) -> bool:
        cid, _ = self._extract_ids(vendor)
        return self.supports(vendor) and bool(cid)

    async def fetch(self, vendor: Vendor, request: DanmuFetchInput) -> DanmuFetchResult | None:
        cid, fallback_vid = self._extract_ids(vendor)
        if not cid:
            return None
        async with httpx.AsyncClient(timeout=15.0) as client:
            if not request.episode_number:
                if request.media_type != MediaType.movie:
                    return None
                vid = fallback_vid
            else:
                vid = await self._resolve_episode_vid(
                    client,
                    cid,
                    int(request.episode_number),
                    fallback_vid,
                    absolute_episode_number=request.absolute_episode_number,
                    season_number=request.season_number,
                )
            if not vid:
                return None
            base_response = await client.get(f"https://dm.video.qq.com/barrage/base/{vid}")
            base_response.raise_for_status()
            base_mapping: dict = base_response.json()
            comments = []
            segments = self._segments(base_mapping)
            for segment in segments:
                segment_response = await client.get(f"https://dm.video.qq.com/barrage/segment/{vid}/{segment.path}")
                segment_response.raise_for_status()
                comments.extend(parse_qq_json(segment_response.content))
            return DanmuFetchResult(
                provider=self.provider_id,
                comments=comments,
                source_id=vid,
                source_duration_seconds=self._segments_duration_seconds(segments),
            )

    def _extract_ids(self, vendor: Vendor) -> tuple[str | None, str | None]:
        query = parse_query_from_deeplink(vendor.url or "")
        if vendor.url:
            query.update(parse_query_from_deeplink(vendor.url))
        cid = first_query_value(query, "cid")
        vid = first_query_value(query, "vid")
        if cid:
            return cid, vid
        match = re.search(r"/x/cover/([^/?#]+)/([^/?#]+)\.html", vendor.url or "")
        if match:
            return match.group(1), match.group(2)
        match = re.search(r"/x/cover/([^/?#]+)/?", vendor.url or "")
        if match:
            return match.group(1), vid
        return None, vid

    async def _resolve_episode_vid(
        self,
        client: httpx.AsyncClient,
        cid: str,
        episode_number: int,
        fallback_vid: str | None,
        *,
        absolute_episode_number: int | None = None,
        season_number: int | None = None,
    ) -> str | None:
        payload = {
            "has_cache": 1,
            "page_params": {
                "page_type": "detail_operation",
                "page_id": "vsite_episode_list",
                "id_type": "1",
                "page_size": "100",
                "cid": cid,
                "lid": "0",
                "req_from": "web_mobile",
            },
        }
        cookies = {
            "pgv_pvid": "40b67e3b06027f3d",
            "video_platform": "2",
            "vversion_name": "8.2.95",
            "video_bucketid": "4",
            "video_omgid": "0a1ff6bc9407c0b1cff86ee5d359614d",
        }
        response = await client.post(
            "https://pbaccess.video.qq.com/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData",
            params={"video_appid": "3000010", "vplatform": "2"},
            json=payload,
            cookies=cookies,
        )
        response.raise_for_status()
        items = self._collect_item_params(response.json())
        for candidate_episode_number in self._episode_number_candidates(
            episode_number,
            absolute_episode_number=absolute_episode_number,
            season_number=season_number,
        ):
            for item in items:
                item_mapping: dict = item
                item_vid = str(item_mapping.get("vid") or "")
                item_title = str(item_mapping.get("title") or item_mapping.get("play_title") or "")
                if item_vid and self._text_matches_episode_number(item_title, candidate_episode_number):
                    return item_vid
        cover_vid = await self._resolve_episode_vid_from_cover_page(
            client,
            cid,
            episode_number,
            fallback_vid,
            absolute_episode_number=absolute_episode_number,
            season_number=season_number,
        )
        if cover_vid:
            return cover_vid
        if episode_number == 1:
            return fallback_vid
        return None

    def _episode_number_candidates(
        self,
        episode_number: int,
        *,
        absolute_episode_number: int | None,
        season_number: int | None,
    ) -> list[int]:
        candidates: list[int] = []
        if season_number and season_number > 1 and absolute_episode_number and absolute_episode_number != episode_number:
            candidates.append(int(absolute_episode_number))
        candidates.append(int(episode_number))
        return candidates

    def _segment_paths(self, base_mapping) -> list[str]:
        return [segment.path for segment in self._segments(base_mapping)]

    def _segments(self, base_mapping) -> list[_QQSegment]:
        segments_mapping: dict = base_mapping.get("segment_index") or {}
        segments: list[_QQSegment] = []
        for key, segment in segments_mapping.items():
            segment_path = ""
            start_milliseconds = self._segment_start_milliseconds(key)
            if type(segment) is dict:
                segment_mapping: dict = segment
                segment_path = str(segment_mapping.get("segment_name") or "")
                start_milliseconds = self._segment_start_milliseconds(
                    segment_mapping.get("segment_start") or start_milliseconds
                )
            elif segment:
                segment_path = str(segment)
            if segment_path:
                segments.append(_QQSegment(path=segment_path, start_seconds=start_milliseconds / 1000))
        return segments

    def _segment_start_milliseconds(self, value) -> int:
        try:
            return max(int(value or 0), 0)
        except (TypeError, ValueError):
            return 0

    def _segments_duration_seconds(self, segments: list[_QQSegment]) -> float | None:
        duration = 0.0
        for segment in segments:
            duration = max(duration, segment.start_seconds + self._segment_path_duration_seconds(segment.path))
        return duration or None

    def _segment_path_duration_seconds(self, path: str) -> float:
        match = re.search(r"/(\d+)/(\d+)$", path or "")
        if not match:
            return 30.0
        try:
            start_ms = int(match.group(1))
            end_ms = int(match.group(2))
        except ValueError:
            return 30.0
        return max((end_ms - start_ms) / 1000, 0.0) or 30.0

    async def _resolve_episode_vid_from_cover_page(
        self,
        client: httpx.AsyncClient,
        cid: str,
        episode_number: int,
        fallback_vid: str | None,
        *,
        absolute_episode_number: int | None = None,
        season_number: int | None = None,
    ) -> str | None:
        if not fallback_vid or episode_number < 1:
            return None
        response = await client.get(
            f"https://v.qq.com/x/cover/{cid}/{fallback_vid}.html",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        video_ids = self._extract_video_ids(response.text)
        for candidate_episode_number in self._episode_number_candidates(
            episode_number,
            absolute_episode_number=absolute_episode_number,
            season_number=season_number,
        ):
            for video_id in video_ids:
                candidate = await self._fetch_video_page_candidate(client, cid, video_id)
                if self._is_episode_candidate(candidate, candidate_episode_number):
                    return video_id
        return None

    def _extract_video_ids(self, html: str) -> list[str]:
        match = re.search(r"video_ids:\[(?P<values>.*?)\]", html or "")
        if not match:
            return []
        return re.findall(r'"([^"]+)"', match.group("values"))

    async def _fetch_video_page_candidate(self, client: httpx.AsyncClient, cid: str, video_id: str) -> dict[str, str]:
        response = await client.get(
            f"https://v.qq.com/x/cover/{cid}/{video_id}.html",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        return self._extract_video_page_candidate(response.text)

    def _extract_video_page_candidate(self, html: str) -> dict[str, str]:
        current_match = re.search(r"currentVideo:\{(?P<body>.*?),nextVideo", html or "")
        body = current_match.group("body") if current_match else ""
        candidate: dict[str, str] = {}
        for key in ("title", "videoSubTitle", "unionTitle", "playTitle", "duration"):
            value_match = re.search(rf'{key}:"(?P<value>.*?)"', body)
            if value_match:
                candidate[key] = value_match.group("value")
        title_match = re.search(r"<title>(?P<value>.*?)</title>", html or "")
        if title_match:
            candidate["htmlTitle"] = title_match.group("value")
        return candidate

    def _is_episode_candidate(self, candidate: dict[str, str], episode_number: int) -> bool:
        text = " ".join(str(value or "") for value in candidate.values())
        if not text:
            return False
        if any(keyword in text for keyword in ("预告", "花絮", "片花", "彩蛋")):
            return False
        if not self._candidate_matches_episode_number(candidate, episode_number):
            return False
        return self._candidate_duration_seconds(candidate) >= 600

    def _candidate_matches_episode_number(self, candidate: dict[str, str], episode_number: int) -> bool:
        title = str(candidate.get("title") or "")
        if title.isdigit() and int(title) == episode_number:
            return True
        text = " ".join(str(candidate.get(key) or "") for key in ("unionTitle", "playTitle", "htmlTitle"))
        return self._text_matches_episode_number(text, episode_number)

    def _text_matches_episode_number(self, text: str, episode_number: int) -> bool:
        return any(
            pattern in text
            for pattern in (
                f"第{episode_number:02d}集",
                f"第{episode_number}集",
                f"第{episode_number:02d}话",
                f"第{episode_number}话",
                f"{episode_number:02d}集",
                f"{episode_number}集",
                f"_{episode_number:02d}",
                f"_{episode_number}",
            )
        )

    def _candidate_duration_seconds(self, candidate: dict[str, str]) -> int:
        value = str(candidate.get("duration") or "")
        parts = value.split(":")
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except ValueError:
            return 0
        return 0

    def _collect_item_params(self, payload) -> list:
        result = []
        if type(payload) is dict:
            payload_mapping: dict = payload
            item_params = payload_mapping.get("item_params")
            if type(item_params) is dict:
                result.append(item_params)
            for value in payload_mapping.values():
                result.extend(self._collect_item_params(value))
        elif type(payload) is list:
            for value in payload:
                result.extend(self._collect_item_params(value))
        return result
