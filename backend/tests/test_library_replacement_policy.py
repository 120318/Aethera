from datetime import datetime

import pytest

from app.schemas.domain.download import TaskContext, TaskData, TaskStatus, TransferFileResult
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata
from app.schemas.exception.exceptions import TransferException
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


def _batch_result(index: int, episodes: list[int], resolution: str) -> TransferFileResult:
    episode_suffix = "E" + "E".join(f"{episode:02d}" for episode in episodes)
    filename = f"Test.S01{episode_suffix}.{resolution}.mkv"
    return TransferFileResult(
        source_path=f"/downloads/{filename}",
        destination_path=f"/library/{filename}",
        file_index=index,
        episode_number=episodes[0],
        episode_numbers=episodes,
        file_item=TorrentFileItem(
            index=index,
            filename=filename,
            size=2000,
            attrs=ResourceAttributes(seasons=[1], episodes=episodes, resolution=resolution),
        ),
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

    def file_is_intact(self, _library_file: LibraryFile) -> bool:
        return True

    def build_package_summaries(self, files: list[LibraryFile]):
        return self._package_service.build_package_summaries(files)

    def resolve_package_root(self, file: LibraryFile) -> str | None:
        return self._package_service.resolve_package_root(file)


@pytest.fixture(autouse=True)
def _quality_profile(monkeypatch):
    monkeypatch.setattr(library_replacement_policy, "_quality_profile", lambda: QualityProfile(name="Default"))


@pytest.mark.parametrize("single_resolution", ["720p", "2160p"])
def test_batch_winners_drop_combined_file_covered_by_equal_or_better_single_episodes(single_resolution):
    winners = library_replacement_policy.select_batch_winners([
        _batch_result(0, [1, 2], "720p"),
        _batch_result(1, [1], single_resolution),
        _batch_result(2, [2], single_resolution),
    ])

    assert [result.file_index for result in winners] == [1, 2]


def test_batch_winners_keep_combined_file_with_exclusive_episode():
    winners = library_replacement_policy.select_batch_winners([
        _batch_result(0, [1, 2], "720p"),
        _batch_result(1, [1], "2160p"),
    ])

    assert [result.file_index for result in winners] == [0, 1]


def test_batch_winners_reject_different_episodes_with_same_destination_path():
    episode_one = _batch_result(0, [1], "1080p")
    episode_two = _batch_result(1, [2], "2160p").model_copy(
        update={"destination_path": episode_one.destination_path},
    )

    with pytest.raises(TransferException, match="backendErrors.transferEpisodePathConflict") as exc_info:
        library_replacement_policy.select_batch_winners([episode_one, episode_two])

    assert exc_info.value.params == {"path": episode_one.destination_path}


def test_batch_winners_allow_equivalent_episodes_with_same_destination_path():
    lower = _batch_result(0, [1], "1080p")
    higher = _batch_result(1, [1], "2160p").model_copy(
        update={"destination_path": lower.destination_path},
    )

    winners = library_replacement_policy.select_batch_winners([lower, higher])

    assert [result.file_index for result in winners] == [1]


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
async def test_combined_video_replaces_only_lower_quality_single_episode_candidates(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    episode_one = _library_file(
        "episode-1",
        media_id=media_id,
        file_name="Test.S01E01.720p.mkv",
        attrs=ResourceAttributes(resolution="720p", seasons=[1], episodes=[1]),
    )
    episode_two = _library_file(
        "episode-2",
        media_id=media_id,
        file_name="Test.S01E02.2160p.mkv",
        attrs=ResourceAttributes(resolution="2160p", seasons=[1], episodes=[2]),
    )
    stub = _LibraryServiceStub(
        [episode_one, episode_two],
        [
            LibraryEpisode(media_id=media_id, season=1, episode=1, file_id="episode-1", created_at=0.0),
            LibraryEpisode(media_id=media_id, season=1, episode=2, file_id="episode-2", created_at=0.0),
        ],
    )
    monkeypatch.setattr("app.services.domain.transfer.replacement.library_service", stub)

    plan = await library_replacement_policy.build_plan(
        _task(media_id, season=1),
        [_batch_result(0, [1, 2], "1080p")],
        season=1,
    )

    assert [item.id for item in plan.replace_files] == ["episode-1"]


@pytest.mark.asyncio
async def test_same_episode_group_keeps_larger_equal_quality_combined_file(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    existing = _library_file(
        "combined",
        media_id=media_id,
        file_name="Test.S01E01E02.1080p.mkv",
        size=3000,
        attrs=ResourceAttributes(resolution="1080p", seasons=[1], episodes=[1, 2]),
    )
    stub = _LibraryServiceStub(
        [existing],
        [
            LibraryEpisode(media_id=media_id, season=1, episode=1, file_id="combined", created_at=0.0),
            LibraryEpisode(media_id=media_id, season=1, episode=2, file_id="combined", created_at=0.0),
        ],
    )
    monkeypatch.setattr("app.services.domain.transfer.replacement.library_service", stub)

    plan = await library_replacement_policy.build_plan(
        _task(media_id, season=1),
        [_batch_result(0, [1, 2], "1080p")],
        season=1,
    )

    assert plan.replace_files == []


@pytest.mark.asyncio
async def test_subtitle_does_not_replace_existing_episode_video(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    old_video = _library_file(
        "old-video",
        media_id=media_id,
        attrs=ResourceAttributes(resolution="720p", resource_form="Video File", seasons=[1], episodes=[1]),
    )
    stub = _LibraryServiceStub(
        [old_video],
        [LibraryEpisode(media_id=media_id, season=1, episode=1, file_id="old-video", created_at=0.0)],
    )
    monkeypatch.setattr("app.services.domain.transfer.replacement.library_service", stub)

    plan = await library_replacement_policy.build_plan(
        _task(media_id, season=1),
        [_transfer_result(
            filename="Test.S01E01.2160p.srt",
            attrs=ResourceAttributes(resolution="2160p", seasons=[1], episodes=[1]),
        )],
        season=1,
    )

    assert plan.replace_files == []


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
