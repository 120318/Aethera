from __future__ import annotations

import asyncio
from urllib.parse import urlparse

import httpx

from pydantic import ValidationError

from app.schemas.domain.subtitle import (
    OpenSubtitlesDownloadPayload,
    OpenSubtitlesLoginPayload,
    OpenSubtitlesSearchPayload,
    SubtitleCandidate,
)


class OpenSubtitlesClient:
    base_url = "https://api.opensubtitles.com/api/v1"
    _allowed_api_hosts = {"api.opensubtitles.com", "vip-api.opensubtitles.com"}

    def __init__(self, api_key: str, username: str = "", password: str = "") -> None:
        self.api_key = api_key.strip()
        self.username = username.strip()
        self.password = password
        self._token = ""
        self._authenticated_base_url = self.base_url
        self._login_lock = asyncio.Lock()

    def _headers(self, *, authenticated: bool = False) -> dict[str, str]:
        if not self.api_key:
            raise ValueError("OpenSubtitles API key is not configured")
        headers = {
            "Api-Key": self.api_key,
            "User-Agent": "Aethera v1",
            "Accept": "application/json",
        }
        if authenticated:
            if not self._token:
                raise ValueError("OpenSubtitles user authentication is not configured")
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _reset_authentication(self) -> None:
        self._token = ""
        self._authenticated_base_url = self.base_url

    async def _authenticated_headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        if self._token:
            return self._headers(authenticated=True)
        async with self._login_lock:
            if not self._token:
                await self._login(client)
        return self._headers(authenticated=True)

    async def _login(self, client: httpx.AsyncClient) -> None:
        if not self.username or not self.password:
            raise ValueError("OpenSubtitles user credentials are not configured")
        try:
            response = await client.post(
                f"{self.base_url}/login",
                headers=self._headers(),
                json={"username": self.username, "password": self.password},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ValueError(f"OpenSubtitles login failed: {exc}") from exc
        try:
            payload = OpenSubtitlesLoginPayload.model_validate(response.json())
        except ValidationError as exc:
            raise ValueError("OpenSubtitles returned an invalid login response") from exc
        self._token = payload.token
        self._authenticated_base_url = self._normalize_api_base_url(payload.base_url)

    @classmethod
    def _normalize_api_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if "://" not in normalized:
            normalized = f"https://{normalized}"
        parsed = urlparse(normalized)
        if parsed.scheme != "https" or parsed.hostname not in cls._allowed_api_hosts:
            raise ValueError("OpenSubtitles returned an invalid API base URL")
        return f"https://{parsed.hostname}/api/v1"

    async def search(
        self,
        *,
        movie_hash: str,
        movie_size: int,
        languages: list[str],
        season_number: int | None,
        episode_number: int | None,
    ) -> list[SubtitleCandidate]:
        params: dict[str, str | int] = {
            "moviehash": movie_hash,
            "moviebytesize": movie_size,
            "languages": ",".join(languages),
            "order_by": "download_count",
            "order_direction": "desc",
        }
        if season_number is not None:
            params["season_number"] = season_number
        if episode_number is not None:
            params["episode_number"] = episode_number
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                authenticated = bool(self._token)
                response = await client.get(
                    f"{self._authenticated_base_url if authenticated else self.base_url}/subtitles",
                    headers=self._headers(authenticated=authenticated),
                    params=params,
                )
                if response.status_code == 401 and authenticated:
                    self._reset_authentication()
                    response = await client.get(
                        f"{self.base_url}/subtitles",
                        headers=self._headers(),
                        params=params,
                    )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ValueError(f"OpenSubtitles search failed: {exc}") from exc
        try:
            payload = OpenSubtitlesSearchPayload.model_validate(response.json())
        except ValidationError as exc:
            raise ValueError("OpenSubtitles returned an invalid search response") from exc
        candidates: list[SubtitleCandidate] = []
        for row in payload.data:
            attributes = row.attributes
            if not attributes.files:
                continue
            hash_matched = attributes.moviehash_match
            release_file_count = len(attributes.files)
            for subtitle_file in attributes.files:
                file_name = subtitle_file.file_name
                candidates.append(
                    SubtitleCandidate(
                        id=f"{row.id}:{subtitle_file.file_id}",
                        file_id=subtitle_file.file_id,
                        provider="opensubtitles",
                        language=attributes.language,
                        format=self._format_from_name(file_name),
                        release=attributes.release,
                        file_name=file_name,
                        cd_number=subtitle_file.cd_number,
                        release_file_count=release_file_count,
                        uploader=attributes.uploader.name,
                        download_count=attributes.download_count,
                        match_confidence=1.0 if hash_matched else 0.8,
                        hash_matched=hash_matched,
                        hearing_impaired=attributes.hearing_impaired,
                        machine_translated=attributes.machine_translated,
                    )
                )
        return candidates

    async def download(self, file_id: int) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = None
                for attempt in range(2):
                    headers = await self._authenticated_headers(client)
                    response = await client.post(
                        f"{self._authenticated_base_url}/download",
                        headers=headers,
                        json={"file_id": file_id},
                    )
                    if response.status_code != 401 or attempt > 0:
                        break
                    self._reset_authentication()
                if response is None:
                    raise ValueError("OpenSubtitles download did not return a response")
                response.raise_for_status()
                try:
                    payload = OpenSubtitlesDownloadPayload.model_validate(response.json())
                except ValidationError as exc:
                    raise ValueError("OpenSubtitles returned an invalid download response") from exc
                subtitle_response = await client.get(payload.link)
                subtitle_response.raise_for_status()
                return subtitle_response.content
        except httpx.HTTPError as exc:
            raise ValueError(f"OpenSubtitles download failed: {exc}") from exc

    @staticmethod
    def _format_from_name(file_name: str) -> str:
        suffix = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "srt"
        return suffix if suffix in {"srt", "ass", "ssa", "sub", "vtt"} else "srt"
