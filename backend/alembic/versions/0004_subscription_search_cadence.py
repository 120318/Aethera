"""Track subscription active search cadence.

Revision ID: 0004_subscription_search_cadence
Revises: 0003_notification_center_events
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_subscription_search_cadence"
down_revision = "0003_notification_center_events"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_table("media_subscription_cycles") or _has_column("media_subscription_cycles", "last_search_at"):
        return
    op.add_column("media_subscription_cycles", sa.Column("last_search_at", sa.Float(), nullable=True))
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE media_subscription_cycles
            SET last_search_at = last_checked_at
            WHERE last_checked_at IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    if _has_table("media_subscription_cycles") and _has_column("media_subscription_cycles", "last_search_at"):
        op.drop_column("media_subscription_cycles", "last_search_at")
