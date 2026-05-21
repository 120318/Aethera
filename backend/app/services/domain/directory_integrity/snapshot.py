from __future__ import annotations

from app.db.repositories.library_file_repository import LibraryFileRepository
from app.db.repositories.managed_media_profile_repository import ManagedMediaProfileRepository
from app.db.repositories.task_repository import TaskRepository
from app.schemas.domain.download import TaskData, TaskStatus
from app.schemas.domain.library import LibraryFile
from app.schemas.media_id import MediaID
from app.services.config.settings_service import settings_service as default_settings_service
from app.services.domain.directory_integrity.models import DirectoryIntegritySnapshot, MediaDisplayIndex


class DirectoryIntegritySnapshotLoader:
    def __init__(self) -> None:
        self.library_repo = LibraryFileRepository()
        self.task_repo = TaskRepository()
        self.profile_repo = ManagedMediaProfileRepository()
        self.settings_service = default_settings_service

    async def load(self, directory_id: str | None = None) -> DirectoryIntegritySnapshot:
        all_directories = [item for item in self.settings_service.list_directories() if item.enabled]
        directories = all_directories
        if directory_id:
            directories = [item for item in directories if item.id == directory_id]
        policies = {policy.directory_id: policy for policy in self.settings_service.list_directory_integrity_policies()}
        library_files = await self.library_repo.get_all()
        tasks = [task for task in await self.task_repo.get_all() if task.status != TaskStatus.VOID]
        media_display = await self._build_media_display_index(library_files, tasks)
        return DirectoryIntegritySnapshot(
            directories=directories,
            all_directories=all_directories,
            policies=policies,
            library_files=library_files,
            tasks=tasks,
            media_display=media_display,
        )

    async def _build_media_display_index(
        self,
        library_files: list[LibraryFile],
        tasks: list[TaskData],
    ) -> MediaDisplayIndex:
        media_ids: set[MediaID] = {task.media_id for task in tasks if task.media_id}
        media_ids.update(library_file.media_id for library_file in library_files if library_file.media_id)
        profiles = await self.profile_repo.find_by_media_ids(list(media_ids))
        display = {str(profile.media_id): (profile.title, profile.year) for profile in profiles if profile.title}
        for task in tasks:
            if not task.media_id or not task.context or not task.context.media:
                continue
            media = task.context.media
            if media.title:
                display[str(task.media_id)] = (media.title, media.year)
        return display
