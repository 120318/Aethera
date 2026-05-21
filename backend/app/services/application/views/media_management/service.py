import json
from datetime import datetime
from datetime import timezone
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.schemas.runtime.media_management import (
    MediaIssueSnapshot,
    MediaManagementListItem,
    MediaManagementListRow,
    MediaManagementRowsPage,
    MediaManagementSummary,
    MediaManagementItemsPage,
    MediaMonitorState,
    MediaRecentEventSummary,
    MediaTaskSummary,
)
from app.services.domain.download import download_service
from app.services.domain.media import media_service
from app.services.domain.subscription.query_service import subscription_query_service


class MediaManagementService:
    async def get_summary(self) -> MediaManagementSummary:
        return await media_service.get_management_summary()

    async def list_items(
        self,
        *,
        statuses: list[str] | None = None,
        query: str | None = None,
        media_type: MediaType | None = None,
        sort: str = "activity",
        direction: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> MediaManagementItemsPage:
        rows_page: MediaManagementRowsPage = await media_service.list_management_rows(
            statuses=statuses,
            query=query,
            media_type=media_type,
            sort=sort,
            direction=direction,
            limit=limit,
            offset=offset,
        )
        items = await self._build_items(rows_page.rows)
        return MediaManagementItemsPage(total=rows_page.total, items=items)

    async def _build_items(
        self,
        rows: list[MediaManagementListRow],
    ) -> list[MediaManagementListItem]:
        row_keys = [(row.media_id, row.season_number) for row in rows]
        row_by_key = {(row.media_id, row.season_number): row for row in rows}
        if not row_keys:
            return []
        monitor_map = await subscription_query_service.find_current_monitors_by_media_ids(list({media_id for media_id, _season in row_keys}))
        task_summary_map = await download_service.summarize_media_tasks_by_media_ids(list({media_id for media_id, _season in row_keys}))
        items: list[MediaManagementListItem] = []
        for media_id, season_number in row_keys:
            key = (media_id, season_number)
            if key not in row_by_key:
                continue
            row = row_by_key[key]
            monitor = self._build_monitor_state(row)
            if not monitor.subscribed and not monitor.followed and row.season_number is None:
                monitor = monitor_map.get(str(media_id), monitor)
            task_summary = task_summary_map.get(str(media_id)) if row.season_number is None else None
            event_summary = self._build_event_summary(row)
            items.append(
                self._build_item(
                    media_id=media_id,
                    row=row,
                    monitor=monitor,
                    task_summary=task_summary,
                    event_summary=event_summary,
                )
            )
        return items

    def _build_item(
        self,
        media_id: MediaID,
        monitor: MediaMonitorState,
        row: MediaManagementListRow,
        task_summary: MediaTaskSummary | None = None,
        event_summary: MediaRecentEventSummary | None = None,
    ) -> MediaManagementListItem:
        media_id_str = str(media_id)
        title = self._resolve_profile_title(row.title, media_id_str)
        media_type = self._resolve_media_type(row.media_type, media_id)
        year = self._resolve_media_year(row.year)
        poster_path = row.poster_path
        activity_at = self._resolve_last_activity_at(
            task_summary=task_summary,
            event_summary=event_summary,
            row=row,
        )
        return MediaManagementListItem(
            media_id=media_id,
            season_number=row.season_number if media_type == MediaType.tv else None,
            title=title,
            media_type=media_type,
            year=year,
            poster_path=poster_path,
            monitor=monitor or MediaMonitorState(),
            task_count=self._resolve_non_negative_int(row.task_count),
            active_task_count=self._resolve_non_negative_int(row.active_task_count),
            error_task_count=self._resolve_non_negative_int(row.error_task_count),
            library_count=self._resolve_non_negative_int(row.library_count),
            library_episode_count=self._resolve_non_negative_int(row.library_episode_count),
            original_disc_package_count=self._resolve_non_negative_int(row.original_disc_package_count),
            library_size=self._resolve_non_negative_int(row.library_size),
            last_activity_at=activity_at,
            last_activity_message_key=self._resolve_last_activity_message_key(event_summary, row),
            last_activity_message_params=self._resolve_last_activity_message_params(event_summary, row),
            issues=self._build_issue_snapshot(
                task_summary or MediaTaskSummary(
                    media_id=media_id,
                    error_task_count=self._resolve_non_negative_int(row.error_task_count),
                    file_missing_task_count=self._resolve_non_negative_int(row.file_missing_task_count),
                    seeding_absent_task_count=self._resolve_non_negative_int(row.seeding_absent_task_count),
                ),
                event_summary,
            ),
        )

    @staticmethod
    def _build_monitor_state(row: MediaManagementListRow) -> MediaMonitorState:
        return MediaMonitorState(
            subscribed=bool(row.subscribed),
            followed=bool(row.followed),
        )

    def _resolve_profile_title(self, title: str, media_id_str: str) -> str:
        if title:
            return title
        return media_id_str

    @staticmethod
    def _resolve_media_type(media_type_value: MediaType | None, media_id: MediaID) -> MediaType:
        return media_type_value or media_id.media_type

    @staticmethod
    def _resolve_media_year(year_value: int) -> int:
        return year_value

    def _build_event_summary(self, row: MediaManagementListRow) -> MediaRecentEventSummary | None:
        media_id = row.media_id
        if not media_id:
            return None
        has_recent_error = bool(row.has_recent_error)
        has_recent_warning = bool(row.has_recent_warning)
        last_event_message_key = row.last_event_message_key
        last_event_at = self._coerce_datetime(row.last_event_ts)
        if not has_recent_error and not has_recent_warning and not last_event_message_key and not last_event_at:
            return MediaRecentEventSummary(media_id=media_id)
        return MediaRecentEventSummary(
            media_id=media_id,
            last_event_at=last_event_at,
            last_event_message_key=str(last_event_message_key) if last_event_message_key else None,
            last_event_message_params=self._normalize_message_params(row.last_event_message_params),
            has_recent_error=has_recent_error,
            has_recent_warning=has_recent_warning,
        )

    def _resolve_last_activity_at(
        self,
        task_summary: MediaTaskSummary | None,
        event_summary: MediaRecentEventSummary | None,
        row: MediaManagementListRow,
    ) -> datetime | None:
        candidates: list[datetime] = []
        if task_summary and task_summary.last_task_at:
            candidates.append(task_summary.last_task_at)
        row_task_ts = self._coerce_datetime(row.last_task_ts)
        if row_task_ts:
            candidates.append(row_task_ts)
        row_library_ts = self._coerce_datetime(row.last_library_ts)
        if row_library_ts:
            candidates.append(row_library_ts)
        row_artifact_ts = self._coerce_datetime(row.last_artifact_ts)
        if row_artifact_ts:
            candidates.append(row_artifact_ts)
        if event_summary and event_summary.last_event_at:
            candidates.append(event_summary.last_event_at)
        return max(candidates) if candidates else None

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

    def _resolve_last_activity_message_key(
        self,
        event_summary: MediaRecentEventSummary | None,
        row: MediaManagementListRow,
    ) -> str | None:
        message_key = row.last_event_message_key
        if message_key:
            return str(message_key)
        if event_summary and event_summary.last_event_message_key:
            return event_summary.last_event_message_key
        return None

    def _resolve_last_activity_message_params(
        self,
        event_summary: MediaRecentEventSummary | None,
        row: MediaManagementListRow,
    ) -> dict[str, str]:
        params = self._normalize_message_params(row.last_event_message_params)
        if params:
            return params
        if event_summary:
            return event_summary.last_event_message_params
        return {}

    def _build_issue_snapshot(
        self,
        task_summary: MediaTaskSummary | None,
        event_summary: MediaRecentEventSummary | None,
    ) -> MediaIssueSnapshot:
        codes: list[str] = []
        if task_summary and task_summary.error_task_count > 0:
            codes.append("download_error")
        if task_summary and task_summary.file_missing_task_count > 0:
            codes.append("file_missing")
        if task_summary and task_summary.seeding_absent_task_count > 0:
            codes.append("seeding_absent")

        summary_key = None
        if "download_error" in codes:
            summary_key = "mediaManagement.issues.downloadError"
        elif "file_missing" in codes:
            summary_key = "mediaManagement.issues.fileMissing"
        elif "seeding_absent" in codes:
            summary_key = "mediaManagement.issues.seedingAbsent"

        return MediaIssueSnapshot(has_issues=len(codes) > 0, codes=codes, summary_key=summary_key)

    @staticmethod
    def _coerce_datetime(value: float | None) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _resolve_non_negative_int(value: int) -> int:
        try:
            return max(0, value)
        except (TypeError, ValueError):
            return 0


media_management_service = MediaManagementService()
