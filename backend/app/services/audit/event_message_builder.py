from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.schemas.domain.download import TaskData, TransferFileResult
from app.schemas.domain.media import MediaIdentity
from app.schemas.domain.media_subscription_state import SubscriptionEndReason


def _join_details(details: list[str]) -> str:
    normalized = [item.strip() for item in details if item and item.strip()]
    if not normalized:
        return ""
    return f" ({', '.join(normalized)})"


def _display_name(value: str | None, fallback: str) -> str:
    normalized = (value or "").strip()
    return normalized or fallback


def _format_hash_prefix(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    return normalized[:8]


def _format_file_selection(selected_files: list[int] | None, total_files: int | None) -> str | None:
    if total_files is not None and total_files <= 0:
        total_files = None
    if not selected_files:
        if total_files and total_files > 1:
            return f"all {total_files} files selected"
        return None
    selected_count = len(selected_files)
    if total_files and total_files > 0:
        return f"{selected_count}/{total_files} files selected"
    return f"{selected_count} files selected"


def _format_episode_summary(episodes: Iterable[int | None]) -> str | None:
    normalized = sorted({int(item) for item in episodes if item and int(item) > 0})
    if not normalized:
        return None
    if len(normalized) == 1:
        return f"episode {normalized[0]} covered"

    ranges: list[tuple[int, int]] = []
    start = normalized[0]
    end = normalized[0]
    for value in normalized[1:]:
        if value == end + 1:
            end = value
            continue
        ranges.append((start, end))
        start = value
        end = value
    ranges.append((start, end))

    parts: list[str] = []
    for start, end in ranges:
        if start == end:
            parts.append(str(start))
        else:
            parts.append(f"{start}-{end}")
    return f"episodes {', '.join(parts)} covered"


def _format_path_name(path: str | None) -> str | None:
    normalized = (path or "").strip()
    if not normalized:
        return None
    return Path(normalized).name or normalized


def build_download_started_message(task: TaskData, downloader_name: str | None = None) -> str:
    title = _display_name(task.context.resource_title, task.context.media.title)
    total_files = len(task.metadata.files) if task.metadata and task.metadata.files else None
    hash_prefix = _format_hash_prefix(task.torrent_hash)
    details = [
        f"site {task.context.indexer}" if task.context.indexer else "",
        f"downloader {downloader_name}" if downloader_name else "",
        _format_file_selection(task.context.selected_files, total_files),
        f"hash {hash_prefix}" if hash_prefix else "",
    ]
    return f'Download started for "{title}"{_join_details(details)}'


def build_download_completed_message(task: TaskData, downloader_name: str | None = None) -> str:
    title = _display_name(
        task.context.resource_title,
        (task.metadata.name if task.metadata else None) or task.context.media.title,
    )
    total_files = len(task.metadata.files) if task.metadata and task.metadata.files else None
    hash_prefix = _format_hash_prefix(task.torrent_hash)
    details = [
        f"downloader {downloader_name}" if downloader_name else "",
        _format_file_selection(task.context.selected_files, total_files),
        f"hash {hash_prefix}" if hash_prefix else "",
    ]
    return f'Download completed for "{title}"{_join_details(details)}'


def build_download_failed_message(title: str, reason: str | None = None) -> str:
    display_title = _display_name(title, "Unknown media")
    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        return f'Failed to create download task for "{display_title}"'
    return f'Failed to create download task for "{display_title}" ({normalized_reason})'


def build_media_import_completed_message(task: TaskData, transfer_results: list[TransferFileResult]) -> str:
    count = len(transfer_results)
    first_target = _format_path_name(transfer_results[0].destination_path) if transfer_results else None
    episode_summary = _format_episode_summary(
        episode for item in transfer_results for episode in (item.episode_numbers or ([item.episode_number] if item.episode_number else []))
    )
    details = [
        f"{count} files imported" if count > 0 else "",
        episode_summary,
        f"first file {first_target}" if first_target else "",
    ]
    return f"Import completed{_join_details(details)}"


def build_media_deleted_message(
    media: MediaIdentity,
    paths: list[str],
    *,
    delete_scope: str,
    media_root_dir: str | None = None,
) -> str:
    count = len(paths)
    first_target = _format_path_name(paths[0]) if paths else None
    scope_map = {
        "file": "file",
        "library": "library",
        "tasks_and_library": "tasks and library",
    }
    scope_label = scope_map[delete_scope] if delete_scope in scope_map else delete_scope
    details = [
        f"scope {scope_label}" if scope_label else "",
        f"{count} paths deleted" if count > 0 else "",
        f"first target {first_target}" if first_target else "",
        f"media root {_format_path_name(media_root_dir)}" if media_root_dir else "",
    ]
    return f"Resource deleted{_join_details(details)}"


def build_follow_released_message(media: MediaIdentity, air_date: str | None) -> str:
    details = [f"date {air_date}" if air_date else ""]
    action = "Released" if media.media_id.media_type.value == "movie" else "Premiered"
    return f"{action}{_join_details(details)}"


def build_follow_digital_released_message(media: MediaIdentity, air_date: str | None) -> str:
    details = [f"date {air_date}" if air_date else ""]
    return f"Digital release is available{_join_details(details)}"


def build_follow_physical_released_message(media: MediaIdentity, air_date: str | None) -> str:
    details = [f"date {air_date}" if air_date else ""]
    return f"Physical release is available{_join_details(details)}"


def build_subscription_run_completed_message(*, checked: int, added: int) -> str:
    return f"Subscription check completed ({checked} candidates matched, {added} download tasks created)"


def build_subscription_run_failed_message(reason: str) -> str:
    normalized = reason.strip()
    if not normalized:
        return "Subscription run failed"
    if normalized.startswith("Subscription run failed"):
        return normalized
    return f"Subscription run failed: {normalized}"


def build_pilot_episode_queued_message(
    media: MediaIdentity,
    *,
    directory_id: str,
    sites: list[str] | None = None,
) -> str:
    details = [
        f"directory {directory_id}" if directory_id else "",
        f"{len(sites)} sites" if sites else "default sites",
    ]
    action_label = "download task" if media.media_id.media_type.value == "movie" else "pilot task"
    return f"{action_label.capitalize()} submitted{_join_details(details)}"


def build_subscription_enabled_message(media: MediaIdentity) -> str:
    return "Subscription auto-download enabled"


def build_subscription_disabled_message(media: MediaIdentity) -> str:
    return "Subscription auto-download disabled"


def build_follow_enabled_message(media: MediaIdentity) -> str:
    return "Follow reminder enabled"


def build_follow_disabled_message(media: MediaIdentity) -> str:
    return "Follow reminder disabled"


def build_subscription_ended_message(reason: SubscriptionEndReason) -> str:
    if reason == SubscriptionEndReason.MANUAL:
        return "Current subscription ended"
    if reason == SubscriptionEndReason.MOVIE_LIBRARY_COMPLETED:
        return "Current subscription ended (movie already imported)"
    if reason == SubscriptionEndReason.MOVIE_DOWNLOADING_COMPLETED:
        return "Current subscription ended (movie already has a download task)"
    if reason == SubscriptionEndReason.MOVIE_TARGET_COMPLETED:
        return "Current subscription ended (movie reached target version)"
    if reason == SubscriptionEndReason.TV_COMPLETED:
        return "Current subscription ended (all episodes covered)"
    if reason == SubscriptionEndReason.TV_UPGRADE_COMPLETED:
        return "Current subscription ended (current upgrade cycle completed)"
    if reason == SubscriptionEndReason.TV_TARGET_COMPLETED:
        return "Current subscription ended (aired episodes reached target version)"
    return "Current subscription ended"
