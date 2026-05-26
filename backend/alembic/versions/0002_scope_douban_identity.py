"""Move Douban identity from profile to profile scopes.

Revision ID: 0002_scope_douban_identity
Revises: 0001_initial_schema
Create Date: 2026-05-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_scope_douban_identity"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    return any(index["name"] == index_name for index in sa.inspect(bind).get_indexes(table_name))


def _now_sql() -> str:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return "strftime('%s', 'now')"
    return "EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)"


def _json_empty_array_sql() -> str:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return "'[]'::json"
    return "'[]'"


def upgrade() -> None:
    if _has_table("media_profile_scopes") and _has_table("media_external_mappings"):
        op.execute(
            sa.text(
                """
                UPDATE media_profile_scopes
                SET douban_id = (
                    SELECT media_external_mappings.douban_id
                    FROM media_external_mappings
                    WHERE media_external_mappings.media_id = media_profile_scopes.media_id
                      AND media_external_mappings.season_number = media_profile_scopes.season_number
                      AND media_external_mappings.douban_id IS NOT NULL
                )
                WHERE (douban_id IS NULL OR douban_id = '')
                  AND EXISTS (
                    SELECT 1
                    FROM media_external_mappings
                    WHERE media_external_mappings.media_id = media_profile_scopes.media_id
                      AND media_external_mappings.season_number = media_profile_scopes.season_number
                      AND media_external_mappings.douban_id IS NOT NULL
                  )
                """
            )
        )

        if _has_table("managed_media_profiles"):
            now_sql = _now_sql()
            json_empty_array_sql = _json_empty_array_sql()
            op.execute(
                sa.text(
                    f"""
                    INSERT INTO media_profile_scopes (
                        media_id,
                        season_number,
                        media_type,
                        douban_id,
                        episode_count_override,
                        aired_episode_count,
                        release_dates_json,
                        platforms_json,
                        airings_json,
                        updated_at
                    )
                    SELECT
                        mapping.media_id,
                        mapping.season_number,
                        mapping.media_type,
                        mapping.douban_id,
                        mapping.episode_count_override,
                        0,
                        {json_empty_array_sql},
                        {json_empty_array_sql},
                        {json_empty_array_sql},
                        {now_sql}
                    FROM media_external_mappings AS mapping
                    INNER JOIN managed_media_profiles AS profile
                        ON profile.media_id = mapping.media_id
                    LEFT JOIN media_profile_scopes AS scope
                        ON scope.media_id = mapping.media_id
                       AND scope.season_number = mapping.season_number
                    WHERE scope.media_id IS NULL
                      AND mapping.douban_id IS NOT NULL
                    """
                )
            )

    if _has_table("managed_media_profiles") and "douban_id" in _columns("managed_media_profiles"):
        if _has_index("managed_media_profiles", "ix_managed_media_profiles_douban_id"):
            op.drop_index("ix_managed_media_profiles_douban_id", table_name="managed_media_profiles")
        with op.batch_alter_table("managed_media_profiles") as batch_op:
            batch_op.drop_column("douban_id")


def downgrade() -> None:
    if _has_table("managed_media_profiles") and "douban_id" not in _columns("managed_media_profiles"):
        with op.batch_alter_table("managed_media_profiles") as batch_op:
            batch_op.add_column(sa.Column("douban_id", sa.Text(), nullable=True))
            batch_op.create_index("ix_managed_media_profiles_douban_id", ["douban_id"])

    if (
        _has_table("managed_media_profiles")
        and _has_table("media_profile_scopes")
        and "douban_id" in _columns("managed_media_profiles")
    ):
        op.execute(
            sa.text(
                """
                UPDATE managed_media_profiles
                SET douban_id = (
                    SELECT media_profile_scopes.douban_id
                    FROM media_profile_scopes
                    WHERE media_profile_scopes.media_id = managed_media_profiles.media_id
                      AND media_profile_scopes.season_number = 0
                      AND media_profile_scopes.douban_id IS NOT NULL
                )
                WHERE media_type = 'movie'
                  AND EXISTS (
                    SELECT 1
                    FROM media_profile_scopes
                    WHERE media_profile_scopes.media_id = managed_media_profiles.media_id
                      AND media_profile_scopes.season_number = 0
                      AND media_profile_scopes.douban_id IS NOT NULL
                  )
                """
            )
        )
