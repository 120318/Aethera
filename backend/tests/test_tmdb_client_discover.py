from __future__ import annotations

import asyncio

import pytest

from app.clients.tmdb import TMDBClient
from app.schemas.config import TMDBConfig
from app.schemas.integration.media.tmdb import TMDBReleaseDatesResponse, TMDBSeasonDetails

pytestmark = pytest.mark.asyncio


class FakeTMDBResponse:
    status_code = 200

    def __init__(self, page: int) -> None:
        self.page = page

    def json(self) -> dict:
        base = (self.page - 1) * 20
        return {
            "page": self.page,
            "total_pages": 3,
            "total_results": 60,
            "results": [
                {
                    "id": base + index + 1,
                    "title": f"Movie {base + index + 1}",
                    "release_date": "2024-01-01",
                    "vote_average": 7.5,
                    "vote_count": 100,
                    "genre_ids": [18],
                    "original_language": "en",
                }
                for index in range(20)
            ],
        }


async def test_tmdb_discover_items_fetches_enough_pages(monkeypatch) -> None:
    client = TMDBClient(TMDBConfig(api_key="tmdb-key"))
    requested_pages: list[int] = []

    async def fake_get_response(operation: str, url: str, params: dict | None = None, *, timeout: float | None = None):
        assert operation.startswith("discover:movie_popular")
        assert url.endswith("/movie/popular")
        assert timeout is None
        assert params is not None
        requested_pages.append(params["page"])
        return FakeTMDBResponse(params["page"])

    monkeypatch.setattr(client, "_get_response", fake_get_response)

    items = await client.discover_items("movie_popular", start=0, count=30)

    assert sorted(requested_pages) == [1, 2]
    assert len(items) == 30
    assert items[0].provider_id == "1"
    assert items[-1].provider_id == "30"


async def test_tmdb_discover_items_applies_start_offset(monkeypatch) -> None:
    client = TMDBClient(TMDBConfig(api_key="tmdb-key"))
    requested_pages: list[int] = []

    async def fake_get_response(operation: str, url: str, params: dict | None = None, *, timeout: float | None = None):
        requested_pages.append((params or {})["page"])
        return FakeTMDBResponse((params or {})["page"])

    monkeypatch.setattr(client, "_get_response", fake_get_response)

    items = await client.discover_items("movie_popular", start=15, count=10)

    assert sorted(requested_pages) == [1, 2]
    assert [item.provider_id for item in items] == [str(index) for index in range(16, 26)]


async def test_tmdb_season_details_fetches_fallback_language_in_parallel(monkeypatch) -> None:
    client = TMDBClient(TMDBConfig(api_key="tmdb-key"))
    started: list[str] = []
    release = asyncio.Event()

    async def fake_get_season_details_raw(tmdb_id: int, season_number: int, *, language: str):
        started.append(language)
        if len(started) == 2:
            release.set()
        await release.wait()
        if language == "zh-CN":
            return TMDBSeasonDetails(id=1, season_number=1, name="第一季", episodes=[]), False
        return TMDBSeasonDetails(
            id=1,
            season_number=1,
            name="Season 1",
            overview="Fallback overview",
            episodes=[],
        ), False

    monkeypatch.setattr(client, "_get_season_details_raw", fake_get_season_details_raw)

    season = await client.get_season_details_with_fallback(279388, 1)

    assert sorted(started) == ["en-US", "zh-CN"]
    assert season is not None
    assert season.name == "第一季"
    assert season.overview == "Fallback overview"


async def test_tmdb_release_dates_preserve_all_release_detail_fields() -> None:
    client = TMDBClient(TMDBConfig(api_key="tmdb-key"))
    payload = TMDBReleaseDatesResponse.model_validate(
        {
            "id": 872585,
            "results": [
                {
                    "iso_3166_1": "US",
                    "release_dates": [
                        {
                            "type": 5,
                            "release_date": "2023-11-21T00:00:00.000Z",
                            "certification": "R",
                            "note": "Blu-ray",
                            "descriptors": ["violence"],
                            "iso_639_1": "en",
                        }
                    ],
                }
            ],
        }
    )

    regions = client._to_release_regions(payload)

    assert regions[0].iso_3166_1 == "US"
    assert regions[0].release_dates[0].type == 5
    assert regions[0].release_dates[0].release_date == "2023-11-21T00:00:00.000Z"
    assert regions[0].release_dates[0].certification == "R"
    assert regions[0].release_dates[0].note == "Blu-ray"
    assert regions[0].release_dates[0].descriptors == ["violence"]
    assert regions[0].release_dates[0].iso_639_1 == "en"
