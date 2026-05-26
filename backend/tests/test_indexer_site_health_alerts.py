from app.schemas.runtime.indexer_site_health import IndexerSiteHealthStatus
from app.services.config import indexer_client_settings
from app.services.config.indexer_client_settings import IndexerSiteHealthState


class _FakeIndexerSiteHealthRepository:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], IndexerSiteHealthStatus] = {}

    def find_one(self, indexer_id: str, site_id: str) -> IndexerSiteHealthStatus | None:
        return self.records.get((indexer_id, site_id))

    def upsert(self, status: IndexerSiteHealthStatus) -> IndexerSiteHealthStatus:
        self.records[(status.indexer_id, status.site_id)] = status
        return status

    def list_by_indexer(self, indexer_id: str) -> list[IndexerSiteHealthStatus]:
        return [
            status
            for (stored_indexer_id, _), status in self.records.items()
            if stored_indexer_id == indexer_id
        ]

    def get_all(self) -> list[IndexerSiteHealthStatus]:
        return list(self.records.values())


def test_indexer_site_failure_refreshes_alert_after_threshold(monkeypatch):
    raised = []
    monkeypatch.setattr(indexer_client_settings, "raise_indexer_site_alert", lambda **kwargs: raised.append(kwargs))
    monkeypatch.setattr(indexer_client_settings, "resolve_indexer_site_alert", lambda *_args, **_kwargs: None)
    state = IndexerSiteHealthState(repo=_FakeIndexerSiteHealthRepository())

    for failure_count in range(1, 5):
        status = state.record_failure(
            indexer_id="jackett",
            indexer_name="Jackett",
            site_id="audiences",
            site_name="Audiences",
            error_message=f"failure {failure_count}",
        )

    assert status.consecutive_failures == 4
    assert status.notify_pending is True
    assert len(raised) == 2
    assert raised[0]["indexer_id"] == "jackett"
    assert raised[0]["site_id"] == "audiences"
    assert raised[0]["consecutive_failures"] == 3
    assert raised[0]["error"] == "failure 3"
    assert raised[1]["consecutive_failures"] == 4
    assert raised[1]["error"] == "failure 4"


def test_indexer_site_success_resolves_alert_and_allows_future_threshold_alert(monkeypatch):
    raised = []
    resolved = []
    monkeypatch.setattr(indexer_client_settings, "raise_indexer_site_alert", lambda **kwargs: raised.append(kwargs))
    monkeypatch.setattr(indexer_client_settings, "resolve_indexer_site_alert", lambda *args: resolved.append(args))
    state = IndexerSiteHealthState(repo=_FakeIndexerSiteHealthRepository())

    for _ in range(3):
        state.record_failure(
            indexer_id="jackett",
            indexer_name="Jackett",
            site_id="audiences",
            site_name="Audiences",
            error_message="login failed",
        )

    recovered = state.record_success(
        indexer_id="jackett",
        indexer_name="Jackett",
        site_id="audiences",
        site_name="Audiences",
    )

    for _ in range(3):
        state.record_failure(
            indexer_id="jackett",
            indexer_name="Jackett",
            site_id="audiences",
            site_name="Audiences",
            error_message="login failed again",
        )

    assert recovered.status == "healthy"
    assert recovered.consecutive_failures == 0
    assert recovered.notify_pending is False
    assert resolved == [("jackett", "audiences")]
    assert len(raised) == 2
    assert raised[0]["consecutive_failures"] == 3
    assert raised[1]["consecutive_failures"] == 3
