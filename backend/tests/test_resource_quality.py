from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.resource_filters import ResourceFilters
from app.services.domain.resource.quality import (
    SOURCE_BLURAY,
    SOURCE_WEB_DL,
    compare_resource_attributes,
    normalize_audio_codec,
    normalize_hdr_type,
    normalize_resolution,
    normalize_source,
    normalize_video_codec,
)


def test_resource_quality_normalizes_common_aliases():
    assert normalize_resolution("4K") == "2160p"
    assert normalize_source("webdl") == SOURCE_WEB_DL
    assert normalize_source("uhd blu ray") == "UHD BluRay"
    assert normalize_video_codec("x265") == "HEVC"
    assert normalize_audio_codec("eac3") == "DDP"
    assert normalize_hdr_type("dv") == "Dolby Vision"
    assert normalize_hdr_type("HDR") == "HDR10"


def test_hdr_models_normalize_hdr_alias_to_hdr10():
    attrs = ResourceAttributes(hdr_type="HDR")
    filters = ResourceFilters(hdr_type=["HDR", "HDR10+", "HDR10"])

    assert attrs.hdr_type == "HDR10"
    assert [str(item) for item in filters.hdr_type] == ["HDR10", "HDR10+"]


def test_resource_quality_compares_canonical_source_order():
    comparison = compare_resource_attributes(
        ResourceAttributes(sources=[SOURCE_BLURAY]),
        ResourceAttributes(sources=[SOURCE_WEB_DL]),
    )

    assert comparison == ("source", -1)


def test_resource_quality_uses_best_source_when_multiple_sources_exist():
    comparison = compare_resource_attributes(
        ResourceAttributes(sources=[SOURCE_WEB_DL]),
        ResourceAttributes(sources=["WEBRip", "REMUX"]),
    )

    assert comparison == ("source", 1)
