from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app.db.repositories.indexer_site_health_repository import IndexerSiteHealthRepository
from app.db.sql.models import EventAcknowledgementORM, EventORM, IndexerSiteHealthORM
from app.db.sql.session import SessionLocal
from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.event import Event, EventLevel
from app.schemas.runtime.indexer_site_health import IndexerSiteHealthStatus
from app.services.config.indexer_client_settings import IndexerSiteHealthState


class _FakeIndexerSiteHealthRepository:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], IndexerSiteHealthStatus] = {}
        self.acknowledge_failures_remaining = 0
        self.acknowledged_calls: list[str] = []
        self.reopened_calls: list[str] = []
        self.before_acknowledge = None
        self.before_emit = None
        self.before_conditional_upsert = None
        self.emit_failures_remaining = 0

    def find_one(self, indexer_id: str, site_id: str) -> IndexerSiteHealthStatus | None:
        return self.records.get((indexer_id, site_id))

    def upsert(self, status: IndexerSiteHealthStatus) -> IndexerSiteHealthStatus:
        self.records[(status.indexer_id, status.site_id)] = status
        return status

    def upsert_if_current(
        self,
        status: IndexerSiteHealthStatus,
        expected: IndexerSiteHealthStatus | None,
    ) -> tuple[bool, IndexerSiteHealthStatus]:
        if self.before_conditional_upsert:
            callback = self.before_conditional_upsert
            self.before_conditional_upsert = None
            callback()
        current = self.find_one(status.indexer_id, status.site_id)
        matches = current is None if expected is None else current == expected
        if not matches:
            return False, current or status
        return True, self.upsert(status)

    def acknowledge_recovered_unhealthy_events(
        self,
        status: IndexerSiteHealthStatus,
        correlation_id: str,
    ) -> tuple[bool, int]:
        if self.before_acknowledge:
            callback = self.before_acknowledge
            self.before_acknowledge = None
            callback()
        if self.acknowledge_failures_remaining:
            self.acknowledge_failures_remaining -= 1
            raise RuntimeError("event store unavailable")
        current = self.find_one(status.indexer_id, status.site_id)
        if not current or current.status != "healthy" or current.checked_at != status.checked_at:
            return False, 0
        self.acknowledged_calls.append(correlation_id)
        saved = current.model_copy(update={"notify_pending": False})
        self.records[(status.indexer_id, status.site_id)] = saved
        return True, 1

    def emit_unhealthy_event_if_current(
        self,
        status: IndexerSiteHealthStatus,
        _event,
        notified_at: datetime,
    ) -> bool:
        if self.before_emit:
            callback = self.before_emit
            self.before_emit = None
            callback()
        if self.emit_failures_remaining:
            self.emit_failures_remaining -= 1
            raise RuntimeError("event store unavailable")
        current = self.find_one(status.indexer_id, status.site_id)
        if not current or current.status != "unhealthy" or current.checked_at != status.checked_at:
            return False
        saved = current.model_copy(update={"last_notified_at": notified_at})
        self.records[(status.indexer_id, status.site_id)] = saved
        return True

    def reopen_unhealthy_events(
        self,
        status: IndexerSiteHealthStatus,
        correlation_id: str,
        _fallback_event,
    ) -> tuple[bool, int]:
        current = self.find_one(status.indexer_id, status.site_id)
        if not current or current.status != "unhealthy" or current.checked_at != status.checked_at:
            return False, 0
        self.reopened_calls.append(correlation_id)
        saved = current.model_copy(update={"last_reopened_at": status.checked_at})
        self.records[(status.indexer_id, status.site_id)] = saved
        return True, 1

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
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
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
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
        lambda event: emitted_events.append(event),
    )
    repo = _FakeIndexerSiteHealthRepository()
    state = IndexerSiteHealthState(repo=repo)

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
    assert repo.reopened_calls == ["indexer:prowlarr:site:audiences:unhealthy"]


def test_indexer_site_recurring_failure_reopens_event_only_once(monkeypatch):
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
        lambda _event: None,
    )
    repo = _FakeIndexerSiteHealthRepository()
    state = IndexerSiteHealthState(repo=repo)

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
    for _ in range(4):
        state.record_failure(
            indexer_id="prowlarr",
            indexer_name="Prowlarr",
            site_id="audiences",
            site_name="Audiences",
            error_message="disabled again",
        )

    assert repo.reopened_calls == ["indexer:prowlarr:site:audiences:unhealthy"]


def test_indexer_site_success_acknowledges_unhealthy_warning_event(monkeypatch):
    emitted_events = []
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
        lambda event: emitted_events.append(event),
    )
    repo = _FakeIndexerSiteHealthRepository()
    state = IndexerSiteHealthState(repo=repo)

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

    assert len(emitted_events) == 1
    assert repo.acknowledged_calls == ["indexer:prowlarr:site:audiences:unhealthy"]


def test_indexer_site_success_retries_failed_recovery_acknowledgement(monkeypatch):
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
        lambda _event: None,
    )
    repo = _FakeIndexerSiteHealthRepository()
    repo.acknowledge_failures_remaining = 1
    state = IndexerSiteHealthState(repo=repo)

    for _ in range(3):
        state.record_failure(
            indexer_id="prowlarr",
            indexer_name="Prowlarr",
            site_id="audiences",
            site_name="Audiences",
            error_message="disabled",
        )

    first_recovery = state.record_success(
        indexer_id="prowlarr",
        indexer_name="Prowlarr",
        site_id="audiences",
        site_name="Audiences",
    )
    second_recovery = state.record_success(
        indexer_id="prowlarr",
        indexer_name="Prowlarr",
        site_id="audiences",
        site_name="Audiences",
    )

    assert first_recovery.notify_pending is True
    assert second_recovery.notify_pending is False
    assert repo.acknowledged_calls == ["indexer:prowlarr:site:audiences:unhealthy"]


def test_indexer_site_success_does_not_acknowledge_after_concurrent_failure(monkeypatch):
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
        lambda _event: None,
    )
    repo = _FakeIndexerSiteHealthRepository()
    state = IndexerSiteHealthState(repo=repo)

    for _ in range(3):
        state.record_failure(
            indexer_id="prowlarr",
            indexer_name="Prowlarr",
            site_id="audiences",
            site_name="Audiences",
            error_message="disabled",
        )

    def write_concurrent_failure():
        current = repo.find_one("prowlarr", "audiences")
        assert current is not None
        repo.upsert(
            current.model_copy(
                update={
                    "status": "unhealthy",
                    "checked_at": datetime.now() + timedelta(seconds=1),
                    "notify_pending": True,
                }
            )
        )

    repo.before_acknowledge = write_concurrent_failure
    recovered = state.record_success(
        indexer_id="prowlarr",
        indexer_name="Prowlarr",
        site_id="audiences",
        site_name="Audiences",
    )

    assert recovered.status == "unhealthy"
    assert recovered.notify_pending is True
    assert repo.acknowledged_calls == []


def test_indexer_site_success_does_not_overwrite_failure_committed_after_read(monkeypatch):
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
        lambda _event: None,
    )
    repo = _FakeIndexerSiteHealthRepository()
    state = IndexerSiteHealthState(repo=repo)

    for _ in range(3):
        state.record_failure(
            indexer_id="prowlarr",
            indexer_name="Prowlarr",
            site_id="audiences",
            site_name="Audiences",
            error_message="disabled",
        )

    def write_newer_failure():
        current = repo.find_one("prowlarr", "audiences")
        assert current is not None
        repo.upsert(
            current.model_copy(
                update={
                    "checked_at": datetime.now() + timedelta(seconds=1),
                    "consecutive_failures": current.consecutive_failures + 1,
                    "last_error_message": "newer failure",
                    "notify_pending": True,
                }
            )
        )

    repo.before_conditional_upsert = write_newer_failure
    recovered = state.record_success(
        indexer_id="prowlarr",
        indexer_name="Prowlarr",
        site_id="audiences",
        site_name="Audiences",
    )

    assert recovered.status == "unhealthy"
    assert recovered.consecutive_failures == 4
    assert recovered.last_error_message == "newer failure"
    assert repo.acknowledged_calls == []


def test_indexer_site_failure_recalculates_after_concurrent_failure(monkeypatch):
    dispatched_events = []
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
        lambda event: dispatched_events.append(event),
    )
    repo = _FakeIndexerSiteHealthRepository()
    state = IndexerSiteHealthState(repo=repo)
    state.record_failure(
        indexer_id="prowlarr",
        indexer_name="Prowlarr",
        site_id="audiences",
        site_name="Audiences",
        error_message="first failure",
    )

    def write_concurrent_failure():
        current = repo.find_one("prowlarr", "audiences")
        assert current is not None
        concurrent_at = datetime.now() + timedelta(seconds=1)
        repo.upsert(
            current.model_copy(
                update={
                    "checked_at": concurrent_at,
                    "last_failure_at": concurrent_at,
                    "consecutive_failures": current.consecutive_failures + 1,
                    "last_error_message": "concurrent failure",
                }
            )
        )

    repo.before_conditional_upsert = write_concurrent_failure
    saved = state.record_failure(
        indexer_id="prowlarr",
        indexer_name="Prowlarr",
        site_id="audiences",
        site_name="Audiences",
        error_message="third failure",
    )

    assert saved.consecutive_failures == 3
    assert saved.notify_pending is True
    assert len(dispatched_events) == 1


def test_indexer_site_failure_recalculates_after_notification_marker_changes(monkeypatch):
    dispatched_events = []
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
        lambda event: dispatched_events.append(event),
    )
    repo = _FakeIndexerSiteHealthRepository()
    state = IndexerSiteHealthState(repo=repo)
    for _ in range(2):
        state.record_failure(
            indexer_id="prowlarr",
            indexer_name="Prowlarr",
            site_id="audiences",
            site_name="Audiences",
            error_message="disabled",
        )

    notified_at = datetime.now()

    def write_notification_marker():
        current = repo.find_one("prowlarr", "audiences")
        assert current is not None
        repo.upsert(current.model_copy(update={"last_notified_at": notified_at}))

    repo.before_conditional_upsert = write_notification_marker
    saved = state.record_failure(
        indexer_id="prowlarr",
        indexer_name="Prowlarr",
        site_id="audiences",
        site_name="Audiences",
        error_message="third failure",
    )

    assert saved.consecutive_failures == 3
    assert saved.last_notified_at == notified_at
    assert dispatched_events == []


def test_indexer_site_failure_does_not_emit_after_concurrent_recovery(monkeypatch):
    dispatched_events = []
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
        lambda event: dispatched_events.append(event),
    )
    repo = _FakeIndexerSiteHealthRepository()
    state = IndexerSiteHealthState(repo=repo)

    def write_concurrent_recovery():
        current = repo.find_one("prowlarr", "audiences")
        assert current is not None
        repo.upsert(
            current.model_copy(
                update={
                    "status": "healthy",
                    "checked_at": datetime.now() + timedelta(seconds=1),
                    "consecutive_failures": 0,
                    "notify_pending": False,
                }
            )
        )

    repo.before_emit = write_concurrent_recovery
    for _ in range(3):
        status = state.record_failure(
            indexer_id="prowlarr",
            indexer_name="Prowlarr",
            site_id="audiences",
            site_name="Audiences",
            error_message="disabled",
        )

    assert status.status == "healthy"
    assert status.notify_pending is False
    assert status.last_notified_at is None
    assert dispatched_events == []


def test_reopen_unhealthy_events_reopens_only_latest_matching_event():
    repo = IndexerSiteHealthRepository()
    checked_at = datetime.now()
    status = IndexerSiteHealthStatus(
        indexer_id="prowlarr",
        indexer_name="Prowlarr",
        site_id="audiences",
        site_name="Audiences",
        status="unhealthy",
        checked_at=checked_at,
        consecutive_failures=3,
        notify_pending=True,
    )
    repo.upsert(status)
    correlation_id = "indexer:prowlarr:site:audiences:unhealthy"
    with SessionLocal.begin() as session:
        session.add_all(
            [
                EventORM(
                    id="indexer-old-warning",
                    ts="2026-08-01T00:00:00",
                    type=EventTypes.INDEXER_SITE_UNHEALTHY.value,
                    level=EventLevel.warning.value,
                    message_params_json={},
                    search_text="",
                    entities_json=[],
                    meta_json={},
                    correlation_id=correlation_id,
                ),
                EventORM(
                    id="indexer-current-warning",
                    ts="2026-08-02T00:00:00",
                    type=EventTypes.INDEXER_SITE_UNHEALTHY.value,
                    level=EventLevel.warning.value,
                    message_params_json={},
                    search_text="",
                    entities_json=[],
                    meta_json={},
                    correlation_id=correlation_id,
                ),
                EventAcknowledgementORM(
                    event_id="indexer-old-warning",
                    acknowledged_at="2026-08-03T00:00:00",
                ),
                EventAcknowledgementORM(
                    event_id="indexer-current-warning",
                    acknowledged_at="2026-08-03T00:00:00",
                ),
            ]
        )

    fallback_event = Event(
        id="indexer-fallback-warning",
        type=EventTypes.INDEXER_SITE_UNHEALTHY,
        level=EventLevel.warning,
        correlation_id=correlation_id,
    )
    applied, reopened_count = repo.reopen_unhealthy_events(
        status,
        correlation_id,
        fallback_event,
    )

    with SessionLocal() as session:
        acknowledged_ids = set(session.execute(select(EventAcknowledgementORM.event_id)).scalars().all())

    assert applied is True
    assert reopened_count == 1
    assert acknowledged_ids == {"indexer-old-warning"}
    saved = repo.find_one("prowlarr", "audiences")
    assert saved is not None
    assert saved.last_reopened_at == checked_at
    with SessionLocal.begin() as session:
        session.execute(
            delete(EventAcknowledgementORM).where(
                EventAcknowledgementORM.event_id.in_([
                    "indexer-old-warning",
                    "indexer-current-warning",
                ])
            )
        )
        session.execute(
            delete(EventORM).where(
                EventORM.id.in_([
                    "indexer-old-warning",
                    "indexer-current-warning",
                    "indexer-fallback-warning",
                ])
            )
        )


def test_reopen_unhealthy_events_creates_warning_when_history_was_pruned():
    repo = IndexerSiteHealthRepository()
    checked_at = datetime.now()
    status = IndexerSiteHealthStatus(
        indexer_id="pruned-indexer",
        site_id="pruned-site",
        status="unhealthy",
        checked_at=checked_at,
        consecutive_failures=3,
        notify_pending=True,
    )
    repo.upsert(status)
    correlation_id = "indexer:pruned-indexer:site:pruned-site:unhealthy"
    fallback_event = Event(
        id="pruned-indexer-warning",
        type=EventTypes.INDEXER_SITE_UNHEALTHY,
        level=EventLevel.warning,
        correlation_id=correlation_id,
    )

    applied, reopened_count = repo.reopen_unhealthy_events(
        status,
        correlation_id,
        fallback_event,
    )
    saved = repo.find_one(status.indexer_id, status.site_id)

    with SessionLocal.begin() as session:
        persisted_event = session.get(EventORM, fallback_event.id)
        session.execute(delete(EventORM).where(EventORM.id == fallback_event.id))
        session.execute(
            delete(IndexerSiteHealthORM).where(
                IndexerSiteHealthORM.indexer_id == status.indexer_id,
                IndexerSiteHealthORM.site_id == status.site_id,
            )
        )

    assert applied is True
    assert reopened_count == 1
    assert persisted_event is not None
    assert saved is not None
    assert saved.last_reopened_at == checked_at


def test_emit_unhealthy_event_rejects_stale_failure_without_inserting_event():
    repo = IndexerSiteHealthRepository()
    checked_at = datetime.now()
    stale_failure = IndexerSiteHealthStatus(
        indexer_id="atomic-indexer",
        site_id="atomic-site",
        status="unhealthy",
        checked_at=checked_at,
        consecutive_failures=3,
        notify_pending=True,
    )
    repo.upsert(
        stale_failure.model_copy(
            update={
                "status": "healthy",
                "checked_at": checked_at + timedelta(seconds=1),
                "consecutive_failures": 0,
                "notify_pending": False,
            }
        )
    )
    event = Event(
        id="stale-indexer-warning",
        type=EventTypes.INDEXER_SITE_UNHEALTHY,
        level=EventLevel.warning,
    )

    applied = repo.emit_unhealthy_event_if_current(stale_failure, event, checked_at)

    with SessionLocal.begin() as session:
        persisted_event = session.get(EventORM, event.id)
        session.execute(
            delete(IndexerSiteHealthORM).where(
                IndexerSiteHealthORM.indexer_id == "atomic-indexer",
                IndexerSiteHealthORM.site_id == "atomic-site",
            )
        )

    assert applied is False
    assert persisted_event is None


def test_indexer_site_unhealthy_event_repeats_after_notification_cooldown(monkeypatch):
    emitted_events = []
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
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
    monkeypatch.setattr(
        "app.services.config.indexer_client_settings.event_service.dispatch_persisted_event",
        lambda event: attempts.append(event),
    )
    repo = _FakeIndexerSiteHealthRepository()
    repo.emit_failures_remaining = 1
    state = IndexerSiteHealthState(repo=repo)

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

    assert len(attempts) == 1
    assert status.last_notified_at is not None
