from __future__ import annotations

import asyncio
import os
import struct
import uuid
from pathlib import Path

from app.schemas.config import SubtitlesAddonConfig
from app.schemas.domain.library import LibraryFile, LibraryFileArtifactStatus
from app.schemas.domain.subtitle import (
    SubtitleBatchFillResponse,
    SubtitleCandidate,
    SubtitleInstallRequest,
    SubtitleInstallResponse,
)
from app.schemas.exception import InvalidRequestException, ResourceNotFoundException, SubtitleFileException
from app.services.application.workflows.media_server_sync import refresh_library_file
from app.services.application.workflows.scoped_seasons import library_file_season_number
from app.services.config.settings_service import settings_service
from app.services.domain.library.service import library_service
from app.services.integration.subtitles.opensubtitles import OpenSubtitlesClient
from app.utils.library_paths import build_library_file_path
from app.utils.media_sidecars import is_danmu_sidecar_path

SUBTITLE_ARTIFACT_TYPE = "subtitle"
_HASH_CHUNK_SIZE = 65536
_SUBTITLE_FORMATS = {"srt", "ass", "ssa", "sub", "vtt"}


class SubtitleApplicationService:
    def config(self) -> SubtitlesAddonConfig:
        return settings_service.get_addons_config().subtitles

    async def search_for_file(self, file_id: str) -> list[SubtitleCandidate]:
        library_file, video_path = await self._resolve_video(file_id)
        config = self._ready_config()
        movie_hash, movie_size = await asyncio.to_thread(self._opensubtitles_hash, video_path)
        attrs = library_file.resource_attributes
        seasons = list(attrs.seasons or []) if attrs else []
        episodes = list(attrs.episodes or []) if attrs else []
        return await OpenSubtitlesClient(config.api_key).search(
            movie_hash=movie_hash,
            movie_size=movie_size,
            languages=config.languages,
            season_number=int(seasons[0]) if len(seasons) == 1 else None,
            episode_number=int(episodes[0]) if len(episodes) == 1 else None,
        )

    async def preview(self, candidate_file_id: int) -> str:
        config = self._ready_config()
        content = await OpenSubtitlesClient(config.api_key).download(candidate_file_id)
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return content.decode(encoding)[:4000]
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")[:4000]

    async def install(self, request: SubtitleInstallRequest) -> SubtitleInstallResponse:
        library_file, video_path = await self._resolve_video(request.file_id)
        config = self._ready_config()
        subtitle_format = request.format.lower()
        if subtitle_format not in _SUBTITLE_FORMATS:
            raise SubtitleFileException(
                "backendErrors.subtitleFormatUnsupported",
                params={"format": request.format},
            )
        language = self._normalize_language(request.language)
        destination = video_path.with_suffix(f".{language}.{subtitle_format}")
        content = await OpenSubtitlesClient(config.api_key).download(request.candidate_file_id)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            await asyncio.to_thread(temporary.write_bytes, content)
            await asyncio.to_thread(os.replace, temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
        await library_service.mark_artifact(
            library_file_id=library_file.id,
            artifact_type=SUBTITLE_ARTIFACT_TYPE,
            expected_path=str(destination),
            status=LibraryFileArtifactStatus.succeeded,
        )
        await refresh_library_file(library_file, str(video_path))
        return SubtitleInstallResponse(path=str(destination), artifact_type=SUBTITLE_ARTIFACT_TYPE)

    async def fill_missing(self, media_id, season_number: int | None = None) -> SubtitleBatchFillResponse:
        self._ready_config()
        files = await library_service.get_files_by_media(media_id)
        result = SubtitleBatchFillResponse()
        for library_file in files:
            if not library_service.is_primary_file(library_file) or not library_service.file_exists(library_file):
                continue
            if season_number is not None and library_file_season_number(library_file) != season_number:
                continue
            result.processed_count += 1
            try:
                video_path = build_library_file_path(library_file.path, library_file.file_name)
                if self._has_subtitle(video_path):
                    result.skipped_count += 1
                    continue
                candidates = await self.search_for_file(library_file.id)
                if not candidates:
                    result.skipped_count += 1
                    continue
                candidate = sorted(
                    candidates,
                    key=lambda item: (item.hash_matched, item.match_confidence, item.download_count),
                    reverse=True,
                )[0]
                await self.install(
                    SubtitleInstallRequest(
                        file_id=library_file.id,
                        candidate_file_id=candidate.file_id,
                        language=candidate.language,
                        format=candidate.format,
                    )
                )
                result.installed_count += 1
            except (OSError, RuntimeError, ValueError, ResourceNotFoundException, SubtitleFileException):
                result.failed_count += 1
        return result

    async def _resolve_video(self, file_id: str) -> tuple[LibraryFile, Path]:
        library_file = await library_service.find_file_by_id(file_id)
        if library_file is None or not library_service.is_primary_file(library_file):
            raise ResourceNotFoundException("backendErrors.resourceFileNotFound")
        video_path = build_library_file_path(library_file.path, library_file.file_name)
        if not video_path.is_file():
            raise ResourceNotFoundException("backendErrors.resourceFileNotFound")
        return library_file, video_path

    def _ready_config(self) -> SubtitlesAddonConfig:
        config = self.config()
        if not config.enabled:
            raise InvalidRequestException(
                "backendErrors.addonDisabled",
                params={"addon_id": "subtitles"},
            )
        if config.provider != "opensubtitles" or not config.api_key.strip():
            raise InvalidRequestException("backendErrors.subtitleProviderNotConfigured")
        return config

    @staticmethod
    def _normalize_language(language: str) -> str:
        value = language.strip().lower().replace("_", "-")
        return value or "und"

    @staticmethod
    def _has_subtitle(video_path: Path) -> bool:
        prefix = f"{video_path.stem}."
        return any(
            item.is_file()
            and item.name.startswith(prefix)
            and item.suffix.lower().lstrip(".") in _SUBTITLE_FORMATS
            and not is_danmu_sidecar_path(item)
            for item in video_path.parent.iterdir()
        )

    @staticmethod
    def _opensubtitles_hash(path: Path) -> tuple[str, int]:
        size = path.stat().st_size
        if size < _HASH_CHUNK_SIZE * 2:
            raise SubtitleFileException("backendErrors.subtitleVideoTooSmall")
        value = size
        with path.open("rb") as handle:
            for chunk_offset in (0, size - _HASH_CHUNK_SIZE):
                handle.seek(chunk_offset)
                chunk = handle.read(_HASH_CHUNK_SIZE)
                values = struct.unpack(f"<{len(chunk) // 8}Q", chunk)
                value = (value + sum(values)) & 0xFFFFFFFFFFFFFFFF
        return f"{value:016x}", size


subtitle_application_service = SubtitleApplicationService()
