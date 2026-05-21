import pytest

from app.schemas.domain.library import LibraryFile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.media_id import MediaID
from app.services.domain.library.cleanup import LibraryCleanup
from app.services.domain.library.service import LibraryService


class FakeFileRepo:
    async def find_by_media_id(self, media_id):
        files = [
            LibraryFile(
                id="disc-file",
                task_id="task-1",
                directory_id="dir-1",
        media_id=MediaID.parse("tmdb:tv:100088"),
                path="tv-bluray/text (2023)/Season 01/THE_LAST_OF_US_S1_D1/BDMV",
                file_name="index.bdmv",
                file_size=10,
                created_at=1.0,
                resource_attributes=ResourceAttributes(
                    resource_form="BluRay Disc",
                    package_layout="BDMV",
                    seasons=[1],
                    episodes=[],
                ),
            ),
            LibraryFile(
                id="season-two-disc-file",
                task_id="task-2",
                directory_id="dir-1",
        media_id=MediaID.parse("tmdb:tv:100088"),
                path="tv-bluray/text (2023)/Season 02/Disc/BDMV",
                file_name="index.bdmv",
                file_size=10,
                created_at=1.0,
                resource_attributes=ResourceAttributes(
                    resource_form="BluRay Disc",
                    package_layout="BDMV",
                    seasons=[2],
                    episodes=[],
                ),
            ),
            LibraryFile(
                id="legacy-douban-file",
                task_id="task-3",
                directory_id="dir-1",
        media_id=MediaID.parse("douban:tv:25848328"),
                path="tv-bluray/text (2023)/Season 01/Legacy/BDMV",
                file_name="index.bdmv",
                file_size=10,
                created_at=1.0,
                resource_attributes=ResourceAttributes(
                    resource_form="BluRay Disc",
                    package_layout="BDMV",
                    seasons=[1],
                    episodes=[],
                ),
            ),
        ]
        return [file for file in files if file.media_id == media_id]

    async def find_by_ids(self, ids):
        return []


class FakeEpisodeRepo:
    async def find_by_media_and_season(self, media_id, season):
        return []


@pytest.mark.asyncio
async def test_get_files_by_media_uses_direct_media_id_for_tv_disc_packages_for_season():
    service = LibraryService(file_repo=FakeFileRepo(), episode_repo=FakeEpisodeRepo())

    files = await service.get_files_by_media(MediaID.parse("tmdb:tv:100088"), season=1)

    assert [file.id for file in files] == ["disc-file"]


def test_delete_files_removes_same_stem_nfo_sidecar(tmp_path):
    episode_file = tmp_path / "Show.S01E01.mkv"
    nfo_file = tmp_path / "Show.S01E01.nfo"
    danmu_xml_file = tmp_path / "Show.S01E01.danmu.xml"
    danmu_ass_file = tmp_path / "Show.S01E01.danmu.ass"
    other_episode_file = tmp_path / "Show.S01E02.mkv"
    episode_file.write_text("video")
    nfo_file.write_text("nfo")
    danmu_xml_file.write_text("xml")
    danmu_ass_file.write_text("ass")
    other_episode_file.write_text("video")
    cleanup = LibraryCleanup()

    cleanup.delete_files([
        LibraryFile(
            id="episode-file",
            task_id="task-1",
            directory_id="dir-1",
        media_id=MediaID.parse("tmdb:tv:100088"),
            path=str(tmp_path),
            file_name=episode_file.name,
            file_size=10,
            created_at=1.0,
            resource_attributes=ResourceAttributes(seasons=[1], episodes=[1]),
        )
    ])

    assert not episode_file.exists()
    assert not nfo_file.exists()
    assert not danmu_xml_file.exists()
    assert not danmu_ass_file.exists()
    assert other_episode_file.exists()
