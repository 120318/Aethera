"""Track indexer health event reopening.

Revision ID: 0006_indexer_event_reopen
Revises: 0005_indexer_notify_cooldown
Create Date: 2026-08-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_indexer_event_reopen"
down_revision = "0005_indexer_notify_cooldown"
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
    if not _has_table("indexer_site_health") or _has_column("indexer_site_health", "last_reopened_at"):
        return
    op.add_column("indexer_site_health", sa.Column("last_reopened_at", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_table("indexer_site_health") and _has_column("indexer_site_health", "last_reopened_at"):
        op.drop_column("indexer_site_health", "last_reopened_at")
