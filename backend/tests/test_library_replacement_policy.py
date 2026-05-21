from datetime import datetime

import pytest

from app.schemas.domain.download import TaskContext, TaskData, TaskStatus, TransferFileResult
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata
from app.schemas.media_id import MediaID
from app.schemas.domain.library import LibraryEpisode, LibraryFile
from app.services.domain.library.service import LibraryService
from app.services.domain.transfer.replacement import library_replacement_policy


pytestmark = [pytest.mark.drift, pytest.mark.health]


def _task(media_id: MediaID, *, season: int | None = None) -> TaskData:
    return TaskData(
        id="task-new",
        torrent_hash="hash-new",
        media_id=media_id,
        status=TaskStatus.FINISHED,
        save_path="/downloads",
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            directory_id="dir-1",
            media={"media_id": media_id, "title": "Test", "year": 2024},
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata=TorrentMetadata(
            hash="hash-new",
            name="Test",
            size=100,
            attrs=ResourceAttributes(seasons=[season] if season else []),
            files=[],
        ),
    )


def _library_file(
    file_id: str,
    *,
    media_id: MediaID,
    task_id: str = "task-old",
    path: str = "Shows/Test/Season 01",
    file_name: str = "Test.S01E01.mkv",
    size: int = 1000,
    attrs: ResourceAttributes | None = None,
) -> LibraryFile:
    return LibraryFile(
        id=file_id,
        task_id=task_id,
        directory_id="dir-1",
        media_id=media_id,
        path=path,
        file_name=file_name,
        file_size=size,
        file_index=0,
        created_at=0.0,
        resource_attributes=attrs or ResourceAttributes(),
    )


def _transfer_result(
    *,
    filename: str = "Test.S01E01.mkv",
    size: int = 2000,
    episode_number: int | None = 1,
    attrs: ResourceAttributes | None = None,
) -> TransferFileResult:
    return TransferFileResult(
        source_path=f"/downloads/{filename}",
        destination_path=f"/library/{filename}",
        file_index=0,
        episode_number=episode_number,
        file_item=TorrentFileItem(index=0, filename=filename, size=size, attrs=attrs or ResourceAttributes()),
    )


class _LibraryServiceStub:
    def __init__(self, files: list[LibraryFile], episodes: list[LibraryEpisode] | None = None) -> None:
        self.files = files
        self.episodes = episodes or []
        self._package_service = LibraryService()

    async def get_files_by_media(self, media_id: MediaID, season: int | None = None) -> list[LibraryFile]:
        return [item for item in self.files if item.media_id == media_id]

    async def get_episodes_by_media(self, media_id: MediaID) -> list[LibraryEpisode]:
        return [item for item in self.episodes if item.media_id == media_id]

    def build_package_summaries(self, files: list[LibraryFile]):
        return self._package_service.build_package_summaries(files)

    def resolve_package_root(self, file: LibraryFile) -> str | None:
        return self._package_service.resolve_package_root(file)


@pytest.fixture(autouse=True)
def _quality_profile(monkeypatch):
    monkeypatch.setattr(library_replacement_policy, "_quality_profile", lambda: QualityProfile(name="Default"))


@pytest.mark.asyncio
async def test_video_file_replaces_only_same_episode_video_files(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    old_video = _library_file(
        "old-video",
        media_id=media_id,
        attrs=ResourceAttributes(resolution="1080p", resource_form="Video File", seasons=[1], episodes=[1]),
    )
    old_disc = _library_file(
        "old-disc",
        media_id=media_id,
        path="Shows/Test/Season 01/Test.S01.BluRay/BDMV",
        file_name="index.bdmv",
        attrs=ResourceAttributes(resolution="1080p", resource_form="BluRay Disc", package_layout="BDMV", seasons=[1]),
    )
    stub = _LibraryServiceStub(
        [old_video, old_disc],
        [LibraryEpisode(media_id=media_id, season=1, episode=1, file_id="old-video", created_at=0.0)],
    )
    monkeypatch.setattr("app.services.domain.transfer.replacement.library_service", stub)

    plan = await library_replacement_policy.build_plan(
        _task(media_id, season=1),
        [_transfer_result(attrs=ResourceAttributes(resolution="2160p", resource_form="Video File", seasons=[1], episodes=[1]))],
        season=1,
    )

    assert [item.id for item in plan.replace_files] == ["old-video"]


@pytest.mark.asyncio
async def test_original_disc_replaces_existing_original_disc_package_only_when_better(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    old_disc_file = _library_file(
        "old-disc-file",
        media_id=media_id,
        path="Movies/Test (2024)/Old.BluRay/BDMV",
        file_name="index.bdmv",
        size=1000,
        attrs=ResourceAttributes(resolution="1080p", resource_form="BluRay Disc", package_layout="BDMV"),
    )
    old_video = _library_file(
        "old-video",
        media_id=media_id,
        path="Movies/Test (2024)",
        file_name="Test.2024.1080p.mkv",
        size=1000,
        attrs=ResourceAttributes(resolution="1080p", resource_form="Video File"),
    )
    monkeypatch.setattr("app.services.domain.transfer.replacement.library_service", _LibraryServiceStub([old_disc_file, old_video]))

    plan = await library_replacement_policy.build_plan(
        _task(media_id),
        [
            _transfer_result(
                filename="New.BluRay/BDMV/index.bdmv",
                size=2000,
                episode_number=None,
                attrs=ResourceAttributes(resolution="2160p", resource_form="BluRay Disc", package_layout="BDMV"),
            )
        ],
        season=None,
    )

    assert [item.id for item in plan.replace_files] == ["old-disc-file"]


@pytest.mark.asyncio
async def test_original_disc_replaces_only_matching_disc_number(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    old_disc_one = _library_file(
        "old-disc-1",
        media_id=media_id,
        path="Shows/Test/Season 01/Old.Package/Disc 1/BDMV",
        file_name="index.bdmv",
        size=1000,
        attrs=ResourceAttributes(
            resolution="1080p",
            resource_form="BluRay Disc",
            package_layout="BDMV",
            seasons=[1],
            disc_number=1,
            disc_total=2,
        ),
    )
    old_disc_two = _library_file(
        "old-disc-2",
        media_id=media_id,
        path="Shows/Test/Season 01/Old.Package/Disc 2/BDMV",
        file_name="index.bdmv",
        size=1000,
        attrs=ResourceAttributes(
            resolution="1080p",
            resource_form="BluRay Disc",
            package_layout="BDMV",
            seasons=[1],
            disc_number=2,
            disc_total=2,
        ),
    )
    monkeypatch.setattr("app.services.domain.transfer.replacement.library_service", _LibraryServiceStub([old_disc_one, old_disc_two]))

    plan = await library_replacement_policy.build_plan(
        _task(media_id, season=1),
        [
            _transfer_result(
                filename="New.Package/Disc 2/BDMV/index.bdmv",
                size=3000,
                episode_number=None,
                attrs=ResourceAttributes(
                    resolution="2160p",
                    resource_form="BluRay Disc",
                    package_layout="BDMV",
                    seasons=[1],
                    disc_number=2,
                    disc_total=2,
                ),
            )
        ],
        season=1,
    )

    assert [item.id for item in plan.replace_files] == ["old-disc-2"]


@pytest.mark.asyncio
async def test_original_disc_absolute_destination_matches_relative_package_root(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    matching_disc = _library_file(
        "matching-disc",
        media_id=media_id,
        path="Movies/Test (2024)/New.BluRay/BDMV",
        file_name="index.bdmv",
        size=1000,
        attrs=ResourceAttributes(
            resolution="1080p",
            resource_form="BluRay Disc",
            package_layout="BDMV",
            disc_number=1,
        ),
    )
    other_disc_same_number = _library_file(
        "other-disc-same-number",
        media_id=media_id,
        path="Movies/Test (2024)/Other.BluRay/BDMV",
        file_name="index.bdmv",
        size=1000,
        attrs=ResourceAttributes(
            resolution="1080p",
            resource_form="BluRay Disc",
            package_layout="BDMV",
            disc_number=1,
        ),
    )
    monkeypatch.setattr("app.services.domain.transfer.replacement.library_service", _LibraryServiceStub([matching_disc, other_disc_same_number]))

    plan = await library_replacement_policy.build_plan(
        _task(media_id),
        [
            _transfer_result(
                filename="Movies/Test (2024)/New.BluRay/BDMV/index.bdmv",
                size=3000,
                episode_number=None,
                attrs=ResourceAttributes(
                    resolution="2160p",
                    resource_form="BluRay Disc",
                    package_layout="BDMV",
                    disc_number=1,
                ),
            )
        ],
        season=None,
    )

    assert [item.id for item in plan.replace_files] == ["matching-disc"]


@pytest.mark.asyncio
async def test_original_disc_keeps_existing_package_when_incoming_is_not_better(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    old_disc_file = _library_file(
        "old-disc-file",
        media_id=media_id,
        path="Movies/Test (2024)/Old.BluRay/BDMV",
        file_name="index.bdmv",
        size=2000,
        attrs=ResourceAttributes(resolution="2160p", resource_form="BluRay Disc", package_layout="BDMV"),
    )
    monkeypatch.setattr("app.services.domain.transfer.replacement.library_service", _LibraryServiceStub([old_disc_file]))

    plan = await library_replacement_policy.build_plan(
        _task(media_id),
        [
            _transfer_result(
                filename="New.BluRay/BDMV/index.bdmv",
                size=1000,
                episode_number=None,
                attrs=ResourceAttributes(resolution="1080p", resource_form="BluRay Disc", package_layout="BDMV"),
            )
        ],
        season=None,
    )

    assert plan.replace_files == []
