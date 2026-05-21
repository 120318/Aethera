from __future__ import annotations

from sqlalchemy import func, select

from app.db.repositories.settings_sqlite_repository import SettingsSqliteRepository
from app.db.sql.models import TaskORM
from app.db.sql.session import SessionLocal
from app.schemas.config import DownloaderConfig
from app.schemas.exception import ConfigurationException
from app.schemas.runtime.settings_runtime import SettingsUsage


class DownloadClientSettings:
    def __init__(self, repo: SettingsSqliteRepository) -> None:
        self._repo = repo

    def list(self, enabled_only: bool = False) -> list[DownloaderConfig]:
        items = self._repo.downloaders.list()
        return [item for item in items if item.enabled] if enabled_only else items

    def replace_all(self, downloaders: list[DownloaderConfig]) -> None:
        self._repo.downloaders.replace(downloaders)

    def create(self, downloader: DownloaderConfig) -> DownloaderConfig:
        downloaders = self.list()
        if any(item.id == downloader.id for item in downloaders):
            raise ConfigurationException("backendErrors.config.downloaderIdExists", params={"id": downloader.id})
        downloaders.append(downloader)
        self.replace_all(downloaders)
        if self.get_default_id() is None and downloader.enabled:
            self.set_default(downloader.id)
        return downloader

    def update(self, downloader_id: str, downloader: DownloaderConfig) -> DownloaderConfig:
        downloaders = self.list()
        current_index = next((index for index, item in enumerate(downloaders) if item.id == downloader_id), -1)
        if current_index == -1:
            raise ConfigurationException("backendErrors.config.downloaderNotFound", params={"id": downloader_id})
        current = downloaders[current_index]
        if current.url != downloader.url:
            raise ConfigurationException("backendErrors.config.downloaderUrlImmutable")
        downloader.id = downloader_id
        downloaders[current_index] = downloader
        self.replace_all(downloaders)
        return downloader

    def delete(self, downloader_id: str) -> None:
        downloaders = self.list()
        next_downloaders = [item for item in downloaders if item.id != downloader_id]
        if len(next_downloaders) == len(downloaders):
            raise ConfigurationException("backendErrors.config.downloaderNotFound", params={"id": downloader_id})
        self.replace_all(next_downloaders)
        if self.get_default_id() == downloader_id:
            self.clear_default()

    def set_default(self, downloader_id: str) -> None:
        downloader = next((item for item in self.list() if item.id == downloader_id and item.enabled), None)
        if downloader is None:
            raise ConfigurationException("backendErrors.config.downloaderNotFoundOrDisabled", params={"id": downloader_id})
        self._repo.set_default("default_downloader_id", downloader_id)

    def clear_default(self) -> None:
        self._repo.set_default("default_downloader_id", None)

    def get_default_id(self) -> str | None:
        return self._repo.get_default("default_downloader_id")

    def validate_immutable_fields(self, next_downloaders: list[DownloaderConfig]) -> None:
        current_downloaders = {item.id: item for item in self.list()}
        for item in next_downloaders:
            current = current_downloaders.get(item.id)
            if current and current.url != item.url:
                raise ConfigurationException("backendErrors.config.downloaderUrlImmutable")

    def get_usage(self, downloader_id: str) -> SettingsUsage:
        if not any(item.id == downloader_id for item in self.list()):
            raise ConfigurationException("backendErrors.config.downloaderNotFound", params={"id": downloader_id})
        with SessionLocal() as session:
            task_count = session.execute(
                select(func.count()).select_from(TaskORM).where(TaskORM.downloader_id == downloader_id)
            ).scalar_one()
        return SettingsUsage(
            task_count=int(task_count or 0),
            subscription_count=0,
            directory_count=0,
            is_default=self.get_default_id() == downloader_id,
        )
