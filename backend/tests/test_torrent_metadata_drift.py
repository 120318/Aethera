from __future__ import annotations

from collections import OrderedDict

import bencodepy
import pytest

from app.services.domain.resource.torrent_metadata import parse_torrent_metadata
from app.services.domain.resource.torrent_season import (
    select_torrent_episode_files,
    selected_files_have_season_conflict,
)


pytestmark = [pytest.mark.drift]


def test_parse_metadata_accepts_bencodepy_ordered_dict_info_and_file_entries():
    payload = bencodepy.encode(
        OrderedDict(
            [
                (
                    b"info",
                    OrderedDict(
                        [
                            (b"name", b"Show.Name.S01"),
                            (
                                b"files",
                                [
                                    OrderedDict(
                                        [
                                            (b"length", 123),
                                            (b"path", [b"Show.Name.S01", b"Show.Name.S01E01.mkv"]),
                                        ]
                                    )
                                ],
                            ),
                        ]
                    ),
                )
            ]
        )
    )

    metadata = parse_torrent_metadata(payload)

    assert metadata.name == "Show.Name.S01"
    assert metadata.size == 123
    assert metadata.files[0].filename == "Show.Name.S01/Show.Name.S01E01.mkv"


def test_parse_metadata_confirms_bluray_disc_structure():
    payload = bencodepy.encode(
        OrderedDict(
            [
                (
                    b"info",
                    OrderedDict(
                        [
                            (b"name", b"Show.Name.S01.Disc.1.of.2"),
                            (
                                b"files",
                                [
                                    OrderedDict(
                                        [
                                            (b"length", 123),
                                            (b"path", [b"Show.Name.S01.Disc.1.of.2", b"BDMV", b"index.bdmv"]),
                                        ]
                                    )
                                ],
                            ),
                        ]
                    ),
                )
            ]
        )
    )

    metadata = parse_torrent_metadata(payload)

    assert metadata.attrs.resource_form == "BluRay Disc"
    assert metadata.attrs.resource_form_evidence == "torrent_structure"
    assert metadata.attrs.package_layout == "BDMV"
    assert metadata.attrs.seasons == [1]
    assert metadata.attrs.disc_number == 1
    assert metadata.attrs.disc_total == 2
    assert metadata.coverage_kind == "disc_package"
    assert metadata.get_episodes() == set()


def test_parse_metadata_confirms_dvd_disc_structure():
    payload = bencodepy.encode(
        OrderedDict(
            [
                (
                    b"info",
                    OrderedDict(
                        [
                            (b"name", b"Movie.1999"),
                            (
                                b"files",
                                [
                                    OrderedDict(
                                        [
                                            (b"length", 123),
                                            (b"path", [b"Movie.1999", b"VIDEO_TS", b"VIDEO_TS.IFO"]),
                                        ]
                                    ),
                                    OrderedDict(
                                        [
                                            (b"length", 456),
                                            (b"path", [b"Movie.1999", b"VIDEO_TS", b"VTS_01_1.VOB"]),
                                        ]
                                    ),
                                ],
                            ),
                        ]
                    ),
                )
            ]
        )
    )

    metadata = parse_torrent_metadata(payload)

    assert metadata.attrs.resource_form == "DVD Disc"
    assert metadata.attrs.resource_form_evidence == "torrent_structure"
    assert metadata.attrs.package_layout == "VIDEO_TS"
    assert metadata.attrs.sources == ["DVD"]
    assert metadata.coverage_kind == "disc_package"


def test_parse_metadata_confirms_iso_package_layout():
    payload = bencodepy.encode(
        OrderedDict(
            [
                (
                    b"info",
                    OrderedDict(
                        [
                            (b"name", b"Movie.2024.BDISO.iso"),
                            (b"length", 123),
                        ]
                    ),
                )
            ]
        )
    )

    metadata = parse_torrent_metadata(payload)

    assert metadata.attrs.resource_form == "BluRay Disc"
    assert metadata.attrs.resource_form_evidence == "torrent_structure"
    assert metadata.attrs.package_layout == "ISO"
    assert metadata.coverage_kind == "disc_package"


def test_parse_metadata_keeps_episode_from_description_when_files_have_no_episode():
    payload = bencodepy.encode(
        OrderedDict(
            [
                (
                    b"info",
                    OrderedDict(
                        [
                            (b"name", "爱情没有神话.2160p.WEB-DL.H265".encode()),
                            (
                                b"files",
                                [
                                    OrderedDict(
                                        [
                                            (b"length", 123),
                                            (b"path", ["爱情没有神话.2160p.WEB-DL.H265.mkv".encode()]),
                                        ]
                                    )
                                ],
                            ),
                        ]
                    ),
                )
            ]
        )
    )

    metadata = parse_torrent_metadata(payload, desc="爱情没有神话 第11集 | 类型：剧情 爱情")

    assert metadata.attrs.desc == "爱情没有神话 第11集 | 类型：剧情 爱情"
    assert metadata.attrs.episodes == [11]
    assert metadata.get_episodes() == {11}


def test_multi_season_metadata_cannot_assign_seasonless_episode_file_to_one_season():
    payload = bencodepy.encode(
        OrderedDict(
            [
                (
                    b"info",
                    OrderedDict(
                        [
                            (b"name", b"Show.Name.S01-S03"),
                            (
                                b"files",
                                [
                                    OrderedDict(
                                        [
                                            (b"length", 123),
                                            (b"path", [b"Show.Name.S01-S03", b"Show.Name.E01.mkv"]),
                                        ]
                                    )
                                ],
                            ),
                        ]
                    ),
                )
            ]
        )
    )

    metadata = parse_torrent_metadata(payload)

    assert metadata.attrs.seasons == [1, 2, 3]
    assert metadata.files[0].attrs.seasons == []
    assert select_torrent_episode_files(metadata, season_number=1, episodes={1}) == []
    assert selected_files_have_season_conflict(metadata, season_number=1, selected_files=[0]) is True


def test_multi_season_torrent_can_select_file_with_one_explicit_target_season():
    payload = bencodepy.encode(
        OrderedDict(
            [
                (
                    b"info",
                    OrderedDict(
                        [
                            (b"name", b"Show.Name.S01-S02"),
                            (
                                b"files",
                                [
                                    OrderedDict(
                                        [
                                            (b"length", 123),
                                            (b"path", [b"Show.Name.S01-S02", b"Show.Name.S01E01.mkv"]),
                                        ]
                                    ),
                                    OrderedDict(
                                        [
                                            (b"length", 456),
                                            (b"path", [b"Show.Name.S01-S02", b"Show.Name.S02E01.mkv"]),
                                        ]
                                    ),
                                ],
                            ),
                        ]
                    ),
                )
            ]
        )
    )

    metadata = parse_torrent_metadata(payload)

    assert select_torrent_episode_files(metadata, season_number=1, episodes={1}) == [0]
    assert selected_files_have_season_conflict(metadata, season_number=1, selected_files=[0]) is False
    assert selected_files_have_season_conflict(metadata, season_number=1, selected_files=None) is True


def test_nested_single_season_directory_remains_file_season_evidence():
    payload = bencodepy.encode(
        OrderedDict(
            [
                (
                    b"info",
                    OrderedDict(
                        [
                            (b"name", b"Show.Name.Complete"),
                            (
                                b"files",
                                [
                                    OrderedDict(
                                        [
                                            (b"length", 123),
                                            (b"path", [b"Season 2", b"Show.Name.E01.mkv"]),
                                        ]
                                    )
                                ],
                            ),
                        ]
                    ),
                )
            ]
        )
    )

    metadata = parse_torrent_metadata(payload)

    assert metadata.attrs.seasons == [2]
    assert metadata.files[0].attrs.seasons == [2]
    assert select_torrent_episode_files(metadata, season_number=1, episodes={1}) == []
    assert selected_files_have_season_conflict(metadata, season_number=1, selected_files=[0]) is True
