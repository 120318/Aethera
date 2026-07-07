from datetime import datetime, timedelta

from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.event import EventLevel
from app.schemas.runtime.indexer_site_health import IndexerSiteHealthStatus
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


def test_indexer_site_failure_marks_notify_pending_after_threshold():
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


def test_indexer_site_failure_emits_unhealthy_event_once_at_threshold(monkeypatch):
    emitted_events = []
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.emit",
        lambda event: emitted_events.append(event),
    )
    state = IndexerSiteHealthState(repo=_FakeIndexerSiteHealthRepository())

    for failure_count in range(1, 5):
        state.record_failure(
            indexer_id="jackett",
            indexer_name="Jackett",
            site_id="audiences",
            site_name="Audiences",
            error_message=f"failure {failure_count}",
        )

    assert len(emitted_events) == 1
    event = emitted_events[0]
    assert event.type == EventTypes.INDEXER_SITE_UNHEALTHY
    assert event.level == EventLevel.warning
    assert event.message_params["indexer_name"] == "Jackett"
    assert event.message_params["site_name"] == "Audiences"
    assert event.message_params["consecutive_failures"] == "3"


def test_indexer_site_success_clears_notify_pending_and_allows_future_threshold():
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
    status = state._get_record("jackett", "audiences")
    assert status is not None
    assert status.consecutive_failures == 3
    assert status.notify_pending is True


def test_indexer_site_unhealthy_event_respects_notification_cooldown(monkeypatch):
    emitted_events = []
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.emit",
        lambda event: emitted_events.append(event),
    )
    state = IndexerSiteHealthState(repo=_FakeIndexerSiteHealthRepository())

    for _ in range(3):
        state.record_failure(
            indexer_id="prowlarr",
            indexer_name="Prowlarr",
            site_id="audiences",
            site_name="Audiences",
            error_message="disabled",
        )
    state.record_success(
        indexer_id="prowlarr",
        indexer_name="Prowlarr",
        site_id="audiences",
        site_name="Audiences",
    )
    for _ in range(3):
        state.record_failure(
            indexer_id="prowlarr",
            indexer_name="Prowlarr",
            site_id="audiences",
            site_name="Audiences",
            error_message="disabled again",
        )

    assert len(emitted_events) == 1


def test_indexer_site_unhealthy_event_repeats_after_notification_cooldown(monkeypatch):
    emitted_events = []
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.emit",
        lambda event: emitted_events.append(event),
    )
    repo = _FakeIndexerSiteHealthRepository()
    state = IndexerSiteHealthState(repo=repo)
    old_notification = datetime.now() - timedelta(hours=25)
    repo.upsert(
        IndexerSiteHealthStatus(
            indexer_id="prowlarr",
            indexer_name="Prowlarr",
            site_id="audiences",
            site_name="Audiences",
            status="unhealthy",
            consecutive_failures=7,
            notify_pending=True,
            last_notified_at=old_notification,
        )
    )

    state.record_failure(
        indexer_id="prowlarr",
        indexer_name="Prowlarr",
        site_id="audiences",
        site_name="Audiences",
        error_message="still disabled",
    )

    assert len(emitted_events) == 1


def test_indexer_site_unhealthy_event_failure_does_not_start_cooldown(monkeypatch):
    attempts = []

    def fake_emit(event):
        attempts.append(event)
        if len(attempts) == 1:
            raise RuntimeError("event store unavailable")

    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.emit",
        fake_emit,
    )
    state = IndexerSiteHealthState(repo=_FakeIndexerSiteHealthRepository())

    for _ in range(3):
        status = state.record_failure(
            indexer_id="prowlarr",
            indexer_name="Prowlarr",
            site_id="audiences",
            site_name="Audiences",
            error_message="disabled",
        )

    assert status.last_notified_at is None

    status = state.record_failure(
        indexer_id="prowlarr",
        indexer_name="Prowlarr",
        site_id="audiences",
        site_name="Audiences",
        error_message="still disabled",
    )

    assert len(attempts) == 2
    assert status.last_notified_at is not None
