"""Track uninterrupted indexer failure windows.

Revision ID: 0008_indexer_failure_window
Revises: 0007_scope_douban_overview
Create Date: 2026-09-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_indexer_failure_window"
down_revision = "0007_scope_douban_overview"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_table("indexer_site_health") or _has_column("indexer_site_health", "first_failure_at"):
        return
    op.add_column("indexer_site_health", sa.Column("first_failure_at", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE indexer_site_health
        SET first_failure_at = CASE
            WHEN notify_pending = 1 THEN COALESCE(last_notified_at, last_failure_at, checked_at)
            ELSE COALESCE(last_failure_at, checked_at)
        END
        WHERE status = 'unhealthy'
        """
    )


def downgrade() -> None:
    if _has_table("indexer_site_health") and _has_column("indexer_site_health", "first_failure_at"):
        op.drop_column("indexer_site_health", "first_failure_at")
