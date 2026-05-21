from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import func, select

from app.db.repositories.settings_sqlite_repository import SettingsSqliteRepository
from app.db.repositories.library_file_repository import LibraryFileRepository
from app.db.sql.models import MediaSubscriptionSettingsORM, TaskORM
from app.db.sql.session import SessionLocal
from app.schemas.config import AppConfig, DirectoryConfig, Template
from app.schemas.domain.media_types import MediaType
from app.schemas.exception import ConfigurationException
from app.schemas.runtime.settings_runtime import SettingsUsage
from app.services.config.naming_template_settings import NamingTemplateSettings
from app.utils.fs_utils import ensure_directory


class DirectorySettings:
    def __init__(
        self,
        repo: SettingsSqliteRepository,
        naming_templates: NamingTemplateSettings,
        create_storage_dirs: Callable[[AppConfig], None],
        library_file_repo: LibraryFileRepository | None = None,
    ) -> None:
        self._repo = repo
        self._naming_templates = naming_templates
        self._create_storage_dirs = create_storage_dirs
        self._library_file_repo = library_file_repo or LibraryFileRepository()

    def list(self) -> list[DirectoryConfig]:
        return self._repo.directories.list()

    def replace_all(self, directories: list[DirectoryConfig]) -> None:
        self._repo.directories.replace(directories)

    def get_by_id(self, directory_id: str) -> DirectoryConfig | None:
        return next((directory for directory in self.list() if directory.id == directory_id), None)

    def get_default(self, media_type: MediaType) -> DirectoryConfig | None:
        enabled = [item for item in self.list() if item.media_type == media_type and item.enabled]
        return next((item for item in enabled if item.is_default), None) or (enabled[0] if enabled else None)

    def get_template_by_directory_id(self, directory_id: str) -> Template | None:
        directory = self.get_by_id(directory_id)
        if not directory:
            return None
        template_id = None
        if directory.media_type == MediaType.movie and directory.movie_template_id:
            template_id = directory.movie_template_id
        elif directory.media_type == MediaType.tv and directory.tv_template_id:
            template_id = directory.tv_template_id
        if template_id:
            template = self._naming_templates.get_template_by_id(template_id)
            if template:
                return template
        default_id = self._default_template_id_for(directory.media_type)
        return self._naming_templates.get_template_by_id(default_id) if default_id else None

    def create(self, directory: DirectoryConfig) -> DirectoryConfig:
        directories = self.list()
        if any(item.id == directory.id for item in directories):
            raise ConfigurationException("backendErrors.config.directoryIdExists", params={"id": directory.id})
        has_default = any(item.is_default and item.media_type == directory.media_type for item in directories)
        if not has_default:
            directory = directory.model_copy(update={"is_default": True})
        directories = self._apply_default_flag(directories, directory)
        directories.append(directory)
        self.replace_all(directories)
        self._create_storage_dirs(AppConfig(directories=directories))
        return directory

    def update(self, directory: DirectoryConfig) -> DirectoryConfig:
        directories = self.list()
        current_index = next((index for index, item in enumerate(directories) if item.id == directory.id), -1)
        if current_index == -1:
            raise ConfigurationException("backendErrors.config.directoryNotFound", params={"id": directory.id})
        current = directories[current_index]
        usage = self.get_usage(directory.id)
        if current.path != directory.path and usage.library_file_count > 0:
            raise ConfigurationException("backendErrors.config.directoryPathInUse", params={"id": directory.id})
        if current.download_path != directory.download_path and (usage.task_count > 0 or usage.library_file_count > 0):
            raise ConfigurationException("backendErrors.config.directoryDownloadPathInUse", params={"id": directory.id})
        directories = self._apply_default_flag(directories, directory)
        current_index = next((index for index, item in enumerate(directories) if item.id == directory.id), -1)
        directories[current_index] = directory
        self.replace_all(directories)
        self._create_storage_dirs(AppConfig(directories=directories))
        return directory

    def delete(self, directory_id: str) -> None:
        directories = self.list()
        directory = next((item for item in directories if item.id == directory_id), None)
        if directory is None:
            raise ConfigurationException("backendErrors.config.directoryNotFound", params={"id": directory_id})
        if directory.is_default:
            raise ConfigurationException("backendErrors.config.defaultDirectoryCannotDelete")
        usage = self.get_usage(directory_id)
        if usage.library_file_count > 0:
            raise ConfigurationException("backendErrors.config.directoryLibraryFilesInUse", params={"id": directory_id})
        self.replace_all([item for item in directories if item.id != directory_id])

    def set_default(self, directory_id: str, media_type: MediaType) -> None:
        directories = self.list()
        directory = next((item for item in directories if item.id == directory_id), None)
        if directory is None:
            raise ConfigurationException("backendErrors.config.directoryNotFound", params={"id": directory_id})
        if directory.media_type != media_type:
            raise ConfigurationException("backendErrors.config.directoryMediaTypeUnsupported", params={"mediaType": media_type.value})
        self.replace_all(
            [
                item.model_copy(update={"is_default": item.id == directory_id})
                if item.media_type == media_type
                else item
                for item in directories
            ]
        )

    def validate_immutable_fields(self, next_directories: list[DirectoryConfig]) -> None:
        current_directories = {item.id: item for item in self.list()}
        for item in next_directories:
            current = current_directories.get(item.id)
            if not current:
                continue
            usage = self.get_usage(item.id)
            if current.path != item.path and usage.library_file_count > 0:
                raise ConfigurationException("backendErrors.config.directoryPathInUse", params={"id": item.id})
            if current.download_path != item.download_path and (usage.task_count > 0 or usage.library_file_count > 0):
                raise ConfigurationException("backendErrors.config.directoryDownloadPathInUse", params={"id": item.id})

    def validate_directory(self, directory: DirectoryConfig) -> list[str]:
        errors: list[str] = []
        if not directory.path:
            errors.append("Directory path is required")
        else:
            permissions = self.check_directory_permissions(directory.path)
            if not permissions["exists"] and not permissions["writable"]:
                errors.append(f"Directory does not exist and parent directory is not writable: {directory.path}")
            elif permissions["exists"] and not permissions["readable"]:
                errors.append(f"Directory is not readable: {directory.path}")

        if not directory.name:
            errors.append("Directory name is required")
        return errors

    def check_directory_permissions(self, path: str) -> dict[str, bool]:
        target = Path(path)
        exists = target.exists()
        readable = False
        writable = False
        if exists:
            readable = target.is_dir() and os.access(path, os.R_OK)
            writable = target.is_dir() and os.access(path, os.W_OK)
        else:
            parent = target.parent
            if parent.exists():
                writable = parent.is_dir() and os.access(str(parent), os.W_OK)
        return {"exists": exists, "readable": readable, "writable": writable}

    def create_directory_if_not_exists(self, path: str) -> None:
        if path:
            ensure_directory(path)

    def get_usage(self, directory_id: str) -> SettingsUsage:
        directory = self.get_by_id(directory_id)
        if directory is None:
            raise ConfigurationException("backendErrors.config.directoryNotFound", params={"id": directory_id})
        with SessionLocal() as session:
            task_count = session.execute(
                select(func.count())
                .select_from(TaskORM)
                .where(func.json_extract(TaskORM.context_json, "$.directory_id") == directory_id)
            ).scalar_one()
            subscription_count = session.execute(
                select(func.count())
                .select_from(MediaSubscriptionSettingsORM)
                .where(MediaSubscriptionSettingsORM.directory_id == directory_id)
            ).scalar_one()
        library_file_count = self._library_file_repo.count_by_directory_id_sync(directory_id)
        return SettingsUsage(
            task_count=int(task_count or 0),
            subscription_count=int(subscription_count or 0),
            directory_count=0,
            library_file_count=int(library_file_count or 0),
            is_default=bool(directory.is_default),
        )

    def _default_template_id_for(self, media_type: MediaType) -> str | None:
        config = AppConfig(naming_templates=self._naming_templates.list())
        if media_type == MediaType.movie:
            return self._naming_templates.resolve_default_id(config, "movie")
        if media_type == MediaType.tv:
            return self._naming_templates.resolve_default_id(config, "tv")
        return None

    def _apply_default_flag(
        self,
        directories: list[DirectoryConfig],
        directory: DirectoryConfig,
    ) -> list[DirectoryConfig]:
        if not directory.is_default:
            return directories
        return [
            item.model_copy(update={"is_default": False})
            if item.media_type == directory.media_type
            else item
            for item in directories
        ]
