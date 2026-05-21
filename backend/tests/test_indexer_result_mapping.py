from datetime import datetime
from types import SimpleNamespace

from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.resource_search import MediaSearchQuery, ResourceSearchResult
from app.schemas.media_id import MediaID
from app.services.domain.resource.search_policy import ResourceSearchResultPolicy


class ResultMapper(ResourceSearchResultPolicy):
    def filter_by_min_seeders(self, client, results: list[ResourceSearchResult]) -> list[ResourceSearchResult]:
        min_seeders = client.config.min_seeders or 0
        if min_seeders <= 0:
            return results
        return [item for item in results if (item.seeders or 0) >= min_seeders]

def _result(
    title: str,
    *,
    result_id: str,
    seeders: int = 10,
    source_doubanid: str | None = None,
    source_imdbid: str | None = None,
    matched_by_id: bool = False,
) -> ResourceSearchResult:
    return ResourceSearchResult(
        id=result_id,
        title=title,
        site="site-a",
        category="movie",
        size="1024",
        seeders=seeders,
        leechers=0,
        publish_date=datetime(2026, 1, 1),
        download_url=f"https://example.test/{result_id}.torrent",
        detail_url=f"https://example.test/{result_id}",
        result_id=result_id,
        source_doubanid=source_doubanid,
        source_imdbid=source_imdbid,
        matched_by_id=matched_by_id,
    )


def _query() -> MediaSearchQuery:
    return MediaSearchQuery(
        media=MediaExecutionSnapshot(
            media_id=MediaID.parse("douban:movie:12345"),
            title="Example Movie",
            year=2026,
            imdb_id="tt1234567",
        ),
    )


def test_filter_media_results_drops_id_mismatch_results():
    mapper = ResultMapper()

    filtered = mapper.filter_media_results([
        _result("wrong", result_id="r1", source_doubanid="99999"),
        _result("right", result_id="r2", source_imdbid="TT1234567"),
        _result("no-id", result_id="r3"),
    ], _query())

    assert [item.result_id for item in filtered] == ["r2", "r3"]
    assert filtered[0].matched_by_id is True
    assert filtered[1].matched_by_id is False


def test_filter_media_results_uses_explicit_douban_id_for_tmdb_media_id():
    mapper = ResultMapper()
    query = MediaSearchQuery(
        media=MediaExecutionSnapshot(
            media_id=MediaID.parse("tmdb:movie:12345"),
            title="Example Movie",
            year=2026,
            imdb_id="tt1234567",
            douban_id="36513446",
        ),
    )

    filtered = mapper.filter_media_results([
        _result("wrong", result_id="r1", source_doubanid="99999"),
        _result("right", result_id="r2", source_doubanid="36513446"),
    ], query)

    assert [item.result_id for item in filtered] == ["r2"]
    assert filtered[0].matched_by_id is True


def test_filter_media_results_keeps_external_id_results_when_query_has_no_expected_id():
    mapper = ResultMapper()
    query = MediaSearchQuery(
        media=MediaExecutionSnapshot(
            media_id=MediaID.parse("tmdb:movie:12345"),
            title="Example Movie",
            year=2026,
        ),
    )

    filtered = mapper.filter_media_results([
        _result("imdb-only", result_id="r1", source_imdbid="tt9999999"),
        _result("douban-only", result_id="r2", source_doubanid="99999"),
    ], query)

    assert [item.result_id for item in filtered] == ["r1", "r2"]
    assert all(item.matched_by_id is False for item in filtered)


def test_merge_results_keeps_first_order_but_promotes_id_matched_duplicate():
    mapper = ResultMapper()
    title = "Example.Movie.2026.1080p.WEB-DL"
    query_result = _result(title, result_id="query", matched_by_id=False)
    id_result = _result(title, result_id="id", source_imdbid="tt1234567", matched_by_id=True)

    merged = mapper.merge_results([query_result], [id_result])

    assert len(merged) == 1
    assert merged[0].result_id == "id"
    assert merged[0].matched_by_id is True
    assert merged[0].source_imdbid == "tt1234567"


def test_filter_by_min_seeders_uses_client_config_threshold():
    mapper = ResultMapper()
    client = SimpleNamespace(config=SimpleNamespace(min_seeders=5))

    filtered = mapper.filter_by_min_seeders(client, [
        _result("low", result_id="low", seeders=4),
        _result("enough", result_id="enough", seeders=5),
    ])

    assert [item.result_id for item in filtered] == ["enough"]
