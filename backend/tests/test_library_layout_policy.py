from pathlib import Path

from app.schemas.media_id import MediaID
from app.schemas.domain.library import LibraryMediaLayout, LibraryMediaLayoutEntry
from app.schemas.domain.library_layout import LibraryLayoutTargetFile
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_types import MediaType
from app.services.domain.library.media_root_policy import library_media_root_policy
from app.services.domain.library.target_path_policy import library_target_path_policy
from app.schemas.config import Template
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem


def _media(media_type: MediaType, title: str) -> MediaFullInfo:
    return MediaFullInfo(
        media_id=MediaID.parse(f"tmdb:{media_type.value}:1"),
        title=title,
        year=2024,
        media_type=media_type,
    )


def test_library_layout_policy_infers_movie_root_from_target_files(tmp_path: Path):
    movie_dir = tmp_path / "Movies" / "Test Movie (2024)"
    movie_dir.mkdir(parents=True)
    movie_file = movie_dir / "Test.Movie.2024.2160p.mkv"
    movie_file.write_text("x", encoding="utf-8")

    decision = library_media_root_policy.build_from_target_files(
        _media(MediaType.movie, "Test Movie"),
        [LibraryLayoutTargetFile(destination_path=str(movie_file))],
        anchor_file=str(movie_file),
    )

    assert decision is not None
    assert decision.anchor_file == str(movie_file)
    assert decision.media_root_dir == str(movie_dir)
    assert decision.updated_paths == [str(movie_dir)]


def test_library_layout_policy_infers_show_root_above_season_dir(tmp_path: Path):
    show_dir = tmp_path / "TV" / "Test Show"
    season_dir = show_dir / "Season 01"
    season_dir.mkdir(parents=True)
    episode_file = season_dir / "Test.Show.S01E01.mkv"
    episode_file.write_text("x", encoding="utf-8")

    decision = library_media_root_policy.build_from_target_files(
        _media(MediaType.tv, "Test Show"),
        [LibraryLayoutTargetFile(destination_path=str(episode_file), episode_number=1)],
        anchor_file=str(episode_file),
    )

    assert decision is not None
    assert decision.media_root_dir == str(show_dir)
    assert decision.updated_paths == [str(show_dir)]


def test_library_layout_policy_infers_show_root_above_season_dir_when_sibling_seasons_exist(tmp_path: Path):
    show_dir = tmp_path / "TV" / "Test Show"
    season_dir = show_dir / "Season 01"
    season_dir.mkdir(parents=True)
    sibling_season_dir = show_dir / "Season 02"
    sibling_season_dir.mkdir(parents=True)
    episode_file = season_dir / "Test.Show.S01E01.mkv"
    sibling_episode_file = sibling_season_dir / "Test.Show.S02E01.mkv"
    episode_file.write_text("x", encoding="utf-8")
    sibling_episode_file.write_text("x", encoding="utf-8")

    decision = library_media_root_policy.build_from_target_files(
        _media(MediaType.tv, "Test Show"),
        [LibraryLayoutTargetFile(destination_path=str(episode_file), episode_number=1)],
        anchor_file=str(episode_file),
    )

    assert decision is not None
    assert decision.media_root_dir == str(show_dir)
    assert decision.updated_paths == [str(show_dir)]


def test_library_layout_policy_keeps_tv_target_files_without_episode_numbers(tmp_path: Path):
    show_dir = tmp_path / "TV" / "Test Show"
    season_dir = show_dir / "Season 01"
    season_dir.mkdir(parents=True)
    episode_file = season_dir / "Test.Show.S01E01.mkv"
    episode_file.write_text("x", encoding="utf-8")

    decision = library_media_root_policy.build_from_library_layout(
        _media(MediaType.tv, "Test Show"),
        LibraryMediaLayout(
            media_id=MediaID.parse("tmdb:tv:1"),
            entries=[
                LibraryMediaLayoutEntry(
                    file_id="file-1",
                    absolute_path=str(episode_file),
                    is_video=True,
                    episode_numbers=[],
                )
            ],
            primary_anchor_file=str(episode_file),
            media_type="tv",
        ),
    )

    assert decision is not None
    assert decision.anchor_file == str(episode_file)
    assert decision.media_root_dir == str(show_dir)
    assert [item.destination_path for item in decision.target_files] == [str(episode_file)]


def test_library_layout_policy_keeps_movie_root_at_anchor_folder_when_multiple_versions_exist(tmp_path: Path):
    movie_a_dir = tmp_path / "Movies" / "Movie A (2024)"
    movie_b_dir = tmp_path / "Movies" / "Movie A (Director Cut)"
    movie_a_dir.mkdir(parents=True)
    movie_b_dir.mkdir(parents=True)
    anchor_file = movie_a_dir / "Movie.A.2024.mkv"
    other_file = movie_b_dir / "Movie.A.Director.Cut.mkv"
    anchor_file.write_text("x", encoding="utf-8")
    other_file.write_text("x", encoding="utf-8")

    decision = library_media_root_policy.build_from_target_files(
        _media(MediaType.movie, "Movie A"),
        [
            LibraryLayoutTargetFile(destination_path=str(anchor_file)),
            LibraryLayoutTargetFile(destination_path=str(other_file)),
        ],
        anchor_file=str(anchor_file),
    )

    assert decision is not None
    assert decision.media_root_dir == str(movie_a_dir)


def test_library_layout_policy_infers_movie_disc_root_above_bdmv(tmp_path: Path):
    movie_dir = tmp_path / "Movies" / "Test Movie (2024)"
    index_file = movie_dir / "BDMV" / "index.bdmv"
    index_file.parent.mkdir(parents=True)
    index_file.write_text("x", encoding="utf-8")

    decision = library_media_root_policy.build_from_target_files(
        _media(MediaType.movie, "Test Movie"),
        [LibraryLayoutTargetFile(destination_path=str(index_file))],
        anchor_file=str(index_file),
    )

    assert decision is not None
    assert decision.media_root_dir == str(movie_dir)


def test_library_layout_policy_infers_movie_disc_root_above_release_folder(tmp_path: Path):
    movie_dir = tmp_path / "Movies" / "Test Movie (2024)"
    index_file = movie_dir / "Test.Movie.2024.BluRay.Disc" / "BDMV" / "index.bdmv"
    index_file.parent.mkdir(parents=True)
    index_file.write_text("x", encoding="utf-8")

    decision = library_media_root_policy.build_from_target_files(
        _media(MediaType.movie, "Test Movie"),
        [LibraryLayoutTargetFile(destination_path=str(index_file))],
        anchor_file=str(index_file),
    )

    assert decision is not None
    assert decision.media_root_dir == str(movie_dir)


def test_library_layout_policy_infers_tv_disc_show_root_above_season_and_disc(tmp_path: Path):
    show_dir = tmp_path / "TV" / "Test Show"
    index_file = show_dir / "Season 01" / "Disc 01" / "BDMV" / "index.bdmv"
    index_file.parent.mkdir(parents=True)
    index_file.write_text("x", encoding="utf-8")
    media = _media(MediaType.tv, "Test Show")
    media.season_number = 1

    decision = library_media_root_policy.build_from_target_files(
        media,
        [LibraryLayoutTargetFile(destination_path=str(index_file))],
        anchor_file=str(index_file),
    )

    assert decision is not None
    assert decision.media_root_dir == str(show_dir)


def test_library_target_path_policy_uses_media_title_for_title_tokens():
    template = Template(
        full_template="{Title}/{Title}",
        dir_template="{Title}",
        file_template="{Title}",
    )
    file_item = TorrentFileItem(
        index=0,
        filename="Torrent.File.Name.2024.1080p.WEB-DL.mkv",
        size=100,
        attrs=ResourceAttributes(title="Torrent File Name"),
    )

    destination = library_target_path_policy.build_destination_path(
        destination_base_path=Path("/library"),
        template_config=template,
        title="Actual Movie",
        year=2024,
        season_number=None,
        file_item=file_item,
    )

    assert str(destination) == "/library/Actual Movie/Actual Movie.mkv"


def test_library_target_path_policy_downgrades_missing_episode_to_clean_extra_like_tv_name():
    template = Template(
        full_template="{Title}/Season {season:00}/{Title} S{season:00}E{episode:00}",
        dir_template="{Title}/Season {season:00}",
        file_template="{Title} S{season:00}E{episode:00}",
    )
    file_item = TorrentFileItem(
        index=0,
        filename="Test.Show.mkv",
        size=100,
        attrs=None,
    )

    assert library_target_path_policy.extract_episode_number(file_item, season_number=1) == 0
    destination = library_target_path_policy.build_destination_path(
        destination_base_path=Path("/library"),
        template_config=template,
        title="Actual Show",
        year=2024,
        season_number=1,
        file_item=file_item,
    )

    assert str(destination) == "/library/Actual Show/Season 01/Actual Show S01.mkv"
