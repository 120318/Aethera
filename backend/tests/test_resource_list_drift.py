import os
import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

pytestmark = [pytest.mark.drift, pytest.mark.health]

from app.api.v1.resource.list import list_resources
from app.schemas.runtime.resource_list import EpisodeStatus, resolve_episode_status
from app.schemas.media_id import MediaID
from app.schemas.domain.download import TaskContext, TaskData, TaskEpisodeCoverage, TaskStatus
from app.schemas.domain.library import LibraryEpisode, LibraryFile
from app.schemas.domain.media import MediaSimpleInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.exception import InvalidRequestException


def _task(status: TaskStatus, *, task_id: str = "task-1") -> TaskData:
    media_id = MediaID.parse("tmdb:tv:1")
    return TaskData(
        id=task_id,
        torrent_hash=f"hash-{task_id}",
        media_id=media_id,
        status=status,
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            directory_id="dir-1",
            media={"media_id": media_id, "title": "Test Show", "year": 2024},
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def test_resolve_episode_status_treats_seeding_absent_as_completed_when_library_episode_exists():
    task = _task(TaskStatus.SEEDING_ABSENT)

    status = resolve_episode_status(
        task,
        season_num=1,
        episode_num=2,
        existing_episode_keys={(1, 2)},
        media_has_primary_library_files=False,
    )

    assert status == EpisodeStatus.completed


def test_resolve_episode_status_treats_partial_missing_as_error_when_library_episode_is_gone():
    task = _task(TaskStatus.PARTIAL_MISSING)

    status = resolve_episode_status(
        task,
        season_num=1,
        episode_num=2,
        existing_episode_keys=set(),
        media_has_primary_library_files=False,
    )

    assert status == EpisodeStatus.error


@pytest.mark.asyncio
async def test_list_resources_reflects_seeding_absent_episode_as_completed(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    task = _task(TaskStatus.SEEDING_ABSENT)
    library_file = LibraryFile(
        id="file-1",
        task_id=task.id,
        directory_id="dir-1",
        media_id=media_id,
        path="TV/Test Show",
        file_name="Test.Show.S01E02.mkv",
        file_size=100,
        file_index=0,
        created_at=0.0,
    )
    library_episode = LibraryEpisode(
        media_id=media_id,
        season=1,
        episode=2,
        file_id="file-1",
        created_at=0.0,
    )
    monkeypatch.setattr("app.services.application.views.resource_status.service.download_service.get_tasks", AsyncMock(return_value=[task]))
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.get_episodes_by_media",
        AsyncMock(return_value=[library_episode]),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.get_files_by_media",
        AsyncMock(return_value=[library_file]),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.file_exists",
        lambda library_file: True,
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.is_primary_file",
        lambda library_file: True,
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.build_file_exists_map",
        lambda library_files: {library_file.id: True for library_file in library_files},
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.media_service.simple_info",
        AsyncMock(
            return_value=MediaSimpleInfo(
                media_id=media_id,
                title="Test Show",
                year=2024,
                media_type=MediaType.tv,
                season_number=1,
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.download_service.resolve_task_episode_coverage_detail",
        lambda task: TaskEpisodeCoverage(season_number=1, episode_numbers=[2]),
    )

    response = await list_resources(media_id, season_number=1)

    assert response.seasons[0].episodes[0].status == EpisodeStatus.completed


@pytest.mark.asyncio
async def test_list_resources_requires_tv_season_number():
    media_id = MediaID.parse("tmdb:tv:1")

    with pytest.raises(InvalidRequestException) as exc_info:
        await list_resources(media_id)

    assert exc_info.value.message_key == "backendErrors.seasonRequired"


@pytest.mark.asyncio
async def test_list_resources_filters_tasks_by_requested_tv_season(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    season_one_task = _task(TaskStatus.DOWNLOADING, task_id="task-s1")
    season_two_task = _task(TaskStatus.DOWNLOADING, task_id="task-s2")
    coverage = {
        season_one_task.id: (1, [1]),
        season_two_task.id: (2, [1]),
    }
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.download_service.get_tasks",
        AsyncMock(return_value=[season_one_task, season_two_task]),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.get_episodes_by_media",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.get_files_by_media",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.build_file_exists_map",
        lambda library_files: {},
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.media_service.simple_info",
        AsyncMock(
            return_value=MediaSimpleInfo(
                media_id=media_id,
                title="Test Show",
                year=2024,
                media_type=MediaType.tv,
                season_number=2,
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.download_service.resolve_task_episode_coverage_detail",
        lambda task: TaskEpisodeCoverage(season_number=coverage[task.id][0], episode_numbers=coverage[task.id][1]),
    )

    response = await list_resources(media_id, season_number=2)

    assert [task.id for task in response.tasks] == ["task-s2"]
    assert [season.season for season in response.seasons] == [2]


@pytest.mark.asyncio
async def test_list_resources_filters_tasks_by_media_context_season_when_parser_has_no_season(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    season_one_task = _task(TaskStatus.DOWNLOADING, task_id="task-s1")
    season_two_task = _task(TaskStatus.DOWNLOADING, task_id="task-s2")
    season_one_task.context.media = season_one_task.context.media.model_copy(update={"season_number": 1})
    season_two_task.context.media = season_two_task.context.media.model_copy(update={"season_number": 2})
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.download_service.get_tasks",
        AsyncMock(return_value=[season_one_task, season_two_task]),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.get_episodes_by_media",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.get_files_by_media",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.build_file_exists_map",
        lambda library_files: {},
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.media_service.simple_info",
        AsyncMock(
            return_value=MediaSimpleInfo(
                media_id=media_id,
                title="Test Show",
                year=2024,
                media_type=MediaType.tv,
                season_number=2,
            )
        ),
    )

    response = await list_resources(media_id, season_number=2)

    assert [task.id for task in response.tasks] == ["task-s2"]


@pytest.mark.asyncio
async def test_list_resources_filters_with_parser_season_before_context_season(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    task = _task(TaskStatus.DOWNLOADING, task_id="task-conflict")
    task.context.media = task.context.media.model_copy(update={"season_number": 1})
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.download_service.get_tasks",
        AsyncMock(return_value=[task]),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.get_episodes_by_media",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.get_files_by_media",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.library_service.build_file_exists_map",
        lambda library_files: {},
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.media_service.simple_info",
        AsyncMock(
            return_value=MediaSimpleInfo(
                media_id=media_id,
                title="Test Show",
                year=2024,
                media_type=MediaType.tv,
                season_number=2,
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_status.service.download_service.resolve_task_episode_coverage_detail",
        lambda _task: TaskEpisodeCoverage(season_number=2, episode_numbers=[1]),
    )

    response = await list_resources(media_id, season_number=2)

    assert [task.id for task in response.tasks] == ["task-conflict"]
    assert [season.season for season in response.seasons] == [2]
