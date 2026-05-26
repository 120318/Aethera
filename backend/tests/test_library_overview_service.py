import pytest

from app.schemas.domain.download import TaskEpisodeCoverage, TaskStatus
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.schedule import MediaScheduleSummary, ScheduleEpisode
from app.schemas.media_id import MediaID
from app.services.application.views.library.overview import OVERVIEW_ACTIVE_TASK_STATUSES, LibraryOverviewService
from app.services.domain.library.service import MediaLibrarySnapshot


def test_library_overview_active_task_statuses_include_migrating():
    assert TaskStatus.MIGRATING in OVERVIEW_ACTIVE_TASK_STATUSES


@pytest.mark.asyncio
async def test_build_snapshot_preserves_passed_media_schedule(monkeypatch):
    service = LibraryOverviewService()
    media_id = MediaID.parse("douban:tv:123")
    schedule = MediaScheduleSummary(
        media_type=MediaType.tv,
        next_episode_to_air=ScheduleEpisode(
            season_number=1,
            episode_number=3,
            air_date="2026-05-01",
            title="Episode 3",
        ),
    )
    media = MediaFullInfo(
        media_id=media_id,
        provider=media_id.provider,
        media_type=MediaType.tv,
        id=media_id.id,
        title="Example Show",
        year=2026,
        season_number=1,
        episodes_count=10,
        schedule=schedule,
    )

    async def fake_tasks_for_overview(status, media_id):
        return []

    monkeypatch.setattr(
        "app.services.application.views.library.overview.download_service.list_media_tasks_for_overview",
        fake_tasks_for_overview,
    )

    snapshot = await service.build_snapshot(
        media_id,
        media,
        library_snapshot=MediaLibrarySnapshot(files=[], present_episodes={1, 2}),
    )

    assert snapshot.schedule == schedule
    assert snapshot.next_episode_to_air is not None
    assert snapshot.next_episode_to_air.season_number == 1
    assert snapshot.next_episode_to_air.episode_number == 3
    assert snapshot.next_episode_to_air.air_date == "2026-05-01"


@pytest.mark.asyncio
async def test_build_snapshot_counts_movie_library_files_and_active_tasks(monkeypatch):
    service = LibraryOverviewService()
    media_id = MediaID.parse("douban:movie:456")
    media = MediaFullInfo(
        media_id=media_id,
        provider=media_id.provider,
        media_type=MediaType.movie,
        id=media_id.id,
        title="Example Movie",
        year=2026,
    )
    library_file = LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-1",
        media_id=media_id,
        path="/library",
        file_name="Example.Movie.2026.mkv",
        created_at=1,
    )
    task = type("Task", (), {"id": "task-2", "status": TaskStatus.DOWNLOADING})()

    async def fake_tasks_for_overview(status, media_id):
        assert TaskStatus.DOWNLOADING in status
        return [task]

    monkeypatch.setattr(
        "app.services.application.views.library.overview.download_service.list_media_tasks_for_overview",
        fake_tasks_for_overview,
    )
    monkeypatch.setattr(
        "app.services.application.views.library.overview.download_service.resolve_task_episode_coverage_detail",
        lambda task: TaskEpisodeCoverage(),
    )

    snapshot = await service.build_snapshot(
        media_id,
        media,
        library_snapshot=MediaLibrarySnapshot(files=[library_file], present_episodes=set()),
    )

    assert snapshot.library_file_count == 1
    assert snapshot.active_task_count == 1
    assert snapshot.collected_count == 1
    assert snapshot.downloading_count == 1


@pytest.mark.asyncio
async def test_build_snapshot_counts_original_disc_packages_without_episode_coverage(monkeypatch):
    service = LibraryOverviewService()
    media_id = MediaID.parse("douban:tv:123")
    media = MediaFullInfo(
        media_id=media_id,
        provider=media_id.provider,
        media_type=MediaType.tv,
        id=media_id.id,
        title="Example Show",
        year=2026,
        season_number=1,
        episodes_count=10,
    )
    attrs = ResourceAttributes(resource_form="BluRay Disc", package_layout="BDMV", disc_number=1, disc_total=2)
    library_files = [
        LibraryFile(
            id="file-index",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Shows/Example/Season 01/Disc 01/BDMV",
            file_name="index.bdmv",
            file_size=20,
            created_at=1,
            resource_attributes=attrs,
        ),
        LibraryFile(
            id="file-cert",
            task_id="task-1",
            directory_id="dir-1",
        media_id=media_id,
            path="Shows/Example/Season 01/Disc 01/CERTIFICATE",
            file_name="id.bdmv",
            file_size=10,
            created_at=1,
            resource_attributes=attrs,
        ),
    ]

    async def fake_tasks_for_overview(status, media_id):
        return []

    monkeypatch.setattr(
        "app.services.application.views.library.overview.download_service.list_media_tasks_for_overview",
        fake_tasks_for_overview,
    )

    snapshot = await service.build_snapshot(
        media_id,
        media,
        library_snapshot=MediaLibrarySnapshot(files=library_files, present_episodes=set()),
    )

    assert snapshot.library_file_count == 2
    assert snapshot.original_disc_package_count == 1
    assert snapshot.original_disc_file_count == 2
    assert snapshot.collected_count == 0
    assert snapshot.collected_episodes == []
