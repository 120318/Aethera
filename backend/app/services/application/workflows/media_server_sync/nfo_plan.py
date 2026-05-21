from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.schemas.domain.media import EpisodeInfo, MediaFullInfo, SeasonDetails
from app.schemas.domain.media_server_sync import MediaServerSyncInput, MediaServerSyncTargetFile
from app.schemas.domain.media_types import MediaType
from app.services.application.workflows.media_server_sync.target import media_server_sync_target
from app.services.domain.library.sidecar_files import library_sidecar_files
from app.services.domain.media import media_service
from app.services.integration.media_server import nfo as media_server_nfo
from app.services.integration.media_server import nfo_inspection


@dataclass(frozen=True)
class MediaServerSyncNfoPlan:
    movie_nfo_path: Path | None = None
    movie_anchor_nfo_path: Path | None = None
    tvshow_nfo_path: Path | None = None
    season_nfo_paths: dict[int, Path] = field(default_factory=dict)
    episode_nfo_paths: list[Path] = field(default_factory=list)


class MediaServerSyncNfoPlanService:
    def expected_nfo_paths(
        self,
        media: MediaFullInfo,
        sync_input: MediaServerSyncInput,
    ) -> MediaServerSyncNfoPlan:
        if media.media_type == MediaType.movie:
            media_root_dir = Path(sync_input.media_root_dir or "")
            anchor_file = Path(sync_input.anchor_file or "")
            anchor_nfo = (
                anchor_file.with_suffix(".nfo")
                if anchor_file.suffix and anchor_file.suffix.lower() not in {".bdmv", ".ifo", ".vob"}
                else None
            )
            return MediaServerSyncNfoPlan(
                movie_nfo_path=media_root_dir / "movie.nfo",
                movie_anchor_nfo_path=anchor_nfo,
            )

        show_dir = Path(sync_input.media_root_dir or "")
        season_paths: dict[int, Path] = {}
        episode_paths: list[Path] = []
        seen_episode_paths: set[Path] = set()
        for target in sync_input.transfer_results:
            dest_path = Path(target.destination_path)
            season_dir, season_num = media_server_sync_target.get_season_dir_and_number(dest_path, media)
            if season_dir is not None and season_num is not None and season_dir != show_dir:
                season_paths.setdefault(int(season_num), season_dir / "season.nfo")
            if target.episode_number:
                episode_nfo_path = dest_path.with_suffix(".nfo")
                if episode_nfo_path not in seen_episode_paths:
                    seen_episode_paths.add(episode_nfo_path)
                    episode_paths.append(episode_nfo_path)
        return MediaServerSyncNfoPlan(
            tvshow_nfo_path=show_dir / "tvshow.nfo",
            season_nfo_paths=season_paths,
            episode_nfo_paths=episode_paths,
        )

    async def write_nfo_files(
        self,
        media: MediaFullInfo,
        file_path: str,
        transfer_results: list[MediaServerSyncTargetFile] | None = None,
        *,
        media_root_dir: str | None = None,
    ) -> None:
        sync_input = MediaServerSyncInput(
            anchor_file=file_path,
            media_root_dir=media_root_dir or str(media_server_sync_target.resolve_media_root_dir(media, file_path, transfer_results)),
            transfer_results=transfer_results or [],
        )
        plan = self.expected_nfo_paths(media, sync_input)
        context = media_service.resolve_media_context(media)
        tmdb_id = media_service.tmdb_id_from_media_context(context)
        if media.media_type == MediaType.movie:
            content = media_server_nfo.build_movie_nfo(media, tmdb_id=tmdb_id)
            if plan.movie_nfo_path:
                library_sidecar_files.write_text_file(plan.movie_nfo_path, content)
            if plan.movie_anchor_nfo_path:
                library_sidecar_files.write_text_file(plan.movie_anchor_nfo_path, content)
            return

        if plan.tvshow_nfo_path:
            library_sidecar_files.write_text_file(
                plan.tvshow_nfo_path,
                media_server_nfo.build_tvshow_nfo(media, tmdb_id=tmdb_id),
            )

        if not context.metadata_capabilities.can_generate_enhanced_nfo:
            return

        season_details_map: dict[int, SeasonDetails] = {}
        for season_num, season_nfo_path in sorted(plan.season_nfo_paths.items()):
            season_details = await media_service.get_season_details_for_media(media, season_num)
            if not season_details:
                continue
            season_details_map[season_num] = season_details
            library_sidecar_files.write_text_file(
                season_nfo_path,
                media_server_nfo.build_season_nfo(media, season_details),
            )

        targets_by_path: dict[str, list[MediaServerSyncTargetFile]] = {}
        for target in sync_input.transfer_results:
            targets_by_path.setdefault(target.destination_path, []).append(target)

        for destination_path, targets in targets_by_path.items():
            dest_path = Path(destination_path)
            _, season_num = media_server_sync_target.get_season_dir_and_number(dest_path, media)
            if season_num is None:
                continue
            season_int = int(season_num)
            season_details = await self._get_or_load_season_details(media, season_int, season_details_map)
            selected = await self._select_episode_nfo_target(media, season_int, targets, season_details)
            if selected is None:
                continue
            episode_int, episode_info = selected
            library_sidecar_files.write_text_file(
                dest_path.with_suffix(".nfo"),
                media_server_nfo.build_episode_nfo(
                    media,
                    season_int,
                    episode_int,
                    episode_info,
                    season_details,
                    tmdb_id=tmdb_id,
                ),
            )

    async def _get_or_load_season_details(
        self,
        media: MediaFullInfo,
        season_num: int,
        season_details_map: dict[int, SeasonDetails],
    ) -> SeasonDetails | None:
        if season_num in season_details_map:
            return season_details_map[season_num]
        season_details = await media_service.get_season_details_for_media(media, season_num)
        if season_details:
            season_details_map[season_num] = season_details
        return season_details

    async def _select_episode_nfo_target(
        self,
        media: MediaFullInfo,
        season_number: int,
        targets: list[MediaServerSyncTargetFile],
        season_details: SeasonDetails | None,
    ) -> tuple[int, EpisodeInfo | None] | None:
        fallback: tuple[int, EpisodeInfo | None] | None = None
        for target in targets:
            if not target.episode_number:
                continue
            episode_number = int(target.episode_number)
            episode_info = await media_service.get_episode_info_for_media(media, season_number, episode_number)
            item = (episode_number, episode_info)
            if fallback is None:
                fallback = item
            require_title, require_plot = self._episode_required_fields(episode_info, season_details, episode_number)
            if require_title and require_plot:
                return item
        return fallback

    async def has_incomplete_episode_nfo(self, media: MediaFullInfo, sync_input: MediaServerSyncInput) -> bool:
        return bool(await self.episode_nfo_targets_needing_sync(media, sync_input, include_missing=False))

    async def episode_nfo_targets_needing_sync(
        self,
        media: MediaFullInfo,
        sync_input: MediaServerSyncInput,
        *,
        include_missing: bool = True,
        include_incomplete: bool = True,
    ) -> list[MediaServerSyncTargetFile]:
        targets_by_path: dict[str, list[MediaServerSyncTargetFile]] = {}
        for target in sync_input.transfer_results:
            targets_by_path.setdefault(target.destination_path, []).append(target)

        targets: list[MediaServerSyncTargetFile] = []
        season_details_map: dict[int, SeasonDetails | None] = {}
        for destination_path, grouped_targets in targets_by_path.items():
            path = Path(destination_path).with_suffix(".nfo")
            if not path.exists():
                if include_missing:
                    targets.extend(grouped_targets)
                continue
            if not include_incomplete:
                continue
            if nfo_inspection.is_episode_nfo_complete(path):
                continue
            season_number, _ = self._episode_target_numbers(media, Path(destination_path), None)
            if season_number is None:
                targets.extend(grouped_targets)
                continue
            season_details = season_details_map.get(season_number)
            if season_number not in season_details_map:
                season_details = await media_service.get_season_details_for_media(media, season_number)
                season_details_map[season_number] = season_details
            if await self._episode_group_needs_sync(media, season_number, grouped_targets, season_details, path):
                targets.extend(grouped_targets)
        return targets

    async def _episode_group_needs_sync(
        self,
        media: MediaFullInfo,
        season_number: int,
        targets: list[MediaServerSyncTargetFile],
        season_details: SeasonDetails | None,
        path: Path,
    ) -> bool:
        for target in targets:
            if not target.episode_number:
                return True
            episode_number = int(target.episode_number)
            episode_info = await media_service.get_episode_info_for_media(media, season_number, episode_number)
            require_title, require_plot = self._episode_required_fields(episode_info, season_details, episode_number)
            if not nfo_inspection.is_episode_nfo_complete(path, require_title=require_title, require_plot=require_plot):
                return True
        return False

    def _episode_target_numbers(self, media: MediaFullInfo, path: Path, episode_number: int | None) -> tuple[int | None, int | None]:
        _, season_number = media_server_sync_target.get_season_dir_and_number(path, media)
        if season_number is None or not episode_number:
            return (season_number, None)
        return (int(season_number), int(episode_number))

    def _episode_required_fields(
        self,
        episode_info: EpisodeInfo | None,
        season_details: SeasonDetails | None,
        episode_number: int,
    ) -> tuple[bool, bool]:
        title = str(episode_info.title or "").strip() if episode_info else ""
        overview = str(episode_info.overview or "").strip() if episode_info else ""
        if (not title or not overview) and season_details:
            for episode in season_details.episodes:
                if episode.episode_number != episode_number:
                    continue
                title = title or str(episode.title or "").strip()
                overview = overview or str(episode.overview or "").strip()
                break
        return (bool(title), bool(overview))


media_server_sync_nfo_plan = MediaServerSyncNfoPlanService()
