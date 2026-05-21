import time
from pathlib import Path

from app.schemas.config import MediaServerSyncConfig
from app.schemas.domain.library import LibraryMediaLayout
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_server_sync import (
    MediaServerSyncDetectNeeds,
    MediaServerSyncInput,
    MediaServerSyncState,
    MediaServerSyncTargetFile,
)
from app.schemas.domain.media_types import MediaType
from app.services.application.workflows.media_server_sync.config import media_server_sync_interval_seconds
from app.services.application.workflows.media_server_sync.nfo_plan import media_server_sync_nfo_plan
from app.services.application.workflows.media_server_sync.target import media_server_sync_target
from app.services.domain.library.sidecar_files import library_sidecar_files
from app.services.integration.media_server import nfo_inspection


class MediaServerSyncNeedsService:
    async def detect(
        self,
        media: MediaFullInfo,
        state: MediaServerSyncState,
        sync_cfg: MediaServerSyncConfig,
        layout: LibraryMediaLayout,
    ) -> MediaServerSyncDetectNeeds:
        if not layout.entries:
            return MediaServerSyncDetectNeeds(should_run=False, missing_flags=["no_lib"])

        sync_input = media_server_sync_target.build_input(media, layout)
        if not sync_input or not sync_input.anchor_file or not sync_input.media_root_dir:
            return MediaServerSyncDetectNeeds(should_run=False, missing_flags=["no_video"])

        missing_flags = await self._detect_missing_flags(media, sync_input, sync_cfg)
        if state.last_success_at is None or self._is_stale(media, state, sync_cfg):
            missing_flags.append("stale")
        return self._needs_from_input(missing_flags, sync_input, await self._targeted_transfer_results(media, sync_input, missing_flags))

    async def _detect_missing_flags(
        self,
        media: MediaFullInfo,
        sync_input: MediaServerSyncInput,
        sync_cfg: MediaServerSyncConfig,
    ) -> list[str]:
        plan = media_server_sync_nfo_plan.expected_nfo_paths(media, sync_input)
        missing_flags: list[str] = []
        if media.media_type == MediaType.movie:
            root_complete = nfo_inspection.is_movie_nfo_complete(plan.movie_nfo_path, media)
            anchor_complete = nfo_inspection.is_movie_nfo_complete(plan.movie_anchor_nfo_path, media)
            root_exists = library_sidecar_files.path_exists(plan.movie_nfo_path)
            anchor_exists = library_sidecar_files.path_exists(plan.movie_anchor_nfo_path)
            if not (root_exists or anchor_exists):
                missing_flags.append("movie_nfo_missing")
            elif not (root_complete or anchor_complete):
                missing_flags.append("movie_nfo_incomplete")
            if sync_cfg.download_images:
                missing_flags.extend(self._detect_missing_image_flags(media, sync_input))
            return missing_flags

        if plan.tvshow_nfo_path and not library_sidecar_files.path_exists(plan.tvshow_nfo_path):
            missing_flags.append("tvshow_nfo_missing")
        elif not nfo_inspection.is_tvshow_nfo_complete(plan.tvshow_nfo_path, media):
            missing_flags.append("tvshow_nfo_incomplete")
        if media.metadata_capabilities.can_generate_enhanced_nfo:
            if library_sidecar_files.missing_paths(list(plan.season_nfo_paths.values())):
                missing_flags.append("season_nfo_missing")
            elif self._has_incomplete_season_nfo(list(plan.season_nfo_paths.values())):
                missing_flags.append("season_nfo_incomplete")
            if await media_server_sync_nfo_plan.episode_nfo_targets_needing_sync(
                media,
                sync_input,
                include_incomplete=False,
            ):
                missing_flags.append("episode_nfo_missing")
            elif await media_server_sync_nfo_plan.has_incomplete_episode_nfo(media, sync_input):
                missing_flags.append("episode_nfo_incomplete")
        if sync_cfg.download_images:
            missing_flags.extend(self._detect_missing_image_flags(media, sync_input))
        return missing_flags

    def _has_incomplete_season_nfo(self, paths: list[Path | None]) -> bool:
        for path in paths:
            if path and not nfo_inspection.is_season_nfo_complete(path):
                return True
        return False

    def _detect_missing_image_flags(
        self,
        media: MediaFullInfo,
        sync_input: MediaServerSyncInput,
    ) -> list[str]:
        if not sync_input.media_root_dir:
            return []
        root = Path(sync_input.media_root_dir)
        flags: list[str] = []
        if media.poster_path and not library_sidecar_files.path_exists(root / "poster.jpg"):
            flags.append("poster_missing")
        if media.backdrop_path and not library_sidecar_files.path_exists(root / "fanart.jpg"):
            flags.append("fanart_missing")
        if media.logo_path and not library_sidecar_files.path_exists(root / "logo.png"):
            flags.append("logo_missing")
        return flags

    def _needs_from_input(
        self,
        missing_flags: list[str],
        sync_input: MediaServerSyncInput,
        transfer_results: list[MediaServerSyncTargetFile] | None = None,
    ) -> MediaServerSyncDetectNeeds:
        return MediaServerSyncDetectNeeds(
            should_run=bool(missing_flags),
            missing_flags=self._unique_in_order(missing_flags),
            updated_paths=self._unique_in_order(sync_input.updated_paths),
            transfer_results=transfer_results if transfer_results is not None else sync_input.transfer_results,
            anchor_file=sync_input.anchor_file,
            media_root_dir=sync_input.media_root_dir,
        )

    async def _targeted_transfer_results(
        self,
        media: MediaFullInfo,
        sync_input: MediaServerSyncInput,
        missing_flags: list[str],
    ) -> list[MediaServerSyncTargetFile]:
        unique_flags = set(missing_flags)
        episode_flags = {"episode_nfo_missing", "episode_nfo_incomplete"}
        if not unique_flags or not unique_flags.issubset(episode_flags):
            if media.media_type == MediaType.tv and "stale" in unique_flags:
                return await self._tv_stale_transfer_results(media, sync_input, unique_flags, episode_flags)
            return sync_input.transfer_results
        return await media_server_sync_nfo_plan.episode_nfo_targets_needing_sync(media, sync_input)

    async def _tv_stale_transfer_results(
        self,
        media: MediaFullInfo,
        sync_input: MediaServerSyncInput,
        missing_flags: set[str],
        episode_flags: set[str],
    ) -> list[MediaServerSyncTargetFile]:
        results = self._season_metadata_transfer_results(media, sync_input)
        if missing_flags & episode_flags:
            results.extend(await media_server_sync_nfo_plan.episode_nfo_targets_needing_sync(media, sync_input))
        return self._unique_transfer_results(results)

    def _season_metadata_transfer_results(
        self,
        media: MediaFullInfo,
        sync_input: MediaServerSyncInput,
    ) -> list[MediaServerSyncTargetFile]:
        by_season: dict[int, MediaServerSyncTargetFile] = {}
        fallback: MediaServerSyncTargetFile | None = None
        for target in sync_input.transfer_results:
            path = Path(target.destination_path)
            _, season_number = media_server_sync_target.get_season_dir_and_number(path, media)
            if season_number is None:
                fallback = fallback or MediaServerSyncTargetFile(destination_path=target.destination_path)
                continue
            by_season.setdefault(int(season_number), MediaServerSyncTargetFile(destination_path=target.destination_path))
        if by_season:
            return [by_season[season] for season in sorted(by_season)]
        return [fallback] if fallback else []

    @staticmethod
    def _unique_transfer_results(results: list[MediaServerSyncTargetFile]) -> list[MediaServerSyncTargetFile]:
        seen: set[tuple[str, int | None]] = set()
        unique: list[MediaServerSyncTargetFile] = []
        for item in results:
            key = (item.destination_path, item.episode_number)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    @staticmethod
    def _unique_in_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _is_stale(
        self,
        media: MediaFullInfo,
        state: MediaServerSyncState,
        sync_cfg: MediaServerSyncConfig,
    ) -> bool:
        if not state.last_success_at:
            return True
        return (time.time() - state.last_success_at) > media_server_sync_interval_seconds(media, sync_cfg)


media_server_sync_needs = MediaServerSyncNeedsService()
