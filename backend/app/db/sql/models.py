from __future__ import annotations

from sqlalchemy import Float, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.sql.base import Base


class MediaSubscriptionSettingsORM(Base):
    __tablename__ = "media_subscription_settings"

    media_id: Mapped[str] = mapped_column(Text, primary_key=True)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0, primary_key=True)
    sub_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    followed: Mapped[bool] = mapped_column(Integer, nullable=False, default=0, index=True)
    subscription_mode: Mapped[str] = mapped_column(Text, nullable=False)
    media_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    upgrade_policy_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    target_filters_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    target_filter_config_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    directory_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_config_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_profile_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    filters_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sites_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    unmatched_rules_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    follow_reminded_air_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_reminded_digital_release_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_reminded_physical_release_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_reminded_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    follow_reminded_digital_release_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    follow_reminded_physical_release_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)


class MediaSubscriptionCycleORM(Base):
    __tablename__ = "media_subscription_cycles"

    cycle_id: Mapped[str] = mapped_column(Text, primary_key=True)
    media_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    sub_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    started_at: Mapped[float] = mapped_column(Float, nullable=False)
    last_checked_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    ended_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    ended_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ended_trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    completion_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_media_subscription_cycles_media_season_status", "media_id", "season_number", "status"),
        Index("ix_media_subscription_cycles_media_season_created", "media_id", "season_number", "created_at"),
    )


class TaskORM(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    media_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_item_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    torrent_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    error_stage: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    context_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    downloader_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_client: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_client_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    save_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_tasks_media_status", "media_id", "status"),
    )


class TaskStorageMigrationORM(Base):
    __tablename__ = "task_storage_migrations"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    action_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    task_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    torrent_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source_downloader_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_downloader_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_directory_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_directory_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_save_path: Mapped[str] = mapped_column(Text, nullable=False)
    target_save_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_content_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_content_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_task_status: Mapped[str] = mapped_column(Text, nullable=False)
    move_content: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cleanup_source_torrent: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    phase: Mapped[str] = mapped_column(Text, nullable=False, default="prepared")
    source_paused: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_added_by_migration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_moved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    library_files_moved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    blockers_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    finalized_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_task_storage_migrations_task_status", "task_id", "status"),
    )


class CommandORM(Base):
    __tablename__ = "commands"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    message_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    initiator: Mapped[str] = mapped_column(Text, nullable=False)
    media_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_season_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uniq_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_commands_media_season_status", "media_id", "target_season_number", "status"),
        Index("ix_commands_media_status", "media_id", "status"),
        Index("ix_commands_target_status", "target_type", "target_id", "status"),
        Index("ix_commands_target_season_status", "target_type", "target_id", "target_season_number", "status"),
        Index("ix_commands_uniq_status", "uniq_key", "status"),
    )


class LibraryMetaORM(Base):
    __tablename__ = "library_meta"

    media_id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)


class LibraryFileORM(Base):
    __tablename__ = "library_files"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    task_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    directory_id: Mapped[str] = mapped_column(Text, nullable=False, index=True, default="", server_default="")
    media_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    resource_attributes_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("ix_library_files_path_name", "path", "file_name"),
    )


class LibraryFileArtifactORM(Base):
    __tablename__ = "library_file_artifacts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    library_file_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    expected_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    last_success_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("library_file_id", "artifact_type", "expected_path", name="uq_library_file_artifact_path"),
        Index("ix_library_file_artifacts_status_retry", "status", "next_retry_at"),
    )


class LibraryEpisodeORM(Base):
    __tablename__ = "library_episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    episode: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_library_episodes_media_season", "media_id", "season"),
        UniqueConstraint("media_id", "season", "episode", "file_id", name="uq_library_episode_file"),
    )


class MediaExternalMappingORM(Base):
    __tablename__ = "media_external_mappings"

    media_id: Mapped[str] = mapped_column(Text, primary_key=True)
    media_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False, primary_key=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    imdb_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    douban_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    episode_count_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    __table_args__ = (
        Index(
            "uq_media_external_mappings_douban_season",
            "media_type",
            "douban_id",
            "season_number",
            unique=True,
            sqlite_where=douban_id.is_not(None),
        ),
    )


class MediaProfileScopeORM(Base):
    __tablename__ = "media_profile_scopes"

    media_id: Mapped[str] = mapped_column(Text, primary_key=True)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False, primary_key=True)
    media_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    air_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    episode_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_count_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    douban_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    douban_vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    douban_rating_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_air_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    aired_episode_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_aired_episode_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    next_episode_to_air_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    premiere_release_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    theatrical_limited_release_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    theatrical_release_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    digital_release_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    physical_release_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    tv_release_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_dates_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    platforms_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    airings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    __table_args__ = (
        Index("ix_media_profile_scopes_media_season", "media_id", "season_number"),
    )


class EventDispatchORM(Base):
    __tablename__ = "event_dispatches"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    event_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    consumer_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_event_dispatches_status_available_at", "status", "available_at"),
        UniqueConstraint("event_id", "consumer_name", name="uq_event_dispatch_event_consumer"),
    )


class ManagedMediaProfileORM(Base):
    __tablename__ = "managed_media_profiles"

    media_id: Mapped[str] = mapped_column(Text, primary_key=True)
    media_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    original_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    genres_json: Mapped[list] = mapped_column(JSON, nullable=False)
    imdb_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    douban_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    primary_metadata_source: Mapped[str] = mapped_column(Text, nullable=False, default="douban")
    metadata_capabilities_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tvdb_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    actors_json: Mapped[list] = mapped_column(JSON, nullable=False)
    directors_json: Mapped[list] = mapped_column(JSON, nullable=False)
    studios_json: Mapped[list] = mapped_column(JSON, nullable=False)
    duration: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    vote_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    douban_vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    douban_rating_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tmdb_vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmdb_rating_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    release_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    seasons_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episodes_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_language: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Integer, nullable=False, default=1, index=True)
    last_seen_at: Mapped[float] = mapped_column(Float, nullable=False)
    inactive_since: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail_ready: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    simple_info_updated_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail_updated_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    schedule_updated_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)


class ActionORM(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    ts: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    action_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    media_season_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    media_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    message_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("ix_actions_target_type_target_id_ts", "target_type", "target_id", "ts"),
        Index("ix_actions_action_name", "action_name"),
        Index("ix_actions_source", "source"),
        Index("ix_actions_status_ts", "status", "ts"),
        Index("ix_actions_kind_ts", "kind", "ts"),
    )


class AlertORM(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    category: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    message_key: Mapped[str] = mapped_column(Text, nullable=False)
    message_params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    target_type: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    target_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    media_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    media_season_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    media_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    action_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    last_seen_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    acknowledged_at: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    resolved_at: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    __table_args__ = (
        Index("ix_alerts_status_ack_severity", "status", "acknowledged_at", "severity"),
        Index("ix_alerts_target", "target_type", "target_id"),
    )


class EventORM(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    ts: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    level: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    message_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    media_season_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    media_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    actor: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    addon_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    addon_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities_json: Mapped[list] = mapped_column(JSON, nullable=False)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)

    __table_args__ = (
        Index("ix_events_media_season_ts", "media_id", "media_season_number", "ts"),
    )


class SchedulerRuntimeORM(Base):
    __tablename__ = "scheduler_runtime"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    running: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    items_json: Mapped[list] = mapped_column(JSON, nullable=False)
    pending_manual_triggers_json: Mapped[list] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)


class IndexerSiteHealthORM(Base):
    __tablename__ = "indexer_site_health"

    indexer_id: Mapped[str] = mapped_column(Text, primary_key=True)
    site_id: Mapped[str] = mapped_column(Text, primary_key=True)
    indexer_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    site_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    checked_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_success_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_failure_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    notify_pending: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    client_type: Mapped[str] = mapped_column(Text, nullable=False, default="jackett")

    __table_args__ = (
        Index("ix_indexer_site_health_indexer", "indexer_id"),
        Index("ix_indexer_site_health_notify_pending", "notify_pending"),
    )


class AuthSessionORM(Base):
    __tablename__ = "auth_sessions"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    username: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)


class MetadataSyncORM(Base):
    __tablename__ = "metadata_sync"

    media_server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    media_id: Mapped[str] = mapped_column(Text, primary_key=True)
    media_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active", index=True)
    last_check_at: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    last_success_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_due_at: Mapped[float] = mapped_column(Float, nullable=False, default=0, index=True)
    missing_flags_json: Mapped[list] = mapped_column(JSON, nullable=False)
    updated_paths_json: Mapped[list] = mapped_column(JSON, nullable=False)


class ConfigSectionORM(Base):
    __tablename__ = "config_sections"

    section: Mapped[str] = mapped_column(Text, primary_key=True)
    payload_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)


class DownloaderSettingORM(Base):
    __tablename__ = "settings_downloaders"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class DirectorySettingORM(Base):
    __tablename__ = "settings_directories"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class IndexerSettingORM(Base):
    __tablename__ = "settings_indexers"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class MediaServerSettingORM(Base):
    __tablename__ = "settings_media_servers"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class NamingTemplateSettingORM(Base):
    __tablename__ = "settings_naming_templates"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class FilterPresetSettingORM(Base):
    __tablename__ = "settings_filter_presets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class QualityProfileSettingORM(Base):
    __tablename__ = "settings_quality_profiles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class TagSettingORM(Base):
    __tablename__ = "settings_tags"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class DirectoryIntegrityPolicySettingORM(Base):
    __tablename__ = "settings_directory_integrity_policies"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class SettingsDefaultORM(Base):
    __tablename__ = "settings_defaults"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
