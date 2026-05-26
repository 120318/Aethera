from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.schemas.media_id import MediaID
from app.schemas.domain.download import TaskContext, TaskData, TaskStatus, TransferFileResult
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem
from app.schemas.exception.exceptions import TransferException
from app.services.domain.transfer import upgrade


def _task() -> TaskData:
    media_id = MediaID.parse("tmdb:movie:1")
    return TaskData(
        id="task-1",
        torrent_hash="hash-1",
        media_id=media_id,
        status=TaskStatus.FINISHED,
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            directory_id="dir-1",
            media={"media_id": media_id, "title": "Test Movie", "year": 2024},
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _existing_library_file(*, resolution: str | None, size: int = 1000) -> LibraryFile:
    return LibraryFile(
        id="file-1",
        task_id="task-old",
        directory_id="dir-1",
        media_id=MediaID.parse("tmdb:movie:1"),
        path="Movies/Test Movie (2024)",
        file_name="Test.Movie.2024.mkv",
        file_size=size,
        file_index=0,
        created_at=0.0,
        resource_attributes=ResourceAttributes(resolution=resolution),
    )


def _existing_retry_library_file(*, resolution: str | None, size: int = 1000) -> LibraryFile:
    return LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-1",
        media_id=MediaID.parse("tmdb:movie:1"),
        path="Movies/Test Movie (2024)",
        file_name="Test.Movie.2024.mkv",
        file_size=size,
        file_index=0,
        created_at=0.0,
        resource_attributes=ResourceAttributes(resolution=resolution),
    )


def _transfer_result(*, resolution: str | None, size: int = 1200) -> TransferFileResult:
    return TransferFileResult(
        source_path="/downloads/Test.Movie.2024.mkv",
        destination_path="/data/library/Movies/Test Movie (2024)/Test.Movie.2024.mkv",
        file_index=0,
        file_item=TorrentFileItem(
            index=0,
            filename="Test.Movie.2024.mkv",
            size=size,
            attrs=ResourceAttributes(resolution=resolution),
        ),
    )


@pytest.mark.asyncio
async def test_validate_transfer_upgrade_policy_allows_better_file(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.transfer.upgrade.library_service.find_file_by_path",
        AsyncMock(return_value=_existing_library_file(resolution="1080p")),
    )

    await upgrade.validate_transfer_upgrade_policy(
        _task(),
        [_transfer_result(resolution="2160p")],
    )


@pytest.mark.asyncio
async def test_validate_transfer_upgrade_policy_allows_idempotent_retry(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.transfer.upgrade.library_service.find_file_by_path",
        AsyncMock(return_value=_existing_retry_library_file(resolution="1080p", size=1200)),
    )

    await upgrade.validate_transfer_upgrade_policy(
        _task(),
        [_transfer_result(resolution="1080p", size=1200)],
    )


@pytest.mark.asyncio
async def test_validate_transfer_upgrade_policy_allows_same_task_retry_without_comparable_attrs(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.transfer.upgrade.library_service.find_file_by_path",
        AsyncMock(return_value=_existing_retry_library_file(resolution=None, size=1200)),
    )

    await upgrade.validate_transfer_upgrade_policy(
        _task(),
        [_transfer_result(resolution=None, size=1200)],
    )


@pytest.mark.asyncio
async def test_validate_transfer_upgrade_policy_allows_same_task_retry_when_only_incoming_has_attrs(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.transfer.upgrade.library_service.find_file_by_path",
        AsyncMock(return_value=_existing_retry_library_file(resolution=None, size=1200)),
    )

    await upgrade.validate_transfer_upgrade_policy(
        _task(),
        [_transfer_result(resolution="1080p", size=1200)],
    )


@pytest.mark.asyncio
async def test_validate_transfer_upgrade_policy_allows_same_task_retry_when_only_existing_has_attrs(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.transfer.upgrade.library_service.find_file_by_path",
        AsyncMock(return_value=_existing_retry_library_file(resolution="1080p", size=1200)),
    )

    await upgrade.validate_transfer_upgrade_policy(
        _task(),
        [_transfer_result(resolution=None, size=1200)],
    )


@pytest.mark.asyncio
async def test_validate_transfer_upgrade_policy_does_not_treat_other_task_collision_as_idempotent(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.transfer.upgrade.library_service.find_file_by_path",
        AsyncMock(return_value=_existing_library_file(resolution="1080p", size=1200)),
    )

    with pytest.raises(TransferException, match="backendErrors.transferFileUpgradeUnknown"):
        await upgrade.validate_transfer_upgrade_policy(
            _task(),
            [_transfer_result(resolution="1080p", size=1200)],
        )


@pytest.mark.asyncio
async def test_validate_transfer_upgrade_policy_rejects_not_better_file(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.transfer.upgrade.library_service.find_file_by_path",
        AsyncMock(return_value=_existing_library_file(resolution="2160p")),
    )

    with pytest.raises(TransferException, match="backendErrors.transferFileNotBetter"):
        await upgrade.validate_transfer_upgrade_policy(
            _task(),
            [_transfer_result(resolution="1080p")],
        )


@pytest.mark.asyncio
async def test_validate_transfer_upgrade_policy_rejects_unknown_file(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.transfer.upgrade.library_service.find_file_by_path",
        AsyncMock(return_value=_existing_library_file(resolution=None, size=1000)),
    )

    with pytest.raises(TransferException, match="backendErrors.transferFileUpgradeUnknown"):
        await upgrade.validate_transfer_upgrade_policy(
            _task(),
            [_transfer_result(resolution=None, size=1000)],
        )
