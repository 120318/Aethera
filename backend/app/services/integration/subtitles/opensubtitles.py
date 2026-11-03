from __future__ import annotations

import httpx

from pydantic import ValidationError

from app.schemas.domain.subtitle import (
    OpenSubtitlesDownloadPayload,
    OpenSubtitlesSearchPayload,
    SubtitleCandidate,
)


class OpenSubtitlesClient:
    base_url = "https://api.opensubtitles.com/api/v1"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key.strip()

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ValueError("OpenSubtitles API key is not configured")
        return {
            "Api-Key": self.api_key,
            "User-Agent": "Aethera v1",
            "Accept": "application/json",
        }

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
            subtitle_file = attributes.files[0]
            file_name = subtitle_file.file_name
            hash_matched = attributes.moviehash_match
            candidates.append(
                SubtitleCandidate(
                    id=str(row.id),
                    file_id=subtitle_file.file_id,
                    provider="opensubtitles",
                    language=attributes.language,
                    format=self._format_from_name(file_name),
                    release=attributes.release,
                    file_name=file_name,
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
                response = await client.post(
                    f"{self.base_url}/download",
                    headers=self._headers(),
                    json={"file_id": file_id},
                )
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
