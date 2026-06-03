"""Drop alerts storage.

Revision ID: 0003_drop_alerts
Revises: 0002_scope_douban_identity
Create Date: 2026-05-31
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_drop_alerts"
down_revision = "0002_scope_douban_identity"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    if _has_table("alerts"):
        op.drop_table("alerts")


def downgrade() -> None:
    if _has_table("alerts"):
        return
    op.create_table(
        "alerts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("message_key", sa.Text(), nullable=False),
        sa.Column("message_params_json", sa.JSON(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("media_id", sa.Text(), nullable=True),
        sa.Column("media_season_number", sa.Integer(), nullable=True),
        sa.Column("media_title", sa.Text(), nullable=True),
        sa.Column("media_year", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Text(), nullable=True),
        sa.Column("action_id", sa.Text(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.Text(), nullable=False),
        sa.Column("acknowledged_at", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("fingerprint", name="uq_alerts_fingerprint"),
    )
    op.create_index("ix_alerts_fingerprint", "alerts", ["fingerprint"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_category", "alerts", ["category"])
    op.create_index("ix_alerts_target_type", "alerts", ["target_type"])
    op.create_index("ix_alerts_target_id", "alerts", ["target_id"])
    op.create_index("ix_alerts_media_id", "alerts", ["media_id"])
    op.create_index("ix_alerts_media_season_number", "alerts", ["media_season_number"])
    op.create_index("ix_alerts_task_id", "alerts", ["task_id"])
    op.create_index("ix_alerts_action_id", "alerts", ["action_id"])
    op.create_index("ix_alerts_first_seen_at", "alerts", ["first_seen_at"])
    op.create_index("ix_alerts_last_seen_at", "alerts", ["last_seen_at"])
    op.create_index("ix_alerts_acknowledged_at", "alerts", ["acknowledged_at"])
    op.create_index("ix_alerts_resolved_at", "alerts", ["resolved_at"])
    op.create_index("ix_alerts_updated_at", "alerts", ["updated_at"])
    op.create_index("ix_alerts_status_ack_severity", "alerts", ["status", "acknowledged_at", "severity"])
    op.create_index("ix_alerts_target", "alerts", ["target_type", "target_id"])
