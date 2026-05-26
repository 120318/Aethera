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
    profile_columns = _columns("managed_media_profiles") if _has_table("managed_media_profiles") else set()
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
            insert_columns = [
                "media_id",
                "season_number",
                "media_type",
                "douban_id",
                "episode_count_override",
                "aired_episode_count",
                "release_dates_json",
                "platforms_json",
                "airings_json",
                "updated_at",
            ]
            select_columns = [
                "mapping.media_id",
                "mapping.season_number",
                "mapping.media_type",
                "mapping.douban_id",
                "mapping.episode_count_override",
                "0",
                json_empty_array_sql,
                json_empty_array_sql,
                json_empty_array_sql,
                now_sql,
            ]
            if {"douban_vote_average", "douban_rating_count"}.issubset(profile_columns):
                insert_columns.extend(["douban_vote_average", "douban_rating_count"])
                select_columns.extend([
                    "CASE WHEN mapping.media_type = 'movie' THEN profile.douban_vote_average ELSE NULL END",
                    "CASE WHEN mapping.media_type = 'movie' THEN profile.douban_rating_count ELSE NULL END",
                ])
            op.execute(
                sa.text(
                    f"""
                    INSERT INTO media_profile_scopes (
                        {", ".join(insert_columns)}
                    )
                    SELECT
                        {", ".join(select_columns)}
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

    if (
        _has_table("managed_media_profiles")
        and _has_table("media_profile_scopes")
        and {"douban_vote_average", "douban_rating_count"}.issubset(profile_columns)
    ):
        op.execute(
            sa.text(
                """
                UPDATE media_profile_scopes
                SET
                    douban_vote_average = COALESCE(douban_vote_average, (
                        SELECT managed_media_profiles.douban_vote_average
                        FROM managed_media_profiles
                        WHERE managed_media_profiles.media_id = media_profile_scopes.media_id
                    )),
                    douban_rating_count = COALESCE(douban_rating_count, (
                        SELECT managed_media_profiles.douban_rating_count
                        FROM managed_media_profiles
                        WHERE managed_media_profiles.media_id = media_profile_scopes.media_id
                    ))
                WHERE media_type = 'movie'
                  AND season_number = 0
                  AND EXISTS (
                    SELECT 1
                    FROM managed_media_profiles
                    WHERE managed_media_profiles.media_id = media_profile_scopes.media_id
                      AND managed_media_profiles.media_type = 'movie'
                  )
                """
            )
        )

    if _has_table("managed_media_profiles") and "douban_id" in profile_columns:
        if _has_index("managed_media_profiles", "ix_managed_media_profiles_douban_id"):
            op.drop_index("ix_managed_media_profiles_douban_id", table_name="managed_media_profiles")
        with op.batch_alter_table("managed_media_profiles") as batch_op:
            batch_op.drop_column("douban_id")
        profile_columns.remove("douban_id")

    if _has_table("managed_media_profiles"):
        droppable_columns = [
            column
            for column in [
                "rating_count",
                "vote_average",
                "vote_count",
                "rating_source",
                "douban_vote_average",
                "douban_rating_count",
            ]
            if column in profile_columns
        ]
        if droppable_columns:
            with op.batch_alter_table("managed_media_profiles") as batch_op:
                for column in droppable_columns:
                    batch_op.drop_column(column)


def downgrade() -> None:
    profile_columns = _columns("managed_media_profiles") if _has_table("managed_media_profiles") else set()
    if _has_table("managed_media_profiles"):
        restore_columns = [
            ("rating_count", sa.Integer()),
            ("vote_average", sa.Float()),
            ("vote_count", sa.Integer()),
            ("rating_source", sa.Text()),
            ("douban_vote_average", sa.Float()),
            ("douban_rating_count", sa.Integer()),
        ]
        missing = [(name, column_type) for name, column_type in restore_columns if name not in profile_columns]
        if missing:
            with op.batch_alter_table("managed_media_profiles") as batch_op:
                for name, column_type in missing:
                    batch_op.add_column(sa.Column(name, column_type, nullable=True))

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

        if {"douban_vote_average", "douban_rating_count"}.issubset(_columns("managed_media_profiles")):
            op.execute(
                sa.text(
                    """
                    UPDATE managed_media_profiles
                    SET
                        douban_vote_average = (
                            SELECT media_profile_scopes.douban_vote_average
                            FROM media_profile_scopes
                            WHERE media_profile_scopes.media_id = managed_media_profiles.media_id
                              AND media_profile_scopes.season_number = 0
                        ),
                        douban_rating_count = (
                            SELECT media_profile_scopes.douban_rating_count
                            FROM media_profile_scopes
                            WHERE media_profile_scopes.media_id = managed_media_profiles.media_id
                              AND media_profile_scopes.season_number = 0
                        )
                    WHERE media_type = 'movie'
                      AND EXISTS (
                        SELECT 1
                        FROM media_profile_scopes
                        WHERE media_profile_scopes.media_id = managed_media_profiles.media_id
                          AND media_profile_scopes.season_number = 0
                      )
                    """
                )
            )
