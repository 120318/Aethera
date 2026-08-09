"""Store scoped Douban overview metadata.

Revision ID: 0007_scope_douban_overview
Revises: 0006_indexer_event_reopen
Create Date: 2026-08-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_scope_douban_overview"
down_revision = "0006_indexer_event_reopen"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_table("media_profile_scopes") or _has_column("media_profile_scopes", "douban_overview"):
        return
    op.add_column("media_profile_scopes", sa.Column("douban_overview", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_table("media_profile_scopes") and _has_column("media_profile_scopes", "douban_overview"):
        op.drop_column("media_profile_scopes", "douban_overview")
