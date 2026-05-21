from app.schemas.domain.library import LibraryFile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.media_id import MediaID
from app.services.application.workflows.scoped_seasons import (
    library_file_season_number,
    library_files_for_season,
    library_files_season_numbers,
)


def _library_file(
    file_name: str,
    *,
    path: str = "tv/老友记 (1994)/Season 01",
    seasons: list[int] | None = None,
    episodes: list[int] | None = None,
) -> LibraryFile:
    return LibraryFile(
        id=file_name,
        task_id="task-1",
        directory_id="dir-1",
        media_id=MediaID.parse("tmdb:tv:1668"),
        path=path,
        file_name=file_name,
        file_size=10,
        created_at=1.0,
        resource_attributes=ResourceAttributes(
            seasons=seasons or [],
            episodes=episodes or [],
        ),
    )


def test_library_file_season_number_prefers_episode_filename_over_package_seasons():
    library_file = _library_file(
        "老友记 - S01E01.mkv",
        seasons=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        episodes=[1],
    )

    assert library_file_season_number(library_file) == 1


def test_library_files_for_season_does_not_include_files_from_other_season_dirs():
    season_one_file = _library_file(
        "老友记 - S01E01.mkv",
        seasons=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        episodes=[1],
    )
    season_ten_file = _library_file(
        "老友记 - S10E01.mkv",
        path="tv/老友记 (1994)/Season 10",
        seasons=[10],
        episodes=[1],
    )

    assert library_files_for_season([season_one_file, season_ten_file], 10) == [season_ten_file]


def test_library_files_season_numbers_uses_file_level_seasons():
    files = [
        _library_file(
            "老友记 - S01E01.mkv",
            seasons=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            episodes=[1],
        ),
        _library_file(
            "老友记 - S10E01.mkv",
            path="tv/老友记 (1994)/Season 10",
            seasons=[10],
            episodes=[1],
        ),
    ]

    assert library_files_season_numbers(files) == [1, 10]
