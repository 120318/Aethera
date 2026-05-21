from typing import Literal

from app.schemas.exception.exceptions import DownloadException
from app.schemas.media_id import MediaID
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service
from app.services.platform.domain_lock_service import domain_lock_service


class MediaResourceDeletionService:
    async def delete_media_resources(
        self,
        media_id: MediaID,
        *,
        season_number: int | None = None,
        mode: Literal["tasks_only", "tasks_and_library"],
        delete_files: bool,
        force: bool,
    ) -> tuple[int, int]:
        async with domain_lock_service.acquire_media_delete(media_id, mode) as acquired:
            if not acquired:
                raise DownloadException("backendErrors.mediaDeletionBusy")

            deleted_library_files_count = 0
            if mode == "tasks_and_library":
                deleted_library_files_count = await library_service.delete_media_library_files(
                    media_id,
                    force=force,
                    season=season_number,
                )
                if season_number is None:
                    await library_service.archive_media_entry(media_id)

            tasks = await download_service.get_tasks(media_id=media_id)
            deleted_tasks_count = 0
            for task in tasks:
                if season_number is not None:
                    coverage = download_service.resolve_task_episode_coverage_detail(task)
                    if not coverage.has_known_season or coverage.season_number != season_number:
                        continue
                if not task.id:
                    continue
                deleted = await download_service.delete_task(
                    task.id,
                    delete_files=delete_files,
                    force_delete_record=force,
                )
                if deleted:
                    deleted_tasks_count += 1

            return deleted_tasks_count, deleted_library_files_count


media_resource_deletion_service = MediaResourceDeletionService()
