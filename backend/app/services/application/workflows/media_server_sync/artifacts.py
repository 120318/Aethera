from pathlib import Path

from app.schemas.domain.library import LibraryFile, LibraryFileArtifactStatus, LibraryFileArtifactType
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_server_sync import MediaServerSyncInput, MediaServerSyncTargetFile
from app.services.application.workflows.media_server_sync.nfo_plan import media_server_sync_nfo_plan
from app.services.domain.library.service import library_service
from app.utils.library_paths import build_library_file_path


class MediaServerSyncArtifactMarker:
    async def mark_nfo_artifacts(
        self,
        files: list[LibraryFile],
        media: MediaFullInfo,
        anchor_file: str | None,
        transfer_results: list[MediaServerSyncTargetFile],
        media_root_dir: str | None,
        status: LibraryFileArtifactStatus,
    ) -> None:
        if not anchor_file:
            return
        sync_input = MediaServerSyncInput(
            anchor_file=anchor_file,
            media_root_dir=media_root_dir,
            transfer_results=transfer_results,
        )
        plan = media_server_sync_nfo_plan.expected_nfo_paths(media, sync_input)

        file_by_path = {
            str(build_library_file_path(library_file.path, library_file.file_name)): library_file
            for library_file in files
            if library_file.id
        }
        anchor_library_file = file_by_path.get(anchor_file)
        anchor_id = anchor_library_file.id if anchor_library_file else None
        path_to_file_id: dict[str, str] = {}
        if anchor_id:
            for item in [plan.movie_nfo_path, plan.movie_anchor_nfo_path, plan.tvshow_nfo_path]:
                if item:
                    path_to_file_id[str(item)] = anchor_id
            if media.metadata_capabilities.can_generate_enhanced_nfo:
                for item in plan.season_nfo_paths.values():
                    path_to_file_id[str(item)] = anchor_id
        if media.metadata_capabilities.can_generate_enhanced_nfo:
            for target in transfer_results:
                if not target.episode_number:
                    continue
                library_file = file_by_path.get(target.destination_path)
                if not library_file:
                    continue
                path_to_file_id[str(Path(target.destination_path).with_suffix(".nfo"))] = library_file.id

        for expected_path, library_file_id in path_to_file_id.items():
            artifact_status = status
            if status == LibraryFileArtifactStatus.succeeded and not Path(expected_path).exists():
                artifact_status = LibraryFileArtifactStatus.pending
            await library_service.mark_artifact(
                library_file_id=library_file_id,
                artifact_type=LibraryFileArtifactType.nfo,
                expected_path=expected_path,
                status=artifact_status,
            )

    async def mark_image_artifacts(
        self,
        files: list[LibraryFile],
        media: MediaFullInfo,
        anchor_file: str | None,
        media_root_dir: str | None,
        status: LibraryFileArtifactStatus,
    ) -> None:
        if not anchor_file or not media_root_dir:
            return
        anchor_library_file = next(
            (
                library_file
                for library_file in files
                if str(build_library_file_path(library_file.path, library_file.file_name)) == anchor_file
            ),
            None,
        )
        if not anchor_library_file:
            return
        root = Path(media_root_dir)
        targets: list[tuple[LibraryFileArtifactType, Path]] = []
        if media.poster_path:
            targets.append((LibraryFileArtifactType.poster, root / "poster.jpg"))
        if media.backdrop_path:
            targets.append((LibraryFileArtifactType.fanart, root / "fanart.jpg"))
        if media.logo_path:
            targets.append((LibraryFileArtifactType.logo, root / "logo.png"))
        for artifact_type, expected_path in targets:
            artifact_status = status
            if status == LibraryFileArtifactStatus.succeeded and not expected_path.exists():
                artifact_status = LibraryFileArtifactStatus.pending
            await library_service.mark_artifact(
                library_file_id=anchor_library_file.id,
                artifact_type=artifact_type,
                expected_path=str(expected_path),
                status=artifact_status,
            )


media_server_sync_artifacts = MediaServerSyncArtifactMarker()
