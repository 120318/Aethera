from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.config import Tag
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.services.domain.resource.filtering import (
    compute_quality_upgrade_score_from_attrs,
    compute_preference_score_from_attrs,
    match_filters_against_attrs,
)
from app.services.domain.resource.tags import resolve_display_tags


def test_target_filter_does_not_match_missing_resolution():
    assert not match_filters_against_attrs(
        ResourceAttributes(),
        SubscriptionFilters(resolution=["2160p"]),
    )


def test_target_filter_does_not_match_missing_source():
    assert not match_filters_against_attrs(
        ResourceAttributes(),
        SubscriptionFilters(source=["BluRay"]),
    )


def test_target_filter_does_not_match_missing_codec():
    assert not match_filters_against_attrs(
        ResourceAttributes(),
        SubscriptionFilters(codec=["HEVC"]),
    )


def test_target_filter_matches_present_attributes():
    assert match_filters_against_attrs(
        ResourceAttributes(resolution="2160p", sources=["BluRay"], video_codec="HEVC"),
        SubscriptionFilters(resolution=["2160p"], source=["BluRay"], codec=["HEVC"]),
    )


def test_resource_form_is_scoped_by_resource_kind():
    video_filters = SubscriptionFilters(resource_kind=["video_file"], resource_form=["BluRay Disc", "Video File"])
    disc_filters = SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc", "Video File", "DVD Disc"])

    assert [str(value) for value in video_filters.resource_form] == ["Video File"]
    assert [str(value) for value in disc_filters.resource_form] == ["BluRay Disc", "DVD Disc"]


def test_original_disc_form_does_not_imply_original_disc_kind():
    filters = SubscriptionFilters(resource_form=["BluRay Disc"])

    assert [str(value) for value in filters.resource_kind] == ["video_file"]
    assert filters.resource_form == []
    assert not match_filters_against_attrs(
        ResourceAttributes(resource_form="BluRay Disc"),
        filters,
    )


def test_include_keyword_matches_desc():
    assert match_filters_against_attrs(
        ResourceAttributes(title="Movie.2024.1080p.WEB-DL", desc="杜比全景声"),
        SubscriptionFilters(include_keywords=["杜比全景声"]),
    )


def test_exclude_keyword_matches_desc():
    assert not match_filters_against_attrs(
        ResourceAttributes(title="Movie.2024.1080p.WEB-DL", desc="低码率版本"),
        SubscriptionFilters(exclude_keywords=["低码"]),
    )


def test_tag_include_keyword_matches_desc(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.resource.tags.settings_service.list_tags",
        lambda: [Tag(id="tag-special", name="特效", include_keywords=["特效字幕"])],
    )

    assert match_filters_against_attrs(
        ResourceAttributes(title="Movie.2024.1080p.WEB-DL", desc="内封特效字幕"),
        SubscriptionFilters(tags=["tag-special"]),
    )


def test_tag_exclude_keyword_matches_desc(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.resource.tags.settings_service.list_tags",
        lambda: [Tag(id="tag-clean", name="排除国语", exclude_keywords=["国语配音"])],
    )

    assert not match_filters_against_attrs(
        ResourceAttributes(title="Movie.2024.1080p.WEB-DL", desc="国语配音"),
        SubscriptionFilters(tags=["tag-clean"]),
    )


def test_tag_regex_matches_desc(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.resource.tags.settings_service.list_tags",
        lambda: [Tag(id="tag-imax", name="IMAX", regex="IMAX版")],
    )

    assert match_filters_against_attrs(
        ResourceAttributes(title="Movie.2024.1080p.WEB-DL", desc="IMAX版"),
        SubscriptionFilters(tags=["tag-imax"]),
    )


def test_quality_tag_score_matches_desc(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.resource.tags.settings_service.list_tags",
        lambda: [Tag(id="tag-bilingual", name="双语", include_keywords=["双语字幕"])],
    )

    score, breakdown = compute_preference_score_from_attrs(
        ResourceAttributes(title="Movie.2024.1080p.WEB-DL", desc="双语字幕"),
        QualityProfile(name="default", tag_scores={"tag-bilingual": 30}),
    )

    assert score == 30
    assert [item.id for item in breakdown.tag_scores] == ["tag-bilingual"]


def test_quality_upgrade_score_uses_ranking_dimensions_before_tags():
    profile = QualityProfile(name="default")
    dolby_vision = ResourceAttributes(
        resolution="2160p",
        sources=["WEB-DL"],
        resource_form="Video File",
        hdr_type="Dolby Vision",
        video_codec="HEVC",
        audio_codec="DDP",
        audio_channels="5.1",
    )
    hdr = dolby_vision.model_copy(update={"hdr_type": "HDR"})

    assert compute_quality_upgrade_score_from_attrs(
        dolby_vision,
        profile,
    ) > compute_quality_upgrade_score_from_attrs(hdr, profile)
    assert compute_quality_upgrade_score_from_attrs(dolby_vision, profile) > 0


def test_quality_upgrade_score_tag_score_cannot_cross_quality_dimension(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.resource.tags.settings_service.list_tags",
        lambda: [Tag(id="tag-preferred", name="preferred", include_keywords=["preferred"])],
    )
    profile = QualityProfile(name="default", tag_scores={"tag-preferred": 999_999_999})
    low_with_tag = ResourceAttributes(
        title="Movie.2024.720p.WEB-DL.preferred",
        resolution="720p",
        sources=["WEB-DL"],
        resource_form="Video File",
    )
    high_without_tag = ResourceAttributes(
        title="Movie.2024.1080p.WEB-DL",
        resolution="1080p",
        sources=["WEB-DL"],
        resource_form="Video File",
    )

    assert compute_quality_upgrade_score_from_attrs(
        high_without_tag,
        profile,
    ) > compute_quality_upgrade_score_from_attrs(low_with_tag, profile)


def test_quality_upgrade_score_tag_score_orders_same_quality(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.resource.tags.settings_service.list_tags",
        lambda: [Tag(id="tag-preferred", name="preferred", include_keywords=["preferred"])],
    )
    profile = QualityProfile(name="default", tag_scores={"tag-preferred": 30})
    plain = ResourceAttributes(
        title="Movie.2024.1080p.WEB-DL",
        resolution="1080p",
        sources=["WEB-DL"],
        resource_form="Video File",
    )
    preferred = plain.model_copy(update={"title": "Movie.2024.1080p.WEB-DL.preferred"})

    assert compute_quality_upgrade_score_from_attrs(
        preferred,
        profile,
    ) > compute_quality_upgrade_score_from_attrs(plain, profile)


def test_matching_tag_names_are_resolved_for_display(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.resource.tags.settings_service.list_tags",
        lambda: [
            Tag(id="tag-special", name="特效", include_keywords=["特效字幕"]),
            Tag(id="tag-voice", name="国语", include_keywords=["国语配音"]),
        ],
    )

    tags = resolve_display_tags(
        ResourceAttributes(
            title="Movie.2024.1080p.WEB-DL",
            desc="内封特效字幕",
        )
    )

    assert tags == ["特效"]
