from datetime import datetime, timedelta

from app.db.repositories.action_repository import ActionRepository
from app.db.repositories.event_dispatch_repository import EventDispatchRepository
from app.db.repositories.event_repository import EventRepository
from app.db.sql.models import ActionORM, EventDispatchORM, EventORM
from app.db.sql.session import SessionLocal
from app.schemas.persistence.event_dispatch import EventDispatchStatus


def _iso(minutes: int) -> str:
    return (datetime(2026, 1, 1, 0, 0, 0) + timedelta(minutes=minutes)).isoformat()


def _insert_action(session, item_id: str, minutes: int) -> None:
    session.add(
        ActionORM(
            id=item_id,
            ts=_iso(minutes),
            started_at=None,
            finished_at=None,
            kind="scheduler",
            action_name="test.action",
            status="completed",
            actor="system",
            trigger="scheduler",
            source="scheduler",
            target_type=None,
            target_id=None,
            media_id=None,
            task_id=None,
            subscription_id=None,
            correlation_id=None,
            message_key=None,
            message_params_json={},
            media_season_number=None,
            media_title=None,
            media_year=None,
            error=None,
            search_text="",
            duration_ms=None,
            meta_json={},
        )
    )


def _insert_event(session, item_id: str, minutes: int) -> None:
    session.add(
        EventORM(
            id=item_id,
            ts=_iso(minutes),
            type="test.event",
            level="info",
            message_key=None,
            message_params_json={},
            search_text="",
            media_id=None,
            media_season_number=None,
            media_title=None,
            media_year=None,
            task_id=None,
            subscription_id=None,
            actor=None,
            source=None,
            addon_id=None,
            addon_name=None,
            entities_json=[],
            meta_json={},
            correlation_id=None,
            action_id=None,
        )
    )


def _insert_dispatch(session, item_id: str, minutes: int, status: EventDispatchStatus) -> None:
    session.add(
        EventDispatchORM(
            id=item_id,
            event_id=f"event-{item_id}",
            consumer_name="consumer",
            status=status.value,
            attempts=1,
            max_attempts=3,
            available_at=_iso(minutes),
            error=None,
            created_at=_iso(minutes),
            started_at=None,
            finished_at=_iso(minutes) if status != EventDispatchStatus.QUEUED else None,
        )
    )


def test_action_repository_prunes_oldest_records_by_limit():
    with SessionLocal() as session:
        session.query(ActionORM).delete()
        for index in range(4):
            _insert_action(session, f"action-{index}", index)
        session.commit()

    removed = ActionRepository().prune_to_limit(2)

    with SessionLocal() as session:
        remaining = [row.id for row in session.query(ActionORM).order_by(ActionORM.ts.asc()).all()]

    assert removed == 2
    assert remaining == ["action-2", "action-3"]


def test_action_repository_skips_prune_when_under_limit():
    with SessionLocal() as session:
        for index in range(2):
            _insert_action(session, f"action-skip-{index}", index)
        session.commit()

    removed = ActionRepository().prune_to_limit(100)

    with SessionLocal() as session:
        remaining = [row.id for row in session.query(ActionORM).filter(ActionORM.id.like("action-skip-%")).order_by(ActionORM.ts.asc()).all()]

    assert removed == 0
    assert remaining == ["action-skip-0", "action-skip-1"]


def test_event_repository_prunes_oldest_records_by_limit():
    with SessionLocal() as session:
        for index in range(4):
            _insert_event(session, f"event-{index}", index)
        session.commit()

    removed = EventRepository().prune_to_limit(2)

    with SessionLocal() as session:
        remaining = [row.id for row in session.query(EventORM).order_by(EventORM.ts.asc()).all()]

    assert removed == 2
    assert remaining == ["event-2", "event-3"]


def test_event_repository_skips_prune_when_under_limit():
    with SessionLocal() as session:
        for index in range(2):
            _insert_event(session, f"event-skip-{index}", index)
        session.commit()

    removed = EventRepository().prune_to_limit(100)

    with SessionLocal() as session:
        remaining = [row.id for row in session.query(EventORM).filter(EventORM.id.like("event-skip-%")).order_by(EventORM.ts.asc()).all()]

    assert removed == 0
    assert remaining == ["event-skip-0", "event-skip-1"]


def test_event_dispatch_repository_prunes_only_terminal_records():
    with SessionLocal() as session:
        _insert_dispatch(session, "dispatch-old", 0, EventDispatchStatus.SUCCEEDED)
        _insert_dispatch(session, "dispatch-new", 1, EventDispatchStatus.FAILED)
        _insert_dispatch(session, "dispatch-queued", 2, EventDispatchStatus.QUEUED)
        _insert_dispatch(session, "dispatch-running", 3, EventDispatchStatus.RUNNING)
        session.commit()

    removed = EventDispatchRepository().prune_terminal_to_limit(1)

    with SessionLocal() as session:
        remaining = [row.id for row in session.query(EventDispatchORM).order_by(EventDispatchORM.created_at.asc()).all()]

    assert removed == 1
    assert remaining == ["dispatch-new", "dispatch-queued", "dispatch-running"]
