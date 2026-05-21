from __future__ import annotations

import json
import logging

from pydantic import ValidationError
from sqlalchemy import Float, Integer, case, cast, desc, func, literal, not_, or_, select, union_all

from app.db.sql.models import (
    EventORM,
    LibraryFileArtifactORM,
    LibraryEpisodeORM,
    LibraryFileORM,
    ManagedMediaProfileORM,
    MediaProfileScopeORM,
    MediaSubscriptionCycleORM,
    MediaSubscriptionSettingsORM,
    TaskORM,
)
from app.db.sql.session import SessionLocal
from app.schemas.domain.download import TaskStatus
from app.schemas.domain.library import LibraryFileArtifactStatus
from app.schemas.domain.media_types import MediaType
from app.schemas.runtime.media_management import MediaManagementRowsPage, MediaManagementSummary, MediaManagementListRow
from app.utils.library_paths import MEDIA_FILE_EXTENSIONS

NON_BUSINESS_EVENT_PREFIXES = (
    "command.",
    "addon.run.",
    "notification.",
    "scheduler.",
)

ACTIVE_TASK_STATUSES = (
    TaskStatus.PENDING.value,
    TaskStatus.DOWNLOADING.value,
    TaskStatus.PAUSED.value,
    TaskStatus.FINISHED.value,
    TaskStatus.TRANSFERRING.value,
    TaskStatus.MIGRATING.value,
)

logger = logging.getLogger("app.repositories.media_management")


class MediaManagementRepository:
    @staticmethod
    def _normalize_message_params(raw) -> dict[str, str]:
        if type(raw) is dict:
            return {str(key): str(value) for key, value in raw.items() if value is not None}
        if type(raw) is str and raw:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            if type(data) is dict:
                return {str(key): str(value) for key, value in data.items() if value is not None}
        return {}

    @staticmethod
    def _primary_library_file_predicate():
        file_name_expr = func.lower(func.coalesce(LibraryFileORM.file_name, ""))
        return or_(*[file_name_expr.like(f"%{extension}") for extension in MEDIA_FILE_EXTENSIONS])

    @staticmethod
    def _validate_rows(rows) -> list[MediaManagementListRow]:
        validated_rows: list[MediaManagementListRow] = []
        for row in rows:
            raw = dict(row)
            raw["last_event_message_params"] = MediaManagementRepository._normalize_message_params(
                raw["last_event_message_params"] if "last_event_message_params" in raw else None
            )
            try:
                validated_rows.append(MediaManagementListRow.model_validate(raw))
            except ValidationError as exc:
                logger.warning(
                    "Skipping invalid media management row: media_id=%s media_type=%s error=%s",
                    raw["media_id"] if "media_id" in raw else None,
                    raw["media_type"] if "media_type" in raw else None,
                    exc.errors()[0]["msg"] if exc.errors() else str(exc),
                )
        return validated_rows

    @staticmethod
    def _candidate_media_ids_subquery():
        return (
            select(
                ManagedMediaProfileORM.media_id.label("media_id"),
                ManagedMediaProfileORM.media_type.label("media_type"),
                ManagedMediaProfileORM.title.label("title"),
                ManagedMediaProfileORM.poster_path.label("poster_path"),
                ManagedMediaProfileORM.year.label("year"),
            )
            .where(ManagedMediaProfileORM.is_active == 1)
            .subquery("media_management_candidates")
        )

    @staticmethod
    def _task_season_expr():
        return func.coalesce(
            cast(func.json_extract(TaskORM.context_json, "$.media.season_number"), Integer),
            cast(func.json_extract(TaskORM.context_json, "$.parsed_attributes.seasons[0]"), Integer),
            case((TaskORM.media_id.like("%:tv:%"), 1), else_=0),
        )

    @staticmethod
    def _candidate_scopes_subquery(candidate_media_ids):
        profile_default_scope = select(
            candidate_media_ids.c.media_id.label("media_id"),
            literal(0).label("season_number"),
        ).where(
            candidate_media_ids.c.media_type != MediaType.tv.value,
        )
        profile_season_scope = select(
            MediaProfileScopeORM.media_id.label("media_id"),
            MediaProfileScopeORM.season_number.label("season_number"),
        ).where(MediaProfileScopeORM.season_number > 0)
        settings_scope = select(
            MediaSubscriptionSettingsORM.media_id.label("media_id"),
            MediaSubscriptionSettingsORM.season_number.label("season_number"),
        )
        cycle_scope = select(
            MediaSubscriptionCycleORM.media_id.label("media_id"),
            MediaSubscriptionCycleORM.season_number.label("season_number"),
        )
        task_scope = select(
            TaskORM.media_id.label("media_id"),
            MediaManagementRepository._task_season_expr().label("season_number"),
        ).where(TaskORM.media_id.is_not(None))
        library_scope = select(
            LibraryEpisodeORM.media_id.label("media_id"),
            LibraryEpisodeORM.season.label("season_number"),
        )
        return (
            union_all(profile_default_scope, profile_season_scope, settings_scope, cycle_scope, task_scope, library_scope)
            .subquery("media_management_candidate_scopes")
        )

    @staticmethod
    def _monitor_flags_subquery():
        active_cycles = (
            select(
                MediaSubscriptionCycleORM.media_id.label("media_id"),
                MediaSubscriptionCycleORM.season_number.label("season_number"),
                func.max(case((MediaSubscriptionCycleORM.status == "active", 1), else_=0)).label("subscribed"),
            )
            .group_by(MediaSubscriptionCycleORM.media_id, MediaSubscriptionCycleORM.season_number)
            .subquery("media_management_active_cycles")
        )
        return (
            select(
                MediaSubscriptionSettingsORM.media_id.label("media_id"),
                MediaSubscriptionSettingsORM.season_number.label("season_number"),
                func.coalesce(active_cycles.c.subscribed, 0).label("subscribed"),
                func.max(case((MediaSubscriptionSettingsORM.followed == 1, 1), else_=0)).label("followed"),
            )
            .select_from(MediaSubscriptionSettingsORM)
            .outerjoin(
                active_cycles,
                (active_cycles.c.media_id == MediaSubscriptionSettingsORM.media_id)
                & (active_cycles.c.season_number == MediaSubscriptionSettingsORM.season_number),
            )
            .group_by(MediaSubscriptionSettingsORM.media_id, MediaSubscriptionSettingsORM.season_number, active_cycles.c.subscribed)
            .subquery("media_management_monitor_flags")
        )

    @staticmethod
    def _task_summary_subquery():
        return (
            select(
                TaskORM.media_id.label("media_id"),
                MediaManagementRepository._task_season_expr().label("season_number"),
                func.count().label("task_count"),
                func.sum(case((TaskORM.status.in_(ACTIVE_TASK_STATUSES), 1), else_=0)).label("active_task_count"),
                func.sum(case((TaskORM.status == "error", 1), else_=0)).label("error_task_count"),
                func.sum(case((TaskORM.status.in_(("file_missing", "partial_missing")), 1), else_=0)).label("file_missing_task_count"),
                func.sum(case((TaskORM.status == "seeding_absent", 1), else_=0)).label("seeding_absent_task_count"),
                func.max(cast(func.strftime("%s", TaskORM.updated_at), Float)).label("last_task_ts"),
            )
            .where(TaskORM.media_id.is_not(None))
            .group_by(TaskORM.media_id, MediaManagementRepository._task_season_expr())
            .subquery("media_management_task_summary")
        )

    @staticmethod
    def _library_summary_subquery():
        primary_library_file = MediaManagementRepository._primary_library_file_predicate()
        resolved_media_id = func.coalesce(LibraryEpisodeORM.media_id, TaskORM.media_id)
        package_layout = func.json_extract(LibraryFileORM.resource_attributes_json, "$.package_layout")
        package_root = case(
            (
                package_layout == "ISO",
                func.rtrim(
                    func.coalesce(LibraryFileORM.path, "")
                    + "/"
                    + func.coalesce(LibraryFileORM.file_name, ""),
                    "/",
                ),
            ),
            (
                package_layout.in_(("BDMV", "VIDEO_TS")),
                case(
                    (
                        func.instr(func.upper(LibraryFileORM.path), "/BDMV") > 0,
                        func.substr(LibraryFileORM.path, 1, func.instr(func.upper(LibraryFileORM.path), "/BDMV") - 1),
                    ),
                    (
                        func.instr(func.upper(LibraryFileORM.path), "/CERTIFICATE") > 0,
                        func.substr(LibraryFileORM.path, 1, func.instr(func.upper(LibraryFileORM.path), "/CERTIFICATE") - 1),
                    ),
                    (
                        func.instr(func.upper(LibraryFileORM.path), "/VIDEO_TS") > 0,
                        func.substr(LibraryFileORM.path, 1, func.instr(func.upper(LibraryFileORM.path), "/VIDEO_TS") - 1),
                    ),
                    else_=LibraryFileORM.path,
                ),
            ),
            else_=None,
        )
        file_map = (
            select(
                resolved_media_id.label("media_id"),
                func.coalesce(LibraryEpisodeORM.season, MediaManagementRepository._task_season_expr()).label("season_number"),
                LibraryFileORM.id.label("file_id"),
                LibraryEpisodeORM.episode.label("episode"),
                package_root.label("package_root"),
                LibraryFileORM.file_size.label("file_size"),
                LibraryFileORM.created_at.label("created_at"),
            )
            .select_from(LibraryFileORM)
            .outerjoin(LibraryEpisodeORM, LibraryEpisodeORM.file_id == LibraryFileORM.id)
            .outerjoin(TaskORM, TaskORM.id == LibraryFileORM.task_id)
            .where(
                resolved_media_id.is_not(None),
                primary_library_file,
            )
            .distinct()
            .subquery("media_management_library_files")
        )
        return (
            select(
                file_map.c.media_id.label("media_id"),
                file_map.c.season_number.label("season_number"),
                func.count().label("library_count"),
                func.count(func.distinct(file_map.c.episode)).label("library_episode_count"),
                func.count(func.distinct(file_map.c.package_root)).label("original_disc_package_count"),
                func.coalesce(func.sum(file_map.c.file_size), 0).label("library_size"),
                func.max(file_map.c.created_at).label("last_library_ts"),
            )
            .group_by(file_map.c.media_id, file_map.c.season_number)
            .subquery("media_management_library_summary")
        )

    @staticmethod
    def _library_presence_subquery():
        primary_library_file = MediaManagementRepository._primary_library_file_predicate()
        episode_presence = select(
            LibraryEpisodeORM.media_id.label("media_id"),
            LibraryEpisodeORM.season.label("season_number"),
            func.count().label("library_count"),
        ).group_by(LibraryEpisodeORM.media_id, LibraryEpisodeORM.season)
        movie_file_presence = (
            select(
                LibraryFileORM.media_id.label("media_id"),
                literal(0).label("season_number"),
                func.count().label("library_count"),
            )
            .select_from(LibraryFileORM)
            .where(
                LibraryFileORM.media_id.is_not(None),
                not_(LibraryFileORM.media_id.like("%:tv:%")),
                primary_library_file,
            )
            .group_by(LibraryFileORM.media_id)
        )
        tv_file_fallback_presence = (
            select(
                LibraryFileORM.media_id.label("media_id"),
                MediaManagementRepository._task_season_expr().label("season_number"),
                func.count().label("library_count"),
            )
            .select_from(LibraryFileORM)
            .outerjoin(LibraryEpisodeORM, LibraryEpisodeORM.file_id == LibraryFileORM.id)
            .outerjoin(TaskORM, TaskORM.id == LibraryFileORM.task_id)
            .where(
                LibraryFileORM.media_id.like("%:tv:%"),
                LibraryEpisodeORM.file_id.is_(None),
                primary_library_file,
            )
            .group_by(LibraryFileORM.media_id, MediaManagementRepository._task_season_expr())
        )
        raw_presence = union_all(
            episode_presence,
            movie_file_presence,
            tv_file_fallback_presence,
        ).subquery("media_management_library_presence_raw")
        return (
            select(
                raw_presence.c.media_id.label("media_id"),
                raw_presence.c.season_number.label("season_number"),
                func.sum(raw_presence.c.library_count).label("library_count"),
            )
            .group_by(raw_presence.c.media_id, raw_presence.c.season_number)
            .subquery("media_management_library_presence")
        )

    @staticmethod
    def _artifact_summary_subquery():
        resolved_media_id = func.coalesce(LibraryEpisodeORM.media_id, LibraryFileORM.media_id, TaskORM.media_id)
        artifact_season = func.coalesce(
            LibraryEpisodeORM.season,
            MediaManagementRepository._task_season_expr(),
        )
        artifact_activity_ts = func.coalesce(
            LibraryFileArtifactORM.last_success_at,
            LibraryFileArtifactORM.updated_at,
        )
        return (
            select(
                resolved_media_id.label("media_id"),
                artifact_season.label("season_number"),
                func.max(artifact_activity_ts).label("last_artifact_ts"),
            )
            .select_from(LibraryFileArtifactORM)
            .join(LibraryFileORM, LibraryFileORM.id == LibraryFileArtifactORM.library_file_id)
            .outerjoin(LibraryEpisodeORM, LibraryEpisodeORM.file_id == LibraryFileORM.id)
            .outerjoin(TaskORM, TaskORM.id == LibraryFileORM.task_id)
            .where(
                LibraryFileArtifactORM.status == LibraryFileArtifactStatus.succeeded.value,
                resolved_media_id.is_not(None),
            )
            .group_by(resolved_media_id, artifact_season)
            .subquery("media_management_artifact_summary")
        )

    @staticmethod
    def _event_summary_subquery():
        excluded = not_(or_(*[EventORM.type.like(f"{prefix}%") for prefix in NON_BUSINESS_EVENT_PREFIXES]))
        event_season_number = func.coalesce(EventORM.media_season_number, 0)
        ranked = (
            select(
                EventORM.media_id.label("media_id"),
                event_season_number.label("season_number"),
                EventORM.level.label("level"),
                EventORM.message_key.label("message_key"),
                EventORM.message_params_json.label("message_params"),
                EventORM.ts.label("ts"),
                func.row_number().over(
                    partition_by=(EventORM.media_id, event_season_number),
                    order_by=desc(EventORM.ts),
                ).label("rn"),
            )
            .where(EventORM.media_id.is_not(None))
            .where(excluded)
            .subquery("media_management_ranked_events")
        )
        return (
            select(
                ranked.c.media_id.label("media_id"),
                ranked.c.season_number.label("season_number"),
                func.max(case((ranked.c.rn == 1, cast(func.strftime("%s", ranked.c.ts), Float)), else_=0.0)).label("last_event_ts"),
                func.max(case((ranked.c.rn == 1, ranked.c.message_key), else_="")).label("last_event_message_key"),
                func.max(case((ranked.c.rn == 1, ranked.c.message_params), else_=literal("{}"))).label("last_event_message_params"),
                func.max(case((((ranked.c.rn <= 6) & (ranked.c.level == "error")), 1), else_=0)).label("has_recent_error"),
                func.max(case((((ranked.c.rn <= 6) & (ranked.c.level == "warning")), 1), else_=0)).label("has_recent_warning"),
            )
            .group_by(ranked.c.media_id, ranked.c.season_number)
            .subquery("media_management_event_summary")
        )

    def _build_base_stmt(self):
        candidate_media_ids = self._candidate_media_ids_subquery()
        candidate_scopes_raw = self._candidate_scopes_subquery(candidate_media_ids)
        candidate_scopes = (
            select(
                candidate_scopes_raw.c.media_id.label("media_id"),
                candidate_scopes_raw.c.season_number.label("season_number"),
            )
            .where(candidate_scopes_raw.c.media_id.is_not(None))
            .where(candidate_scopes_raw.c.season_number >= 0)
            .distinct()
            .subquery("media_management_scopes")
        )
        monitor_flags = self._monitor_flags_subquery()
        task_summary = self._task_summary_subquery()
        library_summary = self._library_summary_subquery()
        artifact_summary = self._artifact_summary_subquery()
        event_summary = self._event_summary_subquery()

        title_expr = func.coalesce(candidate_media_ids.c.title, candidate_media_ids.c.media_id)
        media_type_expr = candidate_media_ids.c.media_type
        subscribed_expr = func.coalesce(monitor_flags.c.subscribed, 0)
        followed_expr = func.coalesce(monitor_flags.c.followed, 0)
        task_count_expr = func.coalesce(task_summary.c.task_count, 0)
        active_task_count_expr = func.coalesce(task_summary.c.active_task_count, 0)
        error_task_count_expr = func.coalesce(task_summary.c.error_task_count, 0)
        file_missing_task_count_expr = func.coalesce(task_summary.c.file_missing_task_count, 0)
        seeding_absent_task_count_expr = func.coalesce(task_summary.c.seeding_absent_task_count, 0)
        library_count_expr = func.coalesce(library_summary.c.library_count, 0)
        library_episode_count_expr = func.coalesce(library_summary.c.library_episode_count, 0)
        original_disc_package_count_expr = func.coalesce(library_summary.c.original_disc_package_count, 0)
        library_size_expr = func.coalesce(library_summary.c.library_size, 0)
        task_last_ts_expr = func.coalesce(task_summary.c.last_task_ts, 0.0)
        library_last_ts_expr = func.coalesce(library_summary.c.last_library_ts, 0.0)
        artifact_last_ts_expr = func.coalesce(artifact_summary.c.last_artifact_ts, 0.0)
        event_last_ts_expr = func.coalesce(event_summary.c.last_event_ts, 0.0)
        recent_error_expr = func.coalesce(event_summary.c.has_recent_error, 0)
        recent_warning_expr = func.coalesce(event_summary.c.has_recent_warning, 0)
        issues_expr = or_(
            error_task_count_expr > 0,
            file_missing_task_count_expr > 0,
            seeding_absent_task_count_expr > 0,
        )
        activity_ts_expr = func.max(task_last_ts_expr, library_last_ts_expr, event_last_ts_expr, artifact_last_ts_expr)

        stmt = (
            select(
                candidate_media_ids.c.media_id.label("media_id"),
                case(
                    (media_type_expr == MediaType.tv.value, candidate_scopes.c.season_number),
                    else_=literal(None),
                ).label("season_number"),
                title_expr.label("title"),
                media_type_expr.label("media_type"),
                candidate_media_ids.c.poster_path.label("poster_path"),
                func.coalesce(candidate_media_ids.c.year, 0).label("year"),
                subscribed_expr.label("subscribed"),
                followed_expr.label("followed"),
                error_task_count_expr.label("error_task_count"),
                file_missing_task_count_expr.label("file_missing_task_count"),
                seeding_absent_task_count_expr.label("seeding_absent_task_count"),
                library_count_expr.label("library_count"),
                library_episode_count_expr.label("library_episode_count"),
                original_disc_package_count_expr.label("original_disc_package_count"),
                library_size_expr.label("library_size"),
                activity_ts_expr.label("activity_ts"),
                task_count_expr.label("task_count"),
                active_task_count_expr.label("active_task_count"),
                task_summary.c.last_task_ts.label("last_task_ts"),
                library_summary.c.last_library_ts.label("last_library_ts"),
                event_summary.c.last_event_ts.label("last_event_ts"),
                artifact_summary.c.last_artifact_ts.label("last_artifact_ts"),
                event_summary.c.last_event_message_key.label("last_event_message_key"),
                event_summary.c.last_event_message_params.label("last_event_message_params"),
                recent_error_expr.label("has_recent_error"),
                recent_warning_expr.label("has_recent_warning"),
                issues_expr.label("has_issues"),
            )
            .select_from(candidate_media_ids)
            .join(candidate_scopes, candidate_scopes.c.media_id == candidate_media_ids.c.media_id)
            .outerjoin(
                monitor_flags,
                (monitor_flags.c.media_id == candidate_media_ids.c.media_id)
                & (monitor_flags.c.season_number == candidate_scopes.c.season_number),
            )
            .outerjoin(
                task_summary,
                (task_summary.c.media_id == candidate_media_ids.c.media_id)
                & (task_summary.c.season_number == candidate_scopes.c.season_number),
            )
            .outerjoin(
                library_summary,
                (library_summary.c.media_id == candidate_media_ids.c.media_id)
                & (library_summary.c.season_number == candidate_scopes.c.season_number),
            )
            .outerjoin(
                artifact_summary,
                (artifact_summary.c.media_id == candidate_media_ids.c.media_id)
                & (artifact_summary.c.season_number == candidate_scopes.c.season_number),
            )
            .outerjoin(
                event_summary,
                (event_summary.c.media_id == candidate_media_ids.c.media_id)
                & (event_summary.c.season_number == candidate_scopes.c.season_number),
            )
            .where(
                or_(
                    candidate_media_ids.c.media_type != MediaType.tv.value,
                    candidate_scopes.c.season_number > 0,
                )
            )
        )
        return stmt, {
            "media_id": candidate_media_ids.c.media_id,
            "season_number": candidate_scopes.c.season_number,
            "title": title_expr,
            "media_type": media_type_expr,
            "poster_path": candidate_media_ids.c.poster_path,
            "year": candidate_media_ids.c.year,
            "subscribed": subscribed_expr,
            "followed": followed_expr,
            "task_count": task_count_expr,
            "active_task_count": active_task_count_expr,
            "error_task_count": error_task_count_expr,
            "file_missing_task_count": file_missing_task_count_expr,
            "seeding_absent_task_count": seeding_absent_task_count_expr,
            "library_count": library_count_expr,
            "library_episode_count": library_episode_count_expr,
            "original_disc_package_count": original_disc_package_count_expr,
            "library_size": library_size_expr,
            "activity_ts": activity_ts_expr,
            "last_task_ts": task_summary.c.last_task_ts,
            "last_library_ts": library_summary.c.last_library_ts,
            "last_event_ts": event_summary.c.last_event_ts,
            "last_artifact_ts": artifact_summary.c.last_artifact_ts,
            "last_event_message_key": event_summary.c.last_event_message_key,
            "last_event_message_params": event_summary.c.last_event_message_params,
            "has_recent_error": recent_error_expr,
            "has_recent_warning": recent_warning_expr,
            "issues": issues_expr,
        }

    @staticmethod
    def _apply_filters(stmt, columns, *, statuses: list[str] | None, query: str | None, media_type: MediaType | None):
        if query:
            keyword = f"%{query.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(columns["title"]).like(keyword),
                    func.lower(columns["media_id"]).like(keyword),
                    func.lower(columns["media_type"]).like(keyword),
                )
            )
        if media_type:
            stmt = stmt.where(columns["media_type"] == media_type.value)
        if statuses:
            predicates = []
            for status in statuses:
                if status == "subscribed":
                    predicates.append(columns["subscribed"] > 0)
                elif status == "followed":
                    predicates.append(columns["followed"] > 0)
                elif status == "downloading":
                    predicates.append(columns["active_task_count"] > 0)
                elif status == "downloaded":
                    predicates.append(
                        (columns["task_count"] > 0)
                        & (columns["active_task_count"] == 0)
                        & (columns["library_count"] == 0)
                    )
                elif status == "library":
                    predicates.append(columns["library_count"] > 0)
                elif status == "issues":
                    predicates.append(columns["issues"])
            if predicates:
                stmt = stmt.where(or_(*predicates))
        return stmt

    @staticmethod
    def _apply_order(stmt, columns, *, sort: str, direction: str):
        descending = direction != "asc"

        def ordered(expr):
            return expr.desc() if descending else expr.asc()

        title_expr = func.lower(columns["title"])
        media_id_expr = columns["media_id"]
        season_expr = columns["season_number"]
        if sort == "title":
            return stmt.order_by(ordered(title_expr), ordered(season_expr), ordered(media_id_expr))
        if sort == "tasks":
            return stmt.order_by(
                ordered(columns["active_task_count"]),
                ordered(columns["task_count"]),
                ordered(title_expr),
                ordered(season_expr),
                ordered(media_id_expr),
            )
        if sort == "library":
            return stmt.order_by(
                ordered(columns["library_count"]),
                ordered(columns["library_size"]),
                ordered(title_expr),
                ordered(season_expr),
                ordered(media_id_expr),
            )
        if sort == "issues":
            issue_sort_expr = case((columns["issues"], 1), else_=0)
            return stmt.order_by(
                ordered(issue_sort_expr),
                ordered(columns["error_task_count"]),
                ordered(title_expr),
                ordered(season_expr),
                ordered(media_id_expr),
            )
        return stmt.order_by(
            ordered(columns["activity_ts"]),
            ordered(columns["active_task_count"]),
            ordered(columns["library_count"]),
            ordered(title_expr),
            ordered(season_expr),
            ordered(media_id_expr),
        )

    def list_page(
        self,
        *,
        statuses: list[str] | None = None,
        query: str | None = None,
        media_type: MediaType | None = None,
        sort: str = "activity",
        direction: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> MediaManagementRowsPage:
        stmt, columns = self._build_base_stmt()
        filtered_stmt = self._apply_filters(
            stmt,
            columns,
            statuses=statuses,
            query=query,
            media_type=media_type,
        )
        ordered_stmt = self._apply_order(filtered_stmt, columns, sort=sort, direction=direction)
        with SessionLocal() as session:
            base = filtered_stmt.with_only_columns(stmt.selected_columns.media_id).subquery()
            total = int(session.execute(select(func.count()).select_from(base)).scalar_one())
            rows = session.execute(
                ordered_stmt.with_only_columns(ordered_stmt.selected_columns).limit(limit).offset(offset)
            ).mappings().all()
        return MediaManagementRowsPage(
            total=total,
            rows=self._validate_rows(rows),
        )

    def get_summary(self) -> MediaManagementSummary:
        candidate_media_ids = self._candidate_media_ids_subquery()
        candidate_scopes_raw = self._candidate_scopes_subquery(candidate_media_ids)
        candidate_scopes = (
            select(
                candidate_scopes_raw.c.media_id.label("media_id"),
                candidate_scopes_raw.c.season_number.label("season_number"),
            )
            .where(candidate_scopes_raw.c.media_id.is_not(None))
            .where(candidate_scopes_raw.c.season_number >= 0)
            .distinct()
            .subquery("media_management_summary_scopes")
        )
        monitor_flags = self._monitor_flags_subquery()
        task_summary = self._task_summary_subquery()
        library_presence = self._library_presence_subquery()

        subscribed_expr = func.coalesce(monitor_flags.c.subscribed, 0)
        followed_expr = func.coalesce(monitor_flags.c.followed, 0)
        active_task_count_expr = func.coalesce(task_summary.c.active_task_count, 0)
        error_task_count_expr = func.coalesce(task_summary.c.error_task_count, 0)
        file_missing_task_count_expr = func.coalesce(task_summary.c.file_missing_task_count, 0)
        seeding_absent_task_count_expr = func.coalesce(task_summary.c.seeding_absent_task_count, 0)
        library_count_expr = func.coalesce(library_presence.c.library_count, 0)

        base = (
            select(
                candidate_media_ids.c.media_id.label("media_id"),
                candidate_scopes.c.season_number.label("season_number"),
                subscribed_expr.label("subscribed"),
                followed_expr.label("followed"),
                active_task_count_expr.label("active_task_count"),
                error_task_count_expr.label("error_task_count"),
                file_missing_task_count_expr.label("file_missing_task_count"),
                seeding_absent_task_count_expr.label("seeding_absent_task_count"),
                library_count_expr.label("library_count"),
            )
            .select_from(candidate_media_ids)
            .join(candidate_scopes, candidate_scopes.c.media_id == candidate_media_ids.c.media_id)
            .outerjoin(
                monitor_flags,
                (monitor_flags.c.media_id == candidate_media_ids.c.media_id)
                & (monitor_flags.c.season_number == candidate_scopes.c.season_number),
            )
            .outerjoin(
                task_summary,
                (task_summary.c.media_id == candidate_media_ids.c.media_id)
                & (task_summary.c.season_number == candidate_scopes.c.season_number),
            )
            .outerjoin(
                library_presence,
                (library_presence.c.media_id == candidate_media_ids.c.media_id)
                & (library_presence.c.season_number == candidate_scopes.c.season_number),
            )
            .where(
                or_(
                    candidate_media_ids.c.media_type != MediaType.tv.value,
                    candidate_scopes.c.season_number > 0,
                )
            )
            .subquery("media_management_summary")
        )
        summary_stmt = select(
            func.count().label("total"),
            func.sum(case((base.c.subscribed > 0, 1), else_=0)).label("subscribed"),
            func.sum(case((base.c.followed > 0, 1), else_=0)).label("followed"),
            func.sum(case((base.c.active_task_count > 0, 1), else_=0)).label("downloading"),
            func.sum(case((base.c.library_count > 0, 1), else_=0)).label("in_library"),
            func.sum(
                case(
                    (
                        (base.c.error_task_count > 0)
                        | (base.c.file_missing_task_count > 0)
                        | (base.c.seeding_absent_task_count > 0),
                        1,
                    ),
                    else_=0,
                )
            ).label("issues"),
        ).select_from(base)
        with SessionLocal() as session:
            row = session.execute(summary_stmt).one()
        return MediaManagementSummary(
            total=int(row.total or 0),
            subscribed=int(row.subscribed or 0),
            followed=int(row.followed or 0),
            downloading=int(row.downloading or 0),
            in_library=int(row.in_library or 0),
            issues=int(row.issues or 0),
        )


media_management_repository = MediaManagementRepository()
