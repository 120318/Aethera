from __future__ import annotations

from app.schemas.config import DirectoryConfig
from app.schemas.runtime.directory_integrity import (
    DirectoryIntegrityCountSummary,
    DirectoryIntegrityDirectorySummary,
    DirectoryIntegrityIssueType,
    DirectoryIntegrityItem,
    DirectoryIntegritySummary,
)
from app.services.domain.directory_integrity.models import DirectorySizeIndex, DirectorySizeSummary


def build_directory_integrity_summary(
    items: list[DirectoryIntegrityItem],
    directories: list[DirectoryConfig] | None = None,
    directory_sizes: DirectorySizeIndex | None = None,
) -> DirectoryIntegritySummary:
    size_index = directory_sizes or DirectorySizeIndex()
    directory_summaries = [
        _build_directory_summary(directory, items, size_index.directories)
        for directory in directories or []
    ]
    counts = _build_count_summary(items)
    return DirectoryIntegritySummary(
        **counts.model_dump(),
        physical_size=size_index.global_summary.physical_size,
        logical_size=size_index.global_summary.logical_size,
        library_logical_size=size_index.global_summary.library_logical_size,
        download_logical_size=size_index.global_summary.download_logical_size,
        directories=directory_summaries,
    )


def build_directory_integrity_count_summary(items: list[DirectoryIntegrityItem]) -> DirectoryIntegrityCountSummary:
    return _build_count_summary(items)


def _build_directory_summary(
    directory: DirectoryConfig,
    items: list[DirectoryIntegrityItem],
    directory_sizes: dict[str, DirectorySizeSummary],
) -> DirectoryIntegrityDirectorySummary:
    directory_items = [item for item in items if item.directory_id == directory.id]
    counts = _build_count_summary(directory_items)
    sizes = directory_sizes[directory.id] if directory.id in directory_sizes else DirectorySizeSummary()
    return DirectoryIntegrityDirectorySummary(
        **counts.model_dump(),
        directory_id=directory.id,
        directory_name=directory.name,
        media_type=directory.media_type.value,
        physical_size=sizes.physical_size,
        logical_size=sizes.logical_size,
        library_logical_size=sizes.library_logical_size,
        download_logical_size=sizes.download_logical_size,
    )


def _build_count_summary(items: list[DirectoryIntegrityItem]) -> DirectoryIntegrityCountSummary:
    return DirectoryIntegrityCountSummary(
        total=len(items),
        repairable=sum(1 for item in items if item.repairable),
        unmanaged_library_files=sum(1 for item in items if item.issue_type == DirectoryIntegrityIssueType.unmanaged_library_file),
        missing_library_files=sum(1 for item in items if item.issue_type == DirectoryIntegrityIssueType.missing_library_file),
        tasks_missing_library_files=sum(1 for item in items if item.issue_type == DirectoryIntegrityIssueType.task_missing_library_file),
        library_files_missing_tasks=sum(1 for item in items if item.issue_type == DirectoryIntegrityIssueType.library_file_missing_task),
        unmanaged_download_entries=sum(1 for item in items if item.issue_type == DirectoryIntegrityIssueType.unmanaged_download_entry),
        missing_download_files=sum(1 for item in items if item.issue_type == DirectoryIntegrityIssueType.missing_download_file),
        missing_downloader_torrents=sum(1 for item in items if item.issue_type == DirectoryIntegrityIssueType.missing_downloader_torrent),
        unhealthy_downloader_torrents=sum(1 for item in items if item.issue_type == DirectoryIntegrityIssueType.unhealthy_downloader_torrent),
    )
