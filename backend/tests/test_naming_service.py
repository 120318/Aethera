import pytest

from app.schemas.domain.resource_attributes import NamingContext, ResourceAttributes
from app.services.domain.library.naming_policy import format_name


def test_format_name_preserves_missing_weak_token_placeholders():
    rendered = format_name(
        "{title} ({year}) - {group}",
        NamingContext(
            resource_title="Actual Movie",
            media_type="movie",
            attributes=ResourceAttributes(),
        ),
    )

    assert rendered == "Actual Movie (unknown_year) - unknown_group"


def test_format_name_uses_distinct_placeholders_for_missing_weak_tokens():
    group_rendered = format_name(
        "{title}.{group}",
        NamingContext(
            resource_title="Actual Movie",
            media_type="movie",
            attributes=ResourceAttributes(),
        ),
    )
    resolution_rendered = format_name(
        "{title}.{resolution}",
        NamingContext(
            resource_title="Actual Movie",
            media_type="movie",
            attributes=ResourceAttributes(),
        ),
    )

    assert group_rendered == "Actual Movie.unknown_group"
    assert resolution_rendered == "Actual Movie.unknown_resolution"
    assert group_rendered != resolution_rendered


def test_format_name_cleans_empty_brackets_and_duplicate_separators():
    rendered = format_name(
        "{title} [{resolution}][{source}].{audio}.{video_codec}",
        NamingContext(
            resource_title="Actual Movie",
            media_type="movie",
            attributes=ResourceAttributes(
                resolution="1080p",
                video_codec="HEVC",
            ),
        ),
    )

    assert rendered == "Actual Movie [1080p][unknown_source].unknown_audio.HEVC"


def test_format_name_raises_when_strong_title_is_missing():
    with pytest.raises(ValueError, match="missing naming field: title"):
        format_name(
            "{title} ({year})",
            NamingContext(
                resource_title="",
                media_type="movie",
                attributes=ResourceAttributes(),
            ),
        )


def test_format_name_raises_when_normal_tv_episode_is_missing():
    with pytest.raises(ValueError, match="missing naming field: episode"):
        format_name(
            "{title} S{season:00}E{episode:00}",
            NamingContext(
                resource_title="Actual Show",
                media_type="tv",
                season_number=1,
                naming_category="normal_episode",
                attributes=ResourceAttributes(episodes=[]),
            ),
        )


def test_format_name_cleans_trailing_episode_marker_for_extra_tv_item():
    rendered = format_name(
        "{title} S{season:00}E{episode:00}",
        NamingContext(
            resource_title="Actual Show",
            media_type="tv",
            season_number=1,
            naming_category="extra_episode",
            attributes=ResourceAttributes(episodes=[]),
        ),
    )

    assert rendered == "Actual Show S01"


def test_format_name_renders_multi_episode_token_with_repeated_episode_marker():
    rendered = format_name(
        "{title} - S{season:00}E{episode:00}",
        NamingContext(
            resource_title="Actual Show",
            media_type="tv",
            season_number=10,
            attributes=ResourceAttributes(episodes=[17, 18]),
        ),
    )

    assert rendered == "Actual Show - S10E17E18"


def test_format_name_omits_empty_disc_tokens_for_normal_file():
    rendered = format_name(
        "{title} ({year})/{disc_folder}/{title} ({year}){disc_suffix}",
        NamingContext(
            resource_title="Actual Movie",
            media_type="movie",
            attributes=ResourceAttributes(year=2024),
        ),
    )

    assert rendered == "Actual Movie (2024)/Actual Movie (2024)"


def test_format_name_renders_disc_tokens_for_original_disc():
    rendered = format_name(
        "{title} ({year})/{disc_folder}/{title} ({year}){disc_suffix}",
        NamingContext(
            resource_title="Actual Movie",
            media_type="movie",
            attributes=ResourceAttributes(
                year=2024,
                resource_form="BluRay Disc",
                package_layout="BDMV",
                disc_number=1,
                disc_total=2,
            ),
        ),
    )

    assert rendered == "Actual Movie (2024)/Disc 01/Actual Movie (2024) - Disc 01"


def test_format_name_renders_disc_package_name_for_original_disc():
    rendered = format_name(
        "{title} ({year})/{disc_package_name}/{title} ({year}){disc_suffix}",
        NamingContext(
            resource_title="Actual Movie",
            media_type="movie",
            disc_package_name="Actual.Movie.2024.BluRay.Disc-Group",
            attributes=ResourceAttributes(
                year=2024,
                resource_form="BluRay Disc",
                package_layout="BDMV",
                disc_number=1,
            ),
        ),
    )

    assert rendered == "Actual Movie (2024)/Actual.Movie.2024.BluRay.Disc-Group/Actual Movie (2024) - Disc 01"


def test_format_name_cleans_episode_marker_before_disc_suffix_for_tv_disc():
    rendered = format_name(
        "{title} - S{season:00}E{episode:00}{disc_suffix}",
        NamingContext(
            resource_title="Actual Show",
            media_type="tv",
            season_number=1,
            naming_category="extra_episode",
            attributes=ResourceAttributes(
                episodes=[],
                resource_form="BluRay Disc",
                package_layout="BDMV",
                disc_number=1,
            ),
        ),
    )

    assert rendered == "Actual Show - S01 - Disc 01"
