"""Add event acknowledgement storage.

Revision ID: 0004_event_acknowledgements
Revises: 0003_drop_alerts
Create Date: 2026-05-31
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_event_acknowledgements"
down_revision = "0003_drop_alerts"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    if _has_table("event_acknowledgements"):
        return
    op.create_table(
        "event_acknowledgements",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("acknowledged_at", sa.Text(), nullable=False),
    )
    op.create_index("ix_event_acknowledgements_acknowledged_at", "event_acknowledgements", ["acknowledged_at"])


def downgrade() -> None:
    if not _has_table("event_acknowledgements"):
        return
    op.drop_index("ix_event_acknowledgements_acknowledged_at", table_name="event_acknowledgements")
    op.drop_table("event_acknowledgements")
