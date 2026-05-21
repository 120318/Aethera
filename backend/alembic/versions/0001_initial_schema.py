"""Initial schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op

from app.db.sql.base import Base
from app.db.sql import models  # noqa: F401


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
