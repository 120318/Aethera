from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.schemas.domain.media import MediaSimpleInfo
from app.schemas.domain.media_download_config import EffectiveMediaDownloadConfig
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.schemas.media_id import MediaID
from app.services.application.views.resource_search import resource_search_result_view_service

pytestmark = [pytest.mark.drift, pytest.mark.health]


def _result(*, matched_by_id: bool = False) -> ResourceSearchResult:
    return ResourceSearchResult(
        id="raw-1",
        title="Some Show S01E01 1080p",
        site="hhanclub",
        category="tv",
        size="1 GB",
        seeders=10,
        leechers=0,
        publish_date=datetime.now(),
        download_url="https://example.com/download",
        detail_url="https://example.com/detail",
        result_id="result-1",
        matched_by_id=matched_by_id,
    )


@pytest.mark.asyncio
async def test_resource_search_view_reads_latest_cache_without_executing_search(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    cached_result = _result()
    search_media = AsyncMock()
    monkeypatch.setattr(
        "app.services.application.views.resource_search.service.media_service.simple_info",
        AsyncMock(
            return_value=MediaSimpleInfo(
                media_id=media_id,
                title="Some Show",
                year=2024,
                media_type=MediaType.tv,
                season_number=1,
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_search.service.resource_search_service.get_latest_media_cached_results",
        lambda requested_media_id, season_number=None: [cached_result],
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_search.service.resource_search_service.search_media",
        search_media,
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_search.service.subscription_download_config_service.find_by_media_id",
        AsyncMock(return_value=None),
    )

    response = await resource_search_result_view_service.get_latest_results(
        media_id=media_id,
        season_number=1,
    )

    assert response.results is not None
    assert response.results[0].resource.result_id == "result-1"
    search_media.assert_not_called()


@pytest.mark.asyncio
async def test_resource_search_view_marks_unmatched_rule_without_mutating_cached_result(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    cached_result = _result(matched_by_id=False)
    monkeypatch.setattr(
        "app.services.application.views.resource_search.service.media_service.simple_info",
        AsyncMock(
            return_value=MediaSimpleInfo(
                media_id=media_id,
                title="Some Show",
                year=2024,
                media_type=MediaType.tv,
                season_number=1,
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_search.service.resource_search_service.get_latest_media_cached_results",
        lambda requested_media_id, season_number=None: [cached_result],
    )
    monkeypatch.setattr(
        "app.services.application.views.resource_search.service.subscription_download_config_service.find_by_media_id",
        AsyncMock(
            return_value=EffectiveMediaDownloadConfig(
                media_id=media_id,
                season_number=1,
                unmatched_rules=[SubscriptionUnmatchedRule(sites=["hhanclub"], pattern=r"S01E01")],
            )
        ),
    )

    response = await resource_search_result_view_service.get_latest_results(
        media_id=media_id,
        season_number=1,
    )

    assert response.results is not None
    assert response.results[0].resource.matched_unmatched_rule is True
    assert cached_result.matched_unmatched_rule is False
