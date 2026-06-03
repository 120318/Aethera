"""Prune subscription run audit events.

Revision ID: 0006_prune_subscription_run_events
Revises: 0005_prune_operation_events
Create Date: 2026-06-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_prune_subscription_run_events"
down_revision = "0005_prune_operation_events"
branch_labels = None
depends_on = None


SUBSCRIPTION_RUN_EVENT_TYPES = (
    "subscription.run.completed",
    "subscription.run.failed",
)


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    if not _has_table("events"):
        return
    bind = op.get_bind()
    params = {f"type_{index}": value for index, value in enumerate(SUBSCRIPTION_RUN_EVENT_TYPES)}
    placeholders = ", ".join(f":type_{index}" for index in range(len(SUBSCRIPTION_RUN_EVENT_TYPES)))
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
