from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.resource_search import Resource, ResourceSearchResult
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.services.domain.resource.filtering import matches_unmatched_rules


def _resource(*, matched_by_id: bool, site: str, title: str, description: str = "") -> Resource:
    return Resource(
        resources=ResourceSearchResult(
            id="1",
            title=title,
            description=description,
            site=site,
            category="tv",
            size="1 GB",
            seeders=10,
            leechers=0,
            publish_date="2026-04-20T00:00:00",
            download_url="https://example.com/download",
            result_id="result-1",
            matched_by_id=matched_by_id,
        ),
        attrs=ResourceAttributes(),
    )


def test_unmatched_rule_match_requires_rule_hit_for_id_mismatch_resource():
    resource = _resource(matched_by_id=False, site="hhanclub", title="Some Show S01E01 1080p")
    rules = [SubscriptionUnmatchedRule(sites=["hhanclub"], pattern=r"S01E01")]

    assert matches_unmatched_rules(resource, rules) is True


def test_unmatched_rule_miss_stays_false_for_id_mismatch_resource():
    resource = _resource(matched_by_id=False, site="hhanclub", title="Some Show S01E01 1080p")
    rules = [SubscriptionUnmatchedRule(sites=["hdsky"], pattern=r"S01E01")]

    assert matches_unmatched_rules(resource, rules) is False


def test_id_matched_resource_is_always_treated_as_matched():
    resource = _resource(matched_by_id=True, site="hhanclub", title="Some Show S01E01 1080p")

    assert matches_unmatched_rules(resource, []) is True
