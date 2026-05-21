from app.schemas.domain.quality_ranking import QualityRankingConfig
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.services.domain.resource.quality import (
    compare_resource_attributes,
    has_any_resource_attributes,
    has_comparable_resource_attributes,
    quality_sort_key,
    resource_attributes_match,
)
from app.services.domain.resource.parser import resource_parser


def test_quality_sort_key_uses_custom_dimension_order_and_ranking():
    ranking = QualityRankingConfig(
        dimension_order=["source", "resolution"],
        source=["WEB-DL", "BluRay"],
        resolution=["1080p", "2160p"],
    )
    web_2160 = ResourceAttributes(resolution="2160p", sources=["WEB-DL"])
    bluray_1080 = ResourceAttributes(resolution="1080p", sources=["BluRay"])

    assert quality_sort_key(web_2160, ranking) > quality_sort_key(bluray_1080, ranking)


def test_compare_resource_attributes_ignores_unknown_or_missing_values():
    existing = ResourceAttributes(resolution="1080p")
    incoming = ResourceAttributes()

    assert compare_resource_attributes(existing, incoming) is None
    assert has_comparable_resource_attributes(existing, incoming) is True
    assert has_any_resource_attributes(incoming) is False


def test_resource_attributes_match_requires_at_least_one_comparable_pair():
    assert resource_attributes_match(ResourceAttributes(), ResourceAttributes()) is False

    left = ResourceAttributes(resolution="2160p", sources=["WEB-DL"], video_codec="HEVC")
    right = ResourceAttributes(resolution="2160p", sources=["WEB-DL"], video_codec="HEVC")

    assert resource_attributes_match(left, right) is True


def test_quality_sort_does_not_promote_release_group_as_source():
    hdatv_group = resource_parser.parse("Cold.War.Ⅱ.2016.WEB-DL.4K.H264.AAC-HDATV")
    adweb_hevc = resource_parser.parse("Cold.War.Ⅱ.2016.2160p.WEB-DL.H.265.AAC.2Audio-ADWeb")

    assert hdatv_group.sources == ["WEB-DL"]
    assert quality_sort_key(adweb_hevc, QualityRankingConfig()) > quality_sort_key(hdatv_group, QualityRankingConfig())


def test_quality_sort_treats_stereo_channels_as_unknown():
    stereo = ResourceAttributes(resolution="2160p", sources=["WEB-DL"], video_codec="HEVC", audio_codec="AAC", audio_channels="2.0")
    unknown = ResourceAttributes(resolution="2160p", sources=["WEB-DL"], video_codec="HEVC", audio_codec="AAC")
    surround = ResourceAttributes(resolution="2160p", sources=["WEB-DL"], video_codec="HEVC", audio_codec="AAC", audio_channels="5.1")

    assert quality_sort_key(stereo, QualityRankingConfig()) == quality_sort_key(unknown, QualityRankingConfig())
    assert quality_sort_key(surround, QualityRankingConfig()) > quality_sort_key(unknown, QualityRankingConfig())
