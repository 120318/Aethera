"""Prune operation-only audit events.

Revision ID: 0005_prune_operation_events
Revises: 0004_event_acknowledgements
Create Date: 2026-06-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_prune_operation_events"
down_revision = "0004_event_acknowledgements"
branch_labels = None
depends_on = None


OPERATION_EVENT_TYPES = (
    "download.started",
    "download.task.downloader_changed",
    "download.task.storage_change_started",
    "download.task.storage_changed",
    "media.import.started",
    "media_server_sync.started",
    "danmu.generate.started",
    "subscription.enabled",
    "subscription.disabled",
    "subscription.ended.manual",
    "follow.enabled",
    "follow.disabled",
    "pilot.episode.queued",
)


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    if not _has_table("events"):
        return
    bind = op.get_bind()
    params = {f"type_{index}": value for index, value in enumerate(OPERATION_EVENT_TYPES)}
    placeholders = ", ".join(f":type_{index}" for index in range(len(OPERATION_EVENT_TYPES)))
    if _has_table("event_dispatches"):
        bind.execute(
            sa.text(
                f"""
                DELETE FROM event_dispatches
                WHERE event_id IN (
                    SELECT id FROM events WHERE type IN ({placeholders})
                )
                """
            ),
            params,
        )
    if _has_table("event_acknowledgements"):
        bind.execute(
            sa.text(
                f"""
                DELETE FROM event_acknowledgements
                WHERE event_id IN (
                    SELECT id FROM events WHERE type IN ({placeholders})
                )
                """
            ),
            params,
        )
    bind.execute(sa.text(f"DELETE FROM events WHERE type IN ({placeholders})"), params)


def downgrade() -> None:
    pass
