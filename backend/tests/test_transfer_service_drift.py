import os
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

pytestmark = [pytest.mark.drift, pytest.mark.health]

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.schemas.exception.exceptions import DownloadException, TransferException
from app.schemas.config import Template, TransferMode
from app.schemas.media_id import MediaID
from app.schemas.domain.download import TaskContext, TaskData, TaskStatus, TransferFileResult
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata
from app.services.domain.transfer import transfer_service
from app.services.domain.transfer.service import commit_transfer_results
from app.services.domain.transfer.execution import TransferExecutionContext, build_transfer_execution_context, build_transfer_plan, execute_transfer, generate_source_path


def _task(status: TaskStatus = TaskStatus.COMPLETED) -> TaskData:
    media_id = MediaID.parse("tmdb:tv:1")
    return TaskData(
        id="task-1",
        torrent_hash="hash-1",
        media_id=media_id,
        status=status,
        downloader_id="downloader-1",
        save_path="downloads/show",
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            directory_id="dir-1",
            media={"media_id": media_id, "title": "Test Show", "year": 2024},
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata=TorrentMetadata(
            hash="hash-1",
            name="Test.Show.S01.2024.1080p.WEB-DL",
            size=100,
            files=[
                TorrentFileItem(
                    index=0,
                    filename="Test.Show.S01E01.2024.1080p.WEB-DL.mkv",
                    size=100,
                )
            ],
        ),
    )


def _library_file(file_id: str = "file-1") -> LibraryFile:
    return LibraryFile(
        id=file_id,
        task_id="task-1",
        directory_id="dir-1",
        media_id=MediaID.parse("tmdb:tv:1"),
        path="TV/Test Show",
        file_name="Test.Show.S01E01.mkv",
        file_size=123,
        file_index=0,
        created_at=0.0,
    )


def _transfer_file_result() -> TransferFileResult:
    return TransferFileResult(
        source_path="/downloads/Test.Show.S01E01.2024.1080p.WEB-DL.mkv",
        destination_path="/library/TV/Test Show/Test.Show.S01E01.mkv",
        file_item=TorrentFileItem(
            index=0,
            filename="Test.Show.S01E01.2024.1080p.WEB-DL.mkv",
            size=100,
        ),
        file_index=0,
        episode_number=1,
        episode_numbers=[1],
    )


@pytest.mark.asyncio
async def test_perform_transfer_by_task_id_skips_when_library_is_complete_but_download_source_is_gone(monkeypatch):
    task = _task(status=TaskStatus.COMPLETED)
    monkeypatch.setattr("app.services.domain.transfer.execution.all_transfer_sources_available", AsyncMock(return_value=False))
    monkeypatch.setattr(
        "app.services.domain.transfer.service.download_service.find_task_by_id",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.service.library_service.get_files_by_task",
        AsyncMock(return_value=[_library_file()]),
    )
    monkeypatch.setattr("app.services.domain.transfer.execution.fs_provider.exists", lambda path: True)

    perform_mock = AsyncMock()
    monkeypatch.setattr(transfer_service, "_perform_transfer", perform_mock)

    result = await transfer_service.perform_transfer_by_task_id(task.id)

    assert result.transferred_files == []
    perform_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_commit_transfer_results_refreshes_tv_profile_with_execution_season(monkeypatch):
    task = _task(status=TaskStatus.TRANSFERRING)
    context = TransferExecutionContext(
        source_base_path=Path("/downloads"),
        destination_base_path=Path("/library"),
        title="Test Show",
        year=2024,
        season_number=2,
    )
    replace_mock = AsyncMock(return_value=[])
    update_state_mock = AsyncMock(return_value=True)
    refresh_mock = AsyncMock()
    completed_event_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.domain.transfer.service.library_service.replace_task_entries",
        replace_mock,
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.service.download_service.update_task_state",
        update_state_mock,
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.service.media_service.refresh_profile_safely",
        refresh_mock,
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.service.emit_media_import_completed",
        completed_event_mock,
    )

    await commit_transfer_results(
        task,
        [_transfer_file_result()],
        [],
        context,
    )

    refresh_mock.assert_awaited_once_with(task.media_id, 2)


@pytest.mark.asyncio
async def test_perform_transfer_by_task_id_rejects_when_library_record_exists_but_sources_are_missing(monkeypatch):
    task = _task(status=TaskStatus.COMPLETED)
    monkeypatch.setattr("app.services.domain.transfer.execution.all_transfer_sources_available", AsyncMock(return_value=False))
    monkeypatch.setattr(
        "app.services.domain.transfer.service.download_service.find_task_by_id",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.service.library_service.get_files_by_task",
        AsyncMock(return_value=[_library_file()]),
    )
    monkeypatch.setattr("app.services.domain.transfer.execution.fs_provider.exists", lambda path: False)

    with pytest.raises(TransferException, match="backendErrors.transferSourceFilesMissing"):
        await transfer_service.perform_transfer_by_task_id(task.id)


@pytest.mark.asyncio
async def test_build_transfer_execution_context_rejects_when_task_download_path_drift_is_detected(monkeypatch):
    task = _task(status=TaskStatus.FINISHED)
    monkeypatch.setattr(
        "app.services.domain.transfer.execution.download_service.ensure_task_download_path_consistent",
        AsyncMock(side_effect=DownloadException("path drift")),
    )

    with pytest.raises(TransferException, match="backendErrors.transferDownloadPathInconsistent"):
        await build_transfer_execution_context(task)


def test_generate_source_path_prefers_rooted_directory_for_directory_single_file(monkeypatch):
    task = _task()
    task.metadata = TorrentMetadata(
        hash="hash-1",
        name="Show.S01.2026.2160p.WEB-DL",
        size=100,
        files=[
            TorrentFileItem(
                index=0,
                filename="Show.S01E01.2026.2160p.WEB-DL.mkv",
                size=100,
            )
        ],
    )
    file_item = task.metadata.files[0]
    rooted_path = "/downloads/Show.S01.2026.2160p.WEB-DL/Show.S01E01.2026.2160p.WEB-DL.mkv"

    monkeypatch.setattr(
        "app.services.domain.transfer.execution.fs_provider.exists",
        lambda path: str(path) == rooted_path,
    )

    source_path = generate_source_path(task, file_item, Path("/downloads"))

    assert str(source_path) == rooted_path


def test_generate_source_path_prefers_plain_file_for_true_single_file(monkeypatch):
    task = _task()
    task.metadata = TorrentMetadata(
        hash="hash-1",
        name="Show.S01E01.2026.2160p.WEB-DL.mkv",
        size=100,
        files=[
            TorrentFileItem(
                index=0,
                filename="Show.S01E01.2026.2160p.WEB-DL.mkv",
                size=100,
            )
        ],
    )
    file_item = task.metadata.files[0]
    plain_path = "/downloads/Show.S01E01.2026.2160p.WEB-DL.mkv"

    monkeypatch.setattr(
        "app.services.domain.transfer.execution.fs_provider.exists",
        lambda path: str(path) == plain_path,
    )

    source_path = generate_source_path(task, file_item, Path("/downloads"))

    assert str(source_path) == plain_path


@pytest.mark.asyncio
async def test_execute_transfer_uses_copy_materializer_for_copy_mode(monkeypatch):
    class RecordingMaterializer:
        @property
        def mode(self):
            return TransferMode.COPY

        def materialize(self, source_path, destination_path):
            calls.append((source_path, destination_path))

    calls = []
    task = _task(status=TaskStatus.FINISHED)
    context = TransferExecutionContext(
        source_base_path=Path("/downloads"),
        destination_base_path=Path("/library"),
        transfer_mode=TransferMode.COPY,
        template_config=Template(
            dir_template="{title} ({year})/Season {season:00}",
            file_template="{title} - S{season:00}E{episode:00}",
        ),
        title="Test Show",
        year=2024,
        season_number=1,
    )
    monkeypatch.setattr("app.services.domain.transfer.execution.fs_provider.exists", lambda path: True)
    monkeypatch.setattr("app.services.domain.transfer.execution.validate_transfer_upgrade_policy", AsyncMock())

    def resolve_materializer(mode):
        assert mode == TransferMode.COPY
        return RecordingMaterializer()

    monkeypatch.setattr("app.services.domain.transfer.execution.transfer_materializer_registry.resolve", resolve_materializer)

    results = await execute_transfer(task, context)

    assert len(results) == 1
    assert calls == [(Path(results[0].source_path), Path(results[0].destination_path))]


def test_build_transfer_plan_preserves_bdmv_package_layout(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    task = TaskData(
        id="task-1",
        torrent_hash="hash-1",
        media_id=media_id,
        status=TaskStatus.FINISHED,
        save_path="downloads/movie",
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            directory_id="dir-1",
            media={"media_id": media_id, "title": "Test Movie", "year": 2024},
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata=TorrentMetadata(
            hash="hash-1",
            name="Test.Movie.2024.BluRay.Disc",
            size=100,
            attrs=ResourceAttributes(
                resource_form="BluRay Disc",
                package_layout="BDMV",
                disc_number=1,
                disc_total=2,
            ),
            files=[
                TorrentFileItem(index=0, filename="Test.Movie.2024.BluRay.Disc/BDMV/index.bdmv", size=10),
                TorrentFileItem(index=1, filename="Test.Movie.2024.BluRay.Disc/CERTIFICATE/id.bdmv", size=10),
            ],
        ),
    )
    monkeypatch.setattr("app.services.domain.transfer.execution.fs_provider.exists", lambda path: True)
    context = TransferExecutionContext(
        source_base_path=Path("/downloads"),
        destination_base_path=Path("/library"),
        template_config=Template(
            dir_template="{title} ({year})/{disc_package_name}",
            file_template="{title} ({year}){disc_suffix}",
        ),
        title="Test Movie",
        year=2024,
    )

    results = build_transfer_plan(task, context)

    assert [item.destination_path for item in results] == [
        "/library/Test Movie (2024)/Test.Movie.2024.BluRay.Disc/BDMV/index.bdmv",
        "/library/Test Movie (2024)/Test.Movie.2024.BluRay.Disc/CERTIFICATE/id.bdmv",
    ]
    assert all(item.episode_number is None for item in results)
    assert all(item.file_item.attrs.package_layout == "BDMV" for item in results)


def test_build_transfer_plan_names_tv_disc_iso_with_single_template(monkeypatch):
    task = _task(status=TaskStatus.FINISHED)
    task.metadata = TorrentMetadata(
        hash="hash-1",
        name="Test.Show.S01.Disc1.iso",
        size=100,
        attrs=ResourceAttributes(
            seasons=[1],
            episodes=[],
            resource_form="BluRay Disc",
            package_layout="ISO",
            disc_number=1,
            disc_total=2,
        ),
        files=[TorrentFileItem(index=0, filename="Test.Show.S01.Disc1.iso", size=100)],
    )
    monkeypatch.setattr("app.services.domain.transfer.execution.fs_provider.exists", lambda path: True)
    context = TransferExecutionContext(
        source_base_path=Path("/downloads"),
        destination_base_path=Path("/library"),
        template_config=Template(
            dir_template="{title} ({year})/Season {season:00}/{disc_package_name}",
            file_template="{title} - S{season:00}E{episode:00}{disc_suffix}",
        ),
        title="Test Show",
        year=2024,
        season_number=1,
    )

    results = build_transfer_plan(task, context)

    assert len(results) == 1
    assert results[0].destination_path == "/library/Test Show (2024)/Season 01/Test.Show.S01.Disc1/Test.Show.S01.Disc1.iso"
    assert results[0].episode_number is None


def test_build_transfer_plan_uses_context_episode_parsed_from_description(monkeypatch):
    task = _task(status=TaskStatus.FINISHED)
    task.context.parsed_attributes = ResourceAttributes(
        title="爱情没有神话.2160p.WEB-DL.H265",
        desc="爱情没有神话 第11集 | 类型：剧情 爱情",
        seasons=[1],
        episodes=[11],
    )
    task.metadata = TorrentMetadata(
        hash="hash-1",
        name="爱情没有神话.2160p.WEB-DL.H265",
        size=100,
        files=[
            TorrentFileItem(
                index=0,
                filename="爱情没有神话.2160p.WEB-DL.H265.mkv",
                size=100,
                attrs=ResourceAttributes(title="爱情没有神话.2160p.WEB-DL.H265", episodes=[]),
            )
        ],
    )
    monkeypatch.setattr("app.services.domain.transfer.execution.fs_provider.exists", lambda path: True)
    context = TransferExecutionContext(
        source_base_path=Path("/downloads"),
        destination_base_path=Path("/library"),
        template_config=Template(
            dir_template="{title} ({year})/Season {season:00}",
            file_template="{title} - S{season:00}E{episode:00}",
        ),
        title="爱情没有神话",
        year=2026,
        season_number=1,
    )

    results = build_transfer_plan(task, context)

    assert len(results) == 1
    assert results[0].episode_number == 11
    assert results[0].file_item.attrs.episodes == [11]
    assert results[0].destination_path == "/library/爱情没有神话 (2026)/Season 01/爱情没有神话 - S01E11.mkv"


def test_build_transfer_plan_names_multi_episode_file(monkeypatch):
    task = _task(status=TaskStatus.FINISHED)
    task.metadata = TorrentMetadata(
        hash="hash-1",
        name="Friends.S10E17E18.1080p.BluRay.Remux.AVC.AC3-WhaleHu",
        size=100,
        files=[
            TorrentFileItem(
                index=0,
                filename="Friends.S10E17E18.1080p.BluRay.Remux.AVC.AC3-WhaleHu.mkv",
                size=100,
                attrs=ResourceAttributes(
                    title="Friends.S10E17E18.1080p.BluRay.Remux.AVC.AC3-WhaleHu.mkv",
                    seasons=[10],
                    episodes=[17, 18],
                    resolution="1080p",
                ),
            )
        ],
    )
    monkeypatch.setattr("app.services.domain.transfer.execution.fs_provider.exists", lambda path: True)
    context = TransferExecutionContext(
        source_base_path=Path("/downloads"),
        destination_base_path=Path("/library"),
        template_config=Template(
            dir_template="{title} ({year})/Season {season:00}",
            file_template="{title} - S{season:00}E{episode:00}",
        ),
        title="Friends",
        year=1994,
        season_number=10,
    )

    results = build_transfer_plan(task, context)

    assert len(results) == 1
    assert results[0].episode_number == 17
    assert results[0].episode_numbers == [17, 18]
    assert results[0].file_item.attrs.episodes == [17, 18]
    assert results[0].destination_path == "/library/Friends (1994)/Season 10/Friends - S10E17E18.mkv"


def test_build_transfer_plan_attaches_context_attrs_when_file_attrs_missing(monkeypatch):
    task = _task(status=TaskStatus.FINISHED)
    task.context.parsed_attributes = ResourceAttributes(
        title="爱情没有神话.2160p.WEB-DL.H265",
        desc="爱情没有神话 第11集 | 类型：剧情 爱情",
        seasons=[1],
        episodes=[11],
    )
    task.metadata = TorrentMetadata(
        hash="hash-1",
        name="爱情没有神话.2160p.WEB-DL.H265",
        size=100,
        files=[
            TorrentFileItem(
                index=0,
                filename="爱情没有神话.2160p.WEB-DL.H265.mkv",
                size=100,
                attrs=None,
            )
        ],
    )
    monkeypatch.setattr("app.services.domain.transfer.execution.fs_provider.exists", lambda path: True)
    context = TransferExecutionContext(
        source_base_path=Path("/downloads"),
        destination_base_path=Path("/library"),
        template_config=Template(
            dir_template="{title} ({year})/Season {season:00}",
            file_template="{title} - S{season:00}E{episode:00}",
        ),
        title="爱情没有神话",
        year=2026,
        season_number=1,
    )

    results = build_transfer_plan(task, context)

    assert len(results) == 1
    assert results[0].episode_number == 11
    assert results[0].file_item.attrs.episodes == [11]
    assert results[0].destination_path == "/library/爱情没有神话 (2026)/Season 01/爱情没有神话 - S01E11.mkv"


def test_build_transfer_plan_backfills_description_technical_attrs(monkeypatch):
    task = _task(status=TaskStatus.FINISHED)
    task.context.parsed_attributes = ResourceAttributes(
        title="Show.S01E11.2160p.WEB-DL.H265",
        desc="HDR Format: Dolby Vision. Audio Codec: Dolby Atmos.",
        seasons=[1],
        episodes=[11],
        resolution="2160p",
        video_codec="HEVC",
        audio_codec="Dolby Atmos",
        hdr_type="Dolby Vision",
        subtitle="双语",
    )
    task.metadata = TorrentMetadata(
        hash="hash-1",
        name="Show.S01E11.2160p.WEB-DL.H265",
        size=100,
        files=[
            TorrentFileItem(
                index=0,
                filename="Show.S01E11.2160p.WEB-DL.H265.mkv",
                size=100,
                attrs=ResourceAttributes(
                    title="Show.S01E11.2160p.WEB-DL.H265.mkv",
                    seasons=[1],
                    episodes=[11],
                    resolution="2160p",
                    video_codec="HEVC",
                ),
            )
        ],
    )
    monkeypatch.setattr("app.services.domain.transfer.execution.fs_provider.exists", lambda path: True)
    context = TransferExecutionContext(
        source_base_path=Path("/downloads"),
        destination_base_path=Path("/library"),
        template_config=Template(
            dir_template="{title} ({year})/Season {season:00}",
            file_template="{title} - S{season:00}E{episode:00}",
        ),
        title="Test Show",
        year=2026,
        season_number=1,
    )

    results = build_transfer_plan(task, context)

    attrs = results[0].file_item.attrs
    assert attrs.audio_codec == "Dolby Atmos"
    assert attrs.hdr_type == "Dolby Vision"
    assert attrs.subtitle == "双语"
    assert attrs.video_codec == "HEVC"
