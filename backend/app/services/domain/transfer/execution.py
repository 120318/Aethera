from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.schemas.config import Template, TransferMode
from app.schemas.domain.download import TaskData, TaskStatus, TransferFileResult, TransferResult
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.torrent import TorrentFileItem
from app.schemas.exception import ConfigurationException
from app.schemas.exception.base import AppException
from app.schemas.exception.exceptions import TransferException
from app.services.domain.directory import directory_service
from app.services.domain.download import download_service
from app.services.domain.library.target_path_policy import library_target_path_policy
from app.utils.fs_utils import fs_provider
from app.utils.library_paths import build_download_path, build_library_file_path

from .materializers import transfer_materializer_registry
from .upgrade import validate_transfer_upgrade_policy


class TransferExecutionContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_base_path: Path
    destination_base_path: Path
    transfer_mode: TransferMode = TransferMode.HARDLINK
    template_config: Template | None = None
    media_info: MediaExecutionSnapshot | None = None
    title: str | None = None
    year: int | None = None
    selected_indices: set[int] | None = None
    season_number: int | None = None


def validate_transfer_task(task: TaskData) -> None:
    if not task.context:
        raise TransferException("backendErrors.transferTaskContextMissing", params={"task_id": task.id})
    if not task.metadata or not task.metadata.files:
        raise TransferException("backendErrors.transferTorrentMetadataMissing", params={"task_id": task.id})


async def validate_download_path_consistency(task: TaskData) -> None:
    try:
        await download_service.ensure_task_download_path_consistent(task)
    except AppException as exc:
        raise TransferException("backendErrors.transferDownloadPathInconsistent", params={"reason_key": exc.message_key}) from exc


def load_library_target(task: TaskData):
    try:
        return directory_service.resolve_library_target(task.context.directory_id)
    except ConfigurationException as exc:
        raise TransferException("backendErrors.transferLibraryTargetInvalid", params={"reason_key": exc.message_key}) from exc


def resolve_selected_indices(task: TaskData) -> set[int] | None:
    if not task.context or not task.context.selected_files:
        return None
    return set(task.context.selected_files)


def resolve_transfer_season_number(task: TaskData, media_info: MediaExecutionSnapshot | None) -> int | None:
    coverage = download_service.resolve_task_episode_coverage_detail(task)
    season_number = coverage.season_number
    if season_number is None and media_info and media_info.media_type == MediaType.tv:
        season_number = media_info.season_number
    if task.media_id.media_type == MediaType.tv and season_number is None:
        raise TransferException("backendErrors.transferSeasonMissing", params={"task_id": task.id})
    return season_number


def resolve_naming_identity(task: TaskData, media_info: MediaExecutionSnapshot | None) -> tuple[str | None, int | None]:
    if not media_info or not (media_info.title or "").strip():
        raise TransferException("backendErrors.transferMediaTitleMissing", params={"task_id": task.id})
    return media_info.title, media_info.year


async def resolve_media_snapshot(task: TaskData, template_config: Template | None) -> MediaExecutionSnapshot | None:
    if not task.context:
        raise TransferException("backendErrors.transferTaskContextMissing", params={"task_id": task.id})
    if not template_config or not (template_config.file_template or "").strip():
        raise TransferException("backendErrors.transferNamingTemplateMissing", params={"task_id": task.id})
    return task.context.media


async def build_transfer_execution_context(task: TaskData) -> TransferExecutionContext:
    validate_transfer_task(task)
    await validate_download_path_consistency(task)
    library_target = load_library_target(task)
    media_info = await resolve_media_snapshot(task, library_target.template)
    title, year = resolve_naming_identity(task, media_info)
    season_number = resolve_transfer_season_number(task, media_info)
    return TransferExecutionContext(
        source_base_path=await resolve_source_base_path(task),
        destination_base_path=Path(library_target.library_path),
        transfer_mode=library_target.transfer_mode,
        template_config=library_target.template,
        media_info=media_info,
        title=title,
        year=year,
        selected_indices=resolve_selected_indices(task),
        season_number=season_number,
    )


async def resolve_source_base_path(task: TaskData) -> Path:
    if task.save_path:
        return build_download_path(task.save_path)

    if not task.context:
        raise TransferException("backendErrors.transferTaskContextMissing", params={"task_id": task.id})
    try:
        download_target = directory_service.resolve_download_target(task.context.directory_id)
    except ConfigurationException as exc:
        raise TransferException("backendErrors.transferDownloadTargetInvalid", params={"reason_key": exc.message_key}) from exc
    return build_download_path(download_target.download_path)


def generate_source_path(task: TaskData, file_item: TorrentFileItem, source_base_path: Path) -> Path:
    relative = Path(file_item.filename)
    root_name = Path(task.metadata.name).name
    if task.metadata.uses_root_directory_for(file_item):
        if not root_name:
            raise TransferException("backendErrors.transferTorrentRootNameMissing", params={"task_id": task.id})
        source_path = source_base_path / relative if relative.parts and relative.parts[0] == root_name else source_base_path / root_name / relative
    else:
        source_path = source_base_path / relative

    if fs_provider.exists(source_path):
        return source_path
    raise TransferException(
        "backendErrors.transferSourceFileNotFound",
        params={"task_id": task.id, "filename": file_item.filename, "source_path": str(source_path)},
    )


def collect_present_library_files(library_files: list[LibraryFile]) -> list[LibraryFile]:
    return [library_file for library_file in library_files if fs_provider.exists(build_library_file_path(library_file.path, library_file.file_name))]


def should_skip_retransfer(
    task: TaskData,
    existing_library_files: list[LibraryFile],
    existing_present_files: list[LibraryFile],
    sources_available: bool,
) -> bool:
    return bool(
        existing_library_files
        and len(existing_present_files) == len(existing_library_files)
        and task.status in [TaskStatus.COMPLETED, TaskStatus.SEEDING_ABSENT]
        and not sources_available
    )


async def all_transfer_sources_available(task: TaskData) -> bool:
    if not task.metadata or not task.metadata.files:
        return False

    source_base_path = await resolve_source_base_path(task)
    found_any = False
    for _, file_item in iter_selected_files(task.metadata.files, task.context.selected_files if task.context else None):
        found_any = True
        try:
            source_path = generate_source_path(task, file_item, source_base_path)
            if not fs_provider.exists(source_path):
                return False
        except TransferException:
            return False
    return found_any


async def validate_transfer_reentry(task: TaskData, existing_library_files: list[LibraryFile]) -> TransferResult | None:
    if not existing_library_files:
        return None

    existing_present_files = collect_present_library_files(existing_library_files)
    sources_available = await all_transfer_sources_available(task)
    if should_skip_retransfer(task, existing_library_files, existing_present_files, sources_available):
        return TransferResult(transferred_files=[])
    if not sources_available:
        raise TransferException("backendErrors.transferSourceFilesMissing")
    return None


def iter_selected_files(files: list[TorrentFileItem], selected_indices):
    selected = set(selected_indices) if selected_indices else None
    for index, file_item in enumerate(files):
        if selected and index not in selected:
            continue
        yield index, file_item


def _is_original_disc_package(task: TaskData) -> bool:
    return bool(task.metadata and task.metadata.attrs and task.metadata.attrs.package_layout)


def _with_package_attrs(task: TaskData, file_item: TorrentFileItem) -> TorrentFileItem:
    if not task.metadata or not task.metadata.attrs:
        return _with_context_resource_attrs(task, file_item)
    return _with_context_resource_attrs(task, file_item.model_copy(update={"attrs": task.metadata.attrs}))


def _with_context_resource_attrs(task: TaskData, file_item: TorrentFileItem) -> TorrentFileItem:
    context_attrs = task.context.parsed_attributes if task.context and task.context.parsed_attributes else None
    if not context_attrs:
        return file_item
    if file_item.attrs is None:
        return file_item.model_copy(update={"attrs": context_attrs})
    attrs = file_item.attrs
    context_data = context_attrs.model_dump(mode="python")
    attrs_data = attrs.model_dump(mode="python")
    updates = {}
    for field in ("groups", "sources", "versions", "seasons", "episodes", "platforms"):
        context_value = context_data[field]
        if context_value and not attrs_data[field]:
            updates[field] = list(context_value)
    for field in (
        "desc",
        "resource_form",
        "resource_form_evidence",
        "package_layout",
        "disc_number",
        "disc_total",
        "resolution",
        "video_codec",
        "audio_codec",
        "hdr_type",
        "audio_channels",
        "color_depth",
        "content_type",
        "language",
        "subtitle",
        "tmdb_id",
        "imdb_id",
        "year",
        "release_year",
        "release_date",
        "first_air_date",
        "runtime",
        "episode_title",
    ):
        context_value = context_data[field]
        if context_value and not attrs_data[field]:
            updates[field] = context_value
    if not updates:
        return file_item
    return file_item.model_copy(update={"attrs": attrs.model_copy(update=updates)})


def _common_torrent_root(files: list[TorrentFileItem]) -> str | None:
    roots = [Path(file.filename).parts[0] for file in files if len(Path(file.filename).parts) > 1]
    if not roots or len(roots) != len(files):
        return None
    first = roots[0]
    if all(root == first for root in roots):
        return first
    return None


def _disc_package_name(task: TaskData, selected_files: list[tuple[int, TorrentFileItem]]) -> str:
    files = [file_item for _, file_item in selected_files]
    common_root = _common_torrent_root(files)
    if common_root:
        return common_root
    if task.metadata and task.metadata.name:
        metadata_name = Path(task.metadata.name).name
        if len(files) == 1 and Path(files[0].filename).suffix.lower() == ".iso":
            return Path(metadata_name).stem or metadata_name
        return metadata_name
    context_title = task.context.media.title if task.context and task.context.media else ""
    return context_title or task.id


def _disc_package_relative_path(package_name: str, file_item: TorrentFileItem) -> Path:
    relative = Path(file_item.filename)
    if relative.parts and relative.parts[0] == package_name:
        return Path(*relative.parts[1:])
    return relative


def _build_disc_package_transfer_plan(
    task: TaskData,
    execution_context: TransferExecutionContext,
) -> list[TransferFileResult]:
    transfer_results: list[TransferFileResult] = []
    package_attrs = task.metadata.attrs if task.metadata else None
    package_layout = str(package_attrs.package_layout) if package_attrs and package_attrs.package_layout else ""
    selected_files = list(iter_selected_files(task.metadata.files, execution_context.selected_indices))
    disc_package_name = _disc_package_name(task, selected_files)
    for index, original_file_item in selected_files:
        file_item = _with_package_attrs(task, original_file_item)
        source_path = generate_source_path(task, original_file_item, execution_context.source_base_path)
        destination_dir = library_target_path_policy.build_destination_dir(
            destination_base_path=execution_context.destination_base_path,
            template_config=execution_context.template_config,
            title=execution_context.title,
            year=execution_context.year,
            season_number=execution_context.season_number,
            file_item=file_item,
            disc_package_name=disc_package_name,
        )
        if package_layout == "ISO" and Path(original_file_item.filename).suffix.lower() == ".iso":
            destination_path = destination_dir / _disc_package_relative_path(disc_package_name, original_file_item)
        else:
            destination_path = destination_dir / _disc_package_relative_path(disc_package_name, original_file_item)
        transfer_results.append(
            TransferFileResult(
                source_path=str(source_path),
                destination_path=str(destination_path),
                file_item=file_item,
                file_index=index,
                episode_number=None,
                episode_numbers=[],
            )
        )
    return transfer_results


def build_transfer_plan(task: TaskData, execution_context: TransferExecutionContext) -> list[TransferFileResult]:
    if not task.metadata or not task.metadata.files:
        raise TransferException("backendErrors.transferTorrentMetadataMissing", params={"task_id": task.id})
    if _is_original_disc_package(task):
        return _build_disc_package_transfer_plan(task, execution_context)
    transfer_results: list[TransferFileResult] = []
    for index, original_file_item in iter_selected_files(task.metadata.files, execution_context.selected_indices):
        file_item = _with_context_resource_attrs(task, original_file_item)
        source_path = generate_source_path(task, file_item, execution_context.source_base_path)
        destination_path = library_target_path_policy.build_destination_path(
            destination_base_path=execution_context.destination_base_path,
            template_config=execution_context.template_config,
            title=execution_context.title,
            year=execution_context.year,
            season_number=execution_context.season_number,
            file_item=file_item,
        )
        episode_numbers = library_target_path_policy.extract_episode_numbers(file_item, season_number=execution_context.season_number)
        transfer_results.append(
            TransferFileResult(
                source_path=str(source_path),
                destination_path=str(destination_path),
                file_item=file_item,
                file_index=index,
                episode_number=episode_numbers[0] if episode_numbers else None,
                episode_numbers=episode_numbers,
            )
        )
    return transfer_results


async def execute_transfer(task: TaskData, execution_context: TransferExecutionContext) -> list[TransferFileResult]:
    transfer_results = build_transfer_plan(task, execution_context)
    await validate_transfer_upgrade_policy(task, transfer_results)
    materializer = transfer_materializer_registry.resolve(execution_context.transfer_mode)
    for transfer_result in transfer_results:
        source_path = Path(transfer_result.source_path)
        destination_path = Path(transfer_result.destination_path)
        try:
            await asyncio.to_thread(materializer.materialize, source_path, destination_path)
        except (TransferException, OSError):
            raise
    return transfer_results
