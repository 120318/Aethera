from __future__ import annotations

from pathlib import Path

from app.schemas.exception import ConfigurationException
from app.schemas.config import TransferMode
from app.schemas.runtime.settings_runtime import (
    DirectoryDownloadBinding,
    DirectoryDownloadTarget,
    DirectoryLibraryTarget,
)
from app.services.config.settings_service import settings_service
from app.services.domain.transfer.materializers import transfer_materializer_registry


class DirectoryService:
    def get_download_binding(self, directory_id: str) -> DirectoryDownloadBinding | None:
        directory = settings_service.get_directory_by_id(directory_id)
        if not directory:
            return None
        return DirectoryDownloadBinding(
            directory_id=directory.id,
            downloader_id=directory.downloader_id,
            download_path=(directory.download_path or "").strip() or None,
            download_category=directory.download_category,
        )

    def resolve_download_target(self, directory_id: str) -> DirectoryDownloadTarget:
        binding = self.get_download_binding(directory_id)
        if not binding:
            raise ConfigurationException("backendErrors.config.directoryNotFound", params={"id": directory_id})
        if not binding.downloader_id:
            raise ConfigurationException("backendErrors.config.directoryDownloaderBindingRequired", params={"id": directory_id})
        if not binding.download_path:
            raise ConfigurationException("backendErrors.config.directoryDownloadPathRequired", params={"id": directory_id})
        return DirectoryDownloadTarget(
            directory_id=binding.directory_id,
            downloader_id=binding.downloader_id,
            download_path=binding.download_path,
            download_category=binding.download_category,
        )

    def resolve_library_target(self, directory_id: str) -> DirectoryLibraryTarget:
        directory = settings_service.get_directory_by_id(directory_id)
        if not directory:
            raise ConfigurationException("backendErrors.config.directoryNotFound", params={"id": directory_id})
        library_path = (directory.path or "").strip()
        if not library_path:
            raise ConfigurationException("backendErrors.config.directoryLibraryPathRequired", params={"id": directory_id})
        template = settings_service.get_template_by_directory_id(directory_id)
        if not template or not (template.file_template or "").strip():
            raise ConfigurationException("backendErrors.config.directoryNamingTemplateRequired", params={"id": directory_id})
        transfer_mode = directory.transfer_mode or TransferMode.HARDLINK
        if not transfer_materializer_registry.supports(transfer_mode):
            raise ConfigurationException(
                "backendErrors.config.directoryTransferModeUnsupported",
                params={"id": directory_id, "mode": str(transfer_mode)},
            )
        return DirectoryLibraryTarget(
            directory_id=directory.id,
            media_type=directory.media_type,
            library_path=library_path,
            template=template,
            transfer_mode=transfer_mode,
        )

    def validate_subscription_directory(self, directory_id: str | None) -> None:
        if not directory_id:
            raise ConfigurationException("backendErrors.config.directoryIdRequired")
        self.resolve_download_target(directory_id)
        self.resolve_library_target(directory_id)

    def list_library_cleanup_roots(self) -> list[Path]:
        roots: set[Path] = set()
        for directory in settings_service.list_directories():
            path = (directory.path or "").strip()
            if not path:
                continue
            roots.add(Path(path).resolve(strict=False))
        return sorted(roots, key=lambda path: len(path.parts), reverse=True)


directory_service = DirectoryService()
