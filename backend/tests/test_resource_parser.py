"""
text

text：
1. 100%text，text
2. textparsertext：
   - video_features text（HEVC/AVC/AV1）text（DTS/Atmos/TrueHD/DDP）
   - video_features text SDR/8bit
   - sources text，text
   - platforms text
   - groups text，texttoken
   - REMUX text source
3. text：
   - text/text/text/text
   - text/text/text
   - text/text
   - text/text/HDR/text
   - text
   - textPTtext
"""

import pytest
from app.services.domain.resource.parser import resource_parser
from app.services.config.default_tags import DEFAULT_TAGS
from app.services.domain.resource.tags import resolve_display_tags


class TestMovieBasics:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            (
                "The.Movie.2024.1080p.WEB-DL.H264.AAC-GroupName",
                {
                    "groups": ["GroupName"],
                    "sources": ["WEB-DL"],
                    "platforms": [],
                    "versions": [],
                    "seasons": [],
                    "episodes": [],
                    "resolution": "1080p",
                    "video_codec": "AVC",
                    "audio_codec": "AAC",
                    "hdr_type": None,
                    "audio_channels": None,
                    "color_depth": None,
                },
            ),
            (
                "Movie.2023.2160p.UHD.BluRay.REMUX.HEVC.DV.HDR10+.TrueHD.Atmos-FRDS",
                {
                    "groups": ["FRDS"],
                    "sources": ["UHD BluRay", "REMUX"],
                    "platforms": [],
                    "versions": [],
                    "seasons": [],
                    "episodes": [],
                    "resolution": "2160p",
                    "video_codec": "HEVC",
                    "audio_codec": "Dolby Atmos",
                    "hdr_type": "Dolby Vision",
                    "audio_channels": None,
                    "color_depth": None,
                },
            ),
            (
                "Film.1080p.BluRay.x264.DTS-HD.MA.5.1@TeamXYZ",
                {
                    "groups": ["TeamXYZ"],
                    "sources": ["BluRay"],
                    "platforms": [],
                    "versions": [],
                    "seasons": [],
                    "episodes": [],
                    "resolution": "1080p",
                    "video_codec": "AVC",
                    "audio_codec": "DTS-HD MA",
                    "hdr_type": None,
                    "audio_channels": "5.1",
                    "color_depth": None,
                },
            ),
            (
                "Cold War 2012 2160p HQ WEB-DL H.265 60fps DTS5.1 2Audio-CHDWEB",
                {
                    "groups": ["CHDWEB"],
                    "sources": ["WEB-DL"],
                    "platforms": [],
                    "versions": [],
                    "seasons": [],
                    "episodes": [],
                    "resolution": "2160p",
                    "video_codec": "HEVC",
                    "audio_codec": "DTS",
                    "hdr_type": None,
                    "audio_channels": "5.1",
                    "color_depth": None,
                },
            ),
            (
                "Movie.2024.720p.WEBRip.AV1.IMAX.DDP5.1",
                {
                    "groups": [],  # Internal note.
                    "sources": ["WEBRip"],
                    "platforms": [],
                    "versions": ["IMAX"],
                    "seasons": [],
                    "episodes": [],
                    "resolution": "720p",
                    "video_codec": "AV1",
                    "audio_codec": "DDP",
                    "hdr_type": None,
                    "audio_channels": "5.1",
                    "color_depth": None,
                },
            ),
        ],
    )
    def test_movie_basic_parsing(self, title, expected):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert sorted(attrs.groups) == sorted(expected["groups"])
        assert sorted(attrs.sources) == sorted(expected["sources"])
        assert sorted(attrs.platforms) == sorted(expected["platforms"])
        assert sorted(attrs.versions) == sorted(expected["versions"])
        assert sorted(attrs.seasons) == sorted(expected["seasons"])
        assert sorted(attrs.episodes) == sorted(expected["episodes"])
        assert attrs.resolution == expected["resolution"]
        assert attrs.video_codec == expected["video_codec"]
        assert attrs.audio_codec == expected["audio_codec"]
        assert attrs.hdr_type == expected["hdr_type"]
        assert attrs.audio_channels == expected["audio_channels"]
        assert attrs.color_depth == expected["color_depth"]


class TestTVShows:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            (
                "Show.S01E01.1080p.WEB-DL.H265.AAC-Team",
                {
                    "groups": ["Team"],
                    "sources": ["WEB-DL"],
                    "platforms": [],
                    "seasons": [1],
                    "episodes": [1],
                    "resolution": "1080p",
                    "video_codec": "HEVC",
                    "audio_codec": "AAC",
                },
            ),
            (
                "Series.S02E05-E08.2160p.AMZN.WEB-DL.DV.HDR10.DDP5.1.Atmos.HEVC-GroupABC",
                {
                    "groups": ["GroupABC"],
                    "sources": ["WEB-DL"],
                    "platforms": ["Amazon Prime Video"],
                    "seasons": [2],
                    "episodes": [5, 6, 7, 8],
                    "resolution": "2160p",
                    "video_codec": "HEVC",
                    "audio_codec": "Dolby Atmos",
                    "hdr_type": "Dolby Vision",
                    "audio_channels": "5.1",
                },
            ),
            (
                "Friends.S10E17E18.1080p.BluRay.Remux.AVC.AC3-WhaleHu",
                {
                    "groups": ["WhaleHu"],
                    "sources": ["BluRay", "REMUX"],
                    "platforms": [],
                    "seasons": [10],
                    "episodes": [17, 18],
                    "resolution": "1080p",
                    "video_codec": "AVC",
                    "audio_codec": "AC3",
                },
            ),
            (
                "Drama.S01-S03.Complete.1080p.NF.WEBRip.x264.DDP5.1",
                {
                    "groups": [],  # Internal note.
                    "sources": ["WEBRip"],
                    "platforms": ["Netflix"],
                    "seasons": [1, 2, 3],
                    "episodes": [],
                    "versions": ["Complete"],
                    "resolution": "1080p",
                    "video_codec": "AVC",
                    "audio_codec": "DDP",
                    "audio_channels": "5.1",
                },
            ),
        ],
    )
    def test_tv_show_parsing(self, title, expected):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert sorted(attrs.groups) == sorted(expected["groups"])
        assert sorted(attrs.sources) == sorted(expected["sources"])
        assert sorted(attrs.platforms) == sorted(expected["platforms"])
        assert sorted(attrs.seasons) == sorted(expected["seasons"])
        assert sorted(attrs.episodes) == sorted(expected["episodes"])
        assert sorted(attrs.versions) == sorted(expected.get("versions", []))
        assert attrs.resolution == expected["resolution"]
        assert attrs.video_codec == expected["video_codec"]
        assert attrs.audio_codec == expected["audio_codec"]
        if "hdr_type" in expected:
            assert attrs.hdr_type == expected["hdr_type"]
        if "audio_channels" in expected:
            assert attrs.audio_channels == expected["audio_channels"]


class TestDiscNumberFormats:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected_disc_number,expected_disc_total",
        [
            ("Show.S01.Disc.1.of.2.1080p.BluRay.AVC.DTS-HD.MA", 1, 2),
            ("Show.S01.DISC02.1080p.BluRay.AVC.DTS-HD.MA", 2, None),
            ("Show.S01D03.1080p.BluRay.AVC.DTS-HD.MA", 3, None),
            ("庆余年.S01.第2碟.1080p.BluRay.AVC.DTS-HD.MA", 2, None),
            ("庆余年.S01.碟3.1080p.BluRay.AVC.DTS-HD.MA", 3, None),
        ],
    )
    def test_disc_number_extraction(self, title, expected_disc_number, expected_disc_total):
        attrs = resource_parser.parse(title)
        assert attrs.disc_number == expected_disc_number
        assert attrs.disc_total == expected_disc_total

    def test_disc_number_does_not_create_episode_coverage(self):
        attrs = resource_parser.parse("Show.S01.Disc.1.of.2.1080p.BluRay.AVC.DTS-HD.MA")
        assert attrs.seasons == [1]
        assert attrs.episodes == []


class TestChineseContent:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            (
                "流浪地球.2024.1080p.WEB-DL.H264.AAC-HHWEB",
                {
                    "groups": ["HHWEB"],
                    "sources": ["WEB-DL"],
                    "platforms": [],
                    "resolution": "1080p",
                    "video_codec": "AVC",
                    "audio_codec": "AAC",
                },
            ),
            (
                "庆余年.S01E01.2160p.IQIYI.WEB-DL.H265.AAC@HHWEB",
                {
                    "groups": ["HHWEB"],
                    "sources": ["WEB-DL"],
                    "platforms": ["iQIYI"],
                    "seasons": [1],
                    "episodes": [1],
                    "resolution": "2160p",
                    "video_codec": "HEVC",
                    "audio_codec": "AAC",
                },
            ),
            (
                "大江大河.S01.1080p.MGTV.WEB-DL.AAC.H264-HHWEB",
                {
                    "groups": ["HHWEB"],
                    "sources": ["WEB-DL"],
                    "platforms": ["Mango TV"],
                    "seasons": [1],
                    "resolution": "1080p",
                    "video_codec": "AVC",
                    "audio_codec": "AAC",
                },
            ),
            (
                "[ANi] 葬送的芙莉莲.S01.1080p.Bilibili.WEB-DL.AAC.AVC",
                {
                    "groups": ["ANi"],
                    "sources": ["WEB-DL"],
                    "platforms": ["Bilibili"],
                    "seasons": [1],
                    "resolution": "1080p",
                    "video_codec": "AVC",
                    "audio_codec": "AAC",
                },
            ),
        ],
    )
    def test_chinese_content_parsing(self, title, expected):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert sorted(attrs.groups) == sorted(expected["groups"])
        assert sorted(attrs.sources) == sorted(expected["sources"])
        assert sorted(attrs.platforms) == sorted(expected["platforms"])
        assert sorted(attrs.seasons) == sorted(expected.get("seasons", []))
        assert sorted(attrs.episodes) == sorted(expected.get("episodes", []))
        assert attrs.resolution == expected["resolution"]
        assert attrs.video_codec == expected["video_codec"]
        assert attrs.audio_codec == expected["audio_codec"]


class TestStreamingPlatforms:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected_platform",
        [
            ("Movie.2024.1080p.NF.WEB-DL.H264-Grp", ["Netflix"]),
            ("Show.S01.2160p.AMZN.WEB-DL.HEVC-Grp", ["Amazon Prime Video"]),
            ("Film.1080p.DSNP.WEBRip.x264-Grp", ["Disney+"]),
            ("Series.S01.1080p.HMAX.WEB-DL.H265-Grp", ["HBO Max"]),
            ("Movie.720p.ATVP.WEB-DL.x264-Grp", ["Apple TV+"]),
            ("Show.S01.1080p.PMTP.WEBRip.H264-Grp", ["Paramount+"]),
            ("Film.1080p.IQIYI.WEB-DL.H264-Grp", ["iQIYI"]),
            ("庆余年.S01.1080p.腾讯视频.WEB-DL.H265-Grp", ["Tencent Video"]),
            ("Movie.1080p.YOUKU.WEB-DL.x264-Grp", ["Youku"]),
            ("大江大河.S01.1080p.芒果TV.WEB-DL.H264-Grp", ["Mango TV"]),
            ("葬送的芙莉莲.S01.1080p.哔哩哔哩.WEB-DL.AVC-Grp", ["Bilibili"]),
        ],
    )
    def test_platform_detection(self, title, expected_platform):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert sorted(attrs.platforms) == sorted(expected_platform)
        # sourcestextWEB-DL/WEBRip，text
        assert all(p not in ["Netflix", "Amazon", "Disney+", "iQIYI", "Tencent Video", "Youku", "Mango TV", "Bilibili"] for p in attrs.sources)


class TestVideoCodecs:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected_codec,expected_color_depth,expected_hdr",
        [
            ("Movie.1080p.WEB-DL.H264.AAC-Grp", "AVC", None, None),
            ("Film.1080p.WEB-DL.x264.AAC-Grp", "AVC", None, None),
            ("Show.S01.2160p.WEB-DL.H265.AAC-Grp", "HEVC", None, None),
            ("Movie.2160p.WEB-DL.HEVC.AAC-Grp", "HEVC", None, None),
            ("Film.1080p.WEBRip.AV1.Opus-Grp", "AV1", None, None),
            # Internal note.
            ("Movie.1080p.WEB-DL.HEVC.10bit.HDR-Grp", "HEVC", "10bit", "HDR10"),
        ],
    )
    def test_video_codec_extraction(self, title, expected_codec, expected_color_depth, expected_hdr):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert attrs.video_codec == expected_codec
        assert attrs.color_depth == expected_color_depth
        assert attrs.hdr_type == expected_hdr


class TestAudioCodecs:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected_audio,expected_channels",
        [
            ("Movie.1080p.BluRay.H264.AAC-Grp", "AAC", None),
            ("Film.1080p.BluRay.x264.AC3-Grp", "AC3", None),
            ("Show.S01.1080p.BluRay.H265.DTS-Grp", "DTS", None),
            ("Movie.1080p.BluRay.x264.DTS-HD.MA.5.1-Grp", "DTS-HD MA", "5.1"),
            ("Film.2160p.BluRay.HEVC.TrueHD.Atmos-Grp", "Dolby Atmos", None),  # Atmostext
            ("Movie.1080p.WEB-DL.H264.DDP5.1-Grp", "DDP", "5.1"),
            ("Show.S01.1080p.WEB-DL.H265.DDP.5.1-Grp", "DDP", "5.1"),
            ("Movie.2160p.BluRay.HEVC.Atmos-Grp", "Dolby Atmos", None),
        ],
    )
    def test_audio_codec_extraction(self, title, expected_audio, expected_channels):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert attrs.audio_codec == expected_audio
        assert attrs.audio_channels == expected_channels


class TestHDRTypes:
    """HDRtext"""

    @pytest.mark.parametrize(
        "title,expected_hdr",
        [
            ("Movie.2160p.WEB-DL.HEVC.HDR-Grp", "HDR10"),
            ("Film.2160p.WEB-DL.H265.HDR10-Grp", "HDR10"),
            ("Show.S01.2160p.WEB-DL.HEVC.HDR10+-Grp", "HDR10+"),
            ("Movie.2160p.UHD.BluRay.HEVC.DV-Grp", "Dolby Vision"),
            ("Film.2160p.WEB-DL.H265.DV.HDR10-Grp", "Dolby Vision"),
        ],
    )
    def test_hdr_type_detection(self, title, expected_hdr):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert attrs.hdr_type == expected_hdr


class TestGroupExtraction:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected_groups",
        [
            # Internal note.
            ("Movie.1080p.WEB-DL.H264-GroupName", ["GroupName"]),
            ("Film.1080p.BluRay.x264@TeamXYZ", ["TeamXYZ"]),
            ("[SubGroup] Anime.S01.1080p.WEB-DL.H264", ["SubGroup"]),
            ("[HHWEB]流浪地球.2024.1080p.WEB-DL.H265", ["HHWEB"]),
            ("【VCB-Studio】葬送的芙莉莲.2024.1080p.BluRay.FLAC", ["VCB-Studio"]),
            # Internal note.
            ("Movie.1080p.WEB-DL.H264.AAC", []),
            ("Film.2160p.UHD.BluRay.REMUX.HEVC", []),
            ("Show.S01.1080p.WEB-DL.DDP5.1", []),
            # Internal note.
            ("Movie.1080p.WEB-DL.H264-HEVC", []),  # HEVCtext，text
            ("Film.1080p.BluRay.x264-DTS", []),  # DTStext，text
            # Internal note.
            ("Movie.1080p.WEB-DL.H264-VeryLongGroupName123", ["VeryLongGroupName123"]),
        ],
    )
    def test_group_extraction_logic(self, title, expected_groups):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert sorted(attrs.groups) == sorted(expected_groups)


class TestSeasonEpisodeRanges:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected_seasons,expected_episodes",
        [
            # Internal note.
            ("Show.S01E01.1080p.WEB-DL.H264-Grp", [1], [1]),
            ("Series.S02E10.1080p.WEB-DL.H265-Grp", [2], [10]),
            # Internal note.
            ("Show.S01E01-E05.1080p.WEB-DL.H264-Grp", [1], [1, 2, 3, 4, 5]),
            ("Series.S02E10-12.1080p.WEB-DL.H265-Grp", [2], [10, 11, 12]),
            # Internal note.
            ("Show.S01-S03.1080p.WEB-DL.H264-Grp", [1, 2, 3], []),
            ("Series.Season.1-3.1080p.WEB-DL.H265-Grp", [1, 2, 3], []),
            # Internal note.
            ("Show.S01.S02.1080p.WEB-DL.H264-Grp", [1, 2], []),
            # Internal note.
            ("庆余年.第1季.1080p.WEB-DL.H264-HHWEB", [1], []),
            ("庆余年.Season.1-3.1080p.WEB-DL.H264-HHWEB", [1, 2, 3], []),
        ],
    )
    def test_season_episode_extraction(self, title, expected_seasons, expected_episodes):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert sorted(attrs.seasons) == sorted(expected_seasons)
        assert sorted(attrs.episodes) == sorted(expected_episodes)


class TestVersions:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected_versions",
        [
            ("Movie.2024.Directors.Cut.1080p.BluRay.x264-Grp", ["Director's Cut"]),
            ("Film.2023.Extended.1080p.BluRay.H265-Grp", ["Extended"]),
            ("Movie.Uncut.1080p.BluRay.x264-Grp", ["Uncut"]),
            ("Film.Remastered.1080p.BluRay.HEVC-Grp", ["Remastered"]),
            ("Movie.IMAX.Edition.2160p.BluRay.x265-Grp", ["IMAX Edition"]),
            ("Film.Theatrical.Cut.1080p.BluRay.x264-Grp", ["Theatrical"]),
            ("Show.S01.Complete.1080p.WEB-DL.H264-Grp", ["Complete"]),
            ("Movie.Proper.1080p.WEB-DL.x264-Grp", ["Proper"]),
            ("Film.Repack.1080p.BluRay.H265-Grp", ["Repack"]),
        ],
    )
    def test_version_detection(self, title, expected_versions):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert sorted(attrs.versions) == sorted(expected_versions)


class TestResolutions:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected_resolution",
        [
            ("Movie.480p.WEB-DL.H264-Grp", "480p"),
            ("Film.720p.WEB-DL.x264-Grp", "720p"),
            ("Show.S01.1080p.WEB-DL.H265-Grp", "1080p"),
            ("Movie.2160p.WEB-DL.HEVC-Grp", "2160p"),
            ("Film.4K.UHD.BluRay.x265-Grp", "2160p"),
        ],
    )
    def test_resolution_extraction(self, title, expected_resolution):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert attrs.resolution == expected_resolution


class TestSources:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected_sources",
        [
            ("Movie.1080p.WEB-DL.H264-Grp", ["WEB-DL"]),
            ("Film.1080p.WEBRip.x264-Grp", ["WEBRip"]),
            ("Show.S01.1080p.BluRay.H265-Grp", ["BluRay"]),
            ("Movie.2160p.UHD.BluRay.HEVC-Grp", ["UHD BluRay"]),
            ("Film.1080p.HDTV.x264-Grp", ["HDTV"]),
            ("Movie.DVDRip.x264-Grp", ["DVDRip"]),
            ("Movie.1999.DVD9.VIDEO_TS", ["DVD"]),
            ("Film.2160p.UHD.BluRay.REMUX.HEVC-Grp", ["UHD BluRay", "REMUX"]),
            ("Movie.1080p.BluRay.REMUX.AVC-Grp", ["BluRay", "REMUX"]),
            ("Cold.War.Ⅱ.2016.WEB-DL.4K.H264.AAC-HDATV", ["WEB-DL"]),
        ],
    )
    def test_source_extraction(self, title, expected_sources):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert sorted(attrs.sources) == sorted(expected_sources)


class TestComplexRealWorld:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            (
                "The.Last.of.Us.S01E01.2160p.HMAX.WEB-DL.DDP5.1.Atmos.DV.HEVC-FLUX",
                {
                    "groups": ["FLUX"],
                    "sources": ["WEB-DL"],
                    "platforms": ["HBO Max"],
                    "seasons": [1],
                    "episodes": [1],
                    "resolution": "2160p",
                    "video_codec": "HEVC",
                    "audio_codec": "Dolby Atmos",
                    "hdr_type": "Dolby Vision",
                    "audio_channels": "5.1",
                },
            ),
            (
                "Dune.Part.Two.2024.2160p.UHD.BluRay.REMUX.DV.HDR10.TrueHD.Atmos.7.1.HEVC-EDITH",
                {
                    "groups": ["EDITH"],
                    "sources": ["UHD BluRay", "REMUX"],
                    "platforms": [],
                    "seasons": [],
                    "episodes": [],
                    "resolution": "2160p",
                    "video_codec": "HEVC",
                    "audio_codec": "Dolby Atmos",
                    "hdr_type": "Dolby Vision",
                    "audio_channels": "7.1",
                },
            ),
            (
                "三体.3.Body.Problem.S01.2024.2160p.NF.WEB-DL.DDP5.1.Atmos.DV.H.265-BlackTV",
                {
                    "groups": ["BlackTV"],
                    "sources": ["WEB-DL"],
                    "platforms": ["Netflix"],
                    "seasons": [1],
                    "episodes": [],
                    "resolution": "2160p",
                    "video_codec": "HEVC",
                    "audio_codec": "Dolby Atmos",
                    "hdr_type": "Dolby Vision",
                    "audio_channels": "5.1",
                },
            ),
            (
                "扫毒风暴.The.Narcotic.Operation.S01.2025.2160p.WEB-DL.H265.AAC-HHWEB",
                {
                    "groups": ["HHWEB"],
                    "sources": ["WEB-DL"],
                    "platforms": [],
                    "seasons": [1],
                    "episodes": [],
                    "resolution": "2160p",
                    "video_codec": "HEVC",
                    "audio_codec": "AAC",
                    "hdr_type": None,
                    "audio_channels": None,
                },
            ),
            (
                "[ANi] 葬送的芙莉莲 / Sousou no Frieren [01-28][1080p][Baha][WEB-DL][AAC AVC][CHT]",
                {
                    "groups": ["ANi"],
                    "sources": ["WEB-DL"],
                    "platforms": [],
                    "seasons": [],
                    "episodes": [],
                    "resolution": "1080p",
                    "video_codec": "AVC",
                    "audio_codec": "AAC",
                    "hdr_type": None,
                    "audio_channels": None,
                },
            ),
        ],
    )
    def test_complex_real_world_titles(self, title, expected):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert sorted(attrs.groups) == sorted(expected["groups"])
        assert sorted(attrs.sources) == sorted(expected["sources"])
        assert sorted(attrs.platforms) == sorted(expected["platforms"])
        assert sorted(attrs.seasons) == sorted(expected["seasons"])
        assert sorted(attrs.episodes) == sorted(expected["episodes"])
        assert attrs.resolution == expected["resolution"]
        assert attrs.video_codec == expected["video_codec"]
        assert attrs.audio_codec == expected["audio_codec"]
        assert attrs.hdr_type == expected["hdr_type"]
        if "audio_channels" in expected:
            assert attrs.audio_channels == expected["audio_channels"]


class TestEdgeCases:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            # Internal note.
            (
                "Movie.Title.2024.1080p",
                {
                    "groups": [],
                    "resolution": "1080p",
                },
            ),
            # Internal note.
            (
                "Film.Name.2024.1080p.WEB-DL.HEVC",
                {
                    "groups": [],
                    "video_codec": "HEVC",
                },
            ),
            # Internal note.
            (
                "Movie.2024.1080p.WEB-DL.H264-AAC",
                {
                    "groups": [],  # AACtext，text
                    "audio_codec": "AAC",
                },
            ),
            # Internal note.
            (
                "Movie.2024.1080p.WEB-DL.H264.AAC-Group1-Group2",
                {
                    "groups": ["Group1-Group2"],  # Internal note.
                },
            ),
            # 10bittextvideo_feature，text
            (
                "Movie.2024.1080p.WEB-DL.HEVC.10bit-Grp",
                {
                    "groups": ["Grp"],
                    "color_depth": "10bit",
                    "video_codec": "HEVC",
                },
            ),
        ],
    )
    def test_edge_cases(self, title, expected):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        if "groups" in expected:
            assert sorted(attrs.groups) == sorted(expected["groups"])
        if "resolution" in expected:
            assert attrs.resolution == expected["resolution"]
        if "video_codec" in expected:
            assert attrs.video_codec == expected["video_codec"]
        if "audio_codec" in expected:
            assert attrs.audio_codec == expected["audio_codec"]
        if "color_depth" in expected:
            assert attrs.color_depth == expected["color_depth"]


class TestMultiSeasonFormats:
    """Internal helper."""

    @pytest.mark.parametrize(
        "title,expected_seasons",
        [
            ("Show.S01-S05.1080p.WEB-DL.H264-Grp", [1, 2, 3, 4, 5]),
            ("Series.Season.1-4.Complete.1080p.BluRay.x265-Grp", [1, 2, 3, 4]),
            ("庆余年.第1-3季.1080p.WEB-DL.H264-HHWEB", [1, 2, 3]),
            ("庆余年.第1,2季.1080p.WEB-DL.H264-HHWEB", [1, 2]),
            ("Show.S01.S02.S03.1080p.WEB-DL.HEVC-Grp", [1, 2, 3]),
        ],
    )
    def test_multi_season_extraction(self, title, expected_seasons):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert sorted(attrs.seasons) == sorted(expected_seasons)


class TestIMAXAndSpecialFormats:
    """IMAXtext"""

    @pytest.mark.parametrize(
        "title,expected_versions",
        [
            ("Movie.2024.IMAX.2160p.BluRay.HEVC-Grp", ["IMAX"]),
            ("Film.2023.IMAX.Edition.1080p.BluRay.x264-Grp", ["IMAX Edition"]),
            ("Movie.Directors.Cut.IMAX.2160p.BluRay.HEVC-Grp", ["Director's Cut", "IMAX"]),
        ],
    )
    def test_imax_detection(self, title, expected_versions):
        """Internal helper."""
        attrs = resource_parser.parse(title)
        assert sorted(attrs.versions) == sorted(expected_versions)


class TestDescriptionAndTags:
    def test_desc_episode_fills_when_title_has_no_episode(self):
        attrs = resource_parser.parse(
            "爱情没有神话.2160p.WEB-DL.H265",
            desc="爱情没有神话 第11集 | 类型：剧情 爱情 | 主演：唐嫣 赵又廷 杨采钰 冯绍峰 晏紫东 | 独身女人 *云视听极光*",
        )

        assert attrs.desc
        assert attrs.episodes == [11]

    def test_title_episode_wins_over_desc_episode(self):
        attrs = resource_parser.parse("Show.S01E10.1080p.WEB-DL.H264", desc="第11集 | 类型：剧情")

        assert attrs.episodes == [10]

    @pytest.mark.parametrize(
        "desc,expected_tags",
        [
            ("特效双语字幕", ["双语", "特效"]),
            ("中字外挂字幕", ["中字"]),
            ("国英双音", ["国语"]),
            ("IMAX版", ["IMAX"]),
        ],
    )
    def test_desc_tags(self, desc, expected_tags):
        attrs = resource_parser.parse("Movie.2024.1080p.WEB-DL.H264", desc=desc)
        tags = resolve_display_tags(attrs, tags=DEFAULT_TAGS)

        for tag in expected_tags:
            assert tag in tags

    def test_desc_does_not_parse_plain_numbers_as_episodes(self):
        attrs = resource_parser.parse("爱情没有神话.2160p.WEB-DL.H265", desc="类型：剧情 爱情 | 主演：唐嫣 赵又廷 | 2026")

        assert attrs.episodes == []

    def test_desc_does_not_use_quality_caveat_as_episode_coverage(self):
        attrs = resource_parser.parse(
            "We Are Criminal Police S01 2024 2160p WEB-DL DDP2.0 H265 DV-HDSWEB",
            desc="我是刑警 / 中国刑警 全38集 | 主演: 于和伟 富大龙 丁勇岱  其中第3-5、19-20、23-27、32-33集无DV，普码4K替代。",
        )

        assert attrs.seasons == [1]
        assert attrs.episodes == list(range(1, 39))

    def test_desc_complete_marker_without_count_blocks_quality_caveat_episodes(self):
        attrs = resource_parser.parse(
            "We Are Criminal Police S01 2024 2160p WEB-DL DDP2.0 H265 DV-HDSWEB",
            desc="我是刑警 全集 | 其中第3-5、32-33集无DV，普码4K替代。",
        )

        assert attrs.seasons == [1]
        assert attrs.episodes == []

    @pytest.mark.parametrize("desc", ["第1-12集 无删减版", "第1-12集 无水印", "第1-12集 修复版"])
    def test_desc_episode_keeps_common_version_notes(self, desc):
        attrs = resource_parser.parse("Show S01 2024 1080p WEB-DL H264", desc=desc)

        assert attrs.seasons == [1]
        assert attrs.episodes == list(range(1, 13))

    def test_desc_episode_excludes_explicit_quality_gap(self):
        attrs = resource_parser.parse(
            "Show S01 2024 1080p WEB-DL H264",
            desc="其中第3-5集无DV，普码4K替代。",
        )

        assert attrs.seasons == [1]
        assert attrs.episodes == []

    def test_desc_can_backfill_dolby_vision_and_atmos(self):
        attrs = resource_parser.parse(
            "Movie.2024.2160p.WEB-DL.HEVC",
            desc=(
                "视频参数：HDR 格式：Dolby Vision, dvhe.08.09, BL+RPU; "
                "音频参数：格式：Enhanced AC-3 with Joint Object Coding "
                "（Dolby Digital Plus with Dolby Atmos）"
            ),
        )

        assert attrs.hdr_type == "Dolby Vision"
        assert attrs.audio_codec == "Dolby Atmos"
        tags = resolve_display_tags(attrs, tags=DEFAULT_TAGS)
        assert "杜比视界" not in tags
        assert "杜比全景声" not in tags

    def test_desc_can_upgrade_title_hdr_with_better_desc_hdr(self):
        attrs = resource_parser.parse(
            "Movie.2024.2160p.WEB-DL.HEVC.HDR",
            desc="HDR Format: Dolby Vision / HDR10+ compatible",
        )

        assert attrs.hdr_type == "Dolby Vision"
        assert "HDR10+" not in resolve_display_tags(attrs, tags=DEFAULT_TAGS)

    def test_desc_fallback_uses_desc_only_for_ranked_technical_values(self):
        attrs = resource_parser.parse(
            "Movie.2024.2160p.WEB-DL.H265.AAC",
            desc="Video Codec: AV1. Audio Codec: FLAC.",
        )

        assert attrs.video_codec == "AV1"
        assert attrs.audio_codec == "FLAC"

    def test_desc_tags_cover_frame_rate_bitrate_open_matte_ai_without_multi_subs(self):
        attrs = resource_parser.parse(
            "Blade.Runner.2049.OpenMatte.2160p.HEVC.TrueHD.7.1",
            desc=("Frame Rate: 60FPS. Overall Bitrate : 66.4 Mb/s. " "Topaz Video AI-Enhanced RIFE. MULTI PGS subtitles included."),
        )
        tags = resolve_display_tags(attrs, tags=DEFAULT_TAGS)

        for tag in ["Open Matte", "60帧", "高码", "AI增强"]:
            assert tag in tags
        assert "PGS" not in tags
        assert "多字幕" not in tags

    @pytest.mark.parametrize(
        "marker,expected_subtitle",
        [
            ("BILINGUAL", "双语"),
            ("CHI.ENG", "中英"),
            ("EXTERNAL", "外挂"),
            ("EMBEDDED", "内嵌"),
        ],
    )
    def test_legacy_english_subtitle_markers_are_preserved(self, marker, expected_subtitle):
        attrs = resource_parser.parse(f"Movie.2024.1080p.WEB-DL.{marker}.H264")

        assert attrs.subtitle == expected_subtitle
