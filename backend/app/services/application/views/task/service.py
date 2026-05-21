from __future__ import annotations

import asyncio
from datetime import datetime

from app.schemas.config import Tag
from app.schemas.media_id import MediaID
from app.schemas.domain.command import CommandRecord, CommandTargetType
from app.schemas.domain.download import TaskData, TaskErrorStage, TaskStatus
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_attributes import ResourceAttributes, ResourceDisplayAttributes, ResourceFormEvidence
from app.schemas.runtime.task_view import (
    TaskAction,
    TaskActionState,
    TaskDetailResponseModel,
    TaskPhase,
    TaskPhaseGroup,
    TaskRealtimeView,
    TaskViewItem,
)
from app.schemas.domain.torrent_status import TorrentState, TorrentStatus
from app.services.application.commands.service import command_service
from app.services.application.workflows.danmu import danmu_application_service
from app.services.application.workflows.media_server_sync.service import media_server_sync_service
from app.services.config.settings_service import settings_service
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service
from app.services.domain.resource.tags import resolve_display_tags


def _as_positive_int(value: int | None) -> int | None:
    if type(value) is not int or value <= 0:
        return None
    return value


class TaskViewService:
    def _list_active_statuses(self) -> list[TaskStatus]:
        return [
            TaskStatus.PENDING,
            TaskStatus.DOWNLOADING,
            TaskStatus.PAUSED,
            TaskStatus.FINISHED,
            TaskStatus.TRANSFERRING,
            TaskStatus.MIGRATING,
            TaskStatus.COMPLETED,
            TaskStatus.PARTIAL_MISSING,
            TaskStatus.SEEDING_ABSENT,
            TaskStatus.FILE_MISSING,
            TaskStatus.ERROR,
        ]

    async def list_media_task_views(self, media_id: MediaID, *, season_number: int | None = None) -> list[TaskViewItem]:
        tasks = await download_service.get_tasks(status=self._list_active_statuses(), media_id=media_id)
        if media_id.media_type == MediaType.tv and season_number is not None:
            tasks = [task for task in tasks if self._task_matches_season(task, season_number)]
        return await self._build_task_views(tasks, media_id=media_id)

    async def get_task_detail(self, task_id: str) -> TaskDetailResponseModel | None:
        task = await download_service.find_task_by_id(task_id)
        if task is None:
            return None
        items = await self._build_task_views([task], media_id=task.media_id)
        if not items:
            return None
        return TaskDetailResponseModel(task=items[0], raw_task=task)

    async def get_task_view(self, task_id: str) -> TaskViewItem | None:
        task = await download_service.find_task_by_id(task_id)
        if task is None:
            return None
        items = await self._build_task_views([task], media_id=task.media_id)
        if not items:
            return None
        return items[0]

    async def _build_task_views(
        self,
        tasks: list[TaskData],
        *,
        media_id: MediaID | None = None,
    ) -> list[TaskViewItem]:
        if not tasks:
            return []

        realtime_map = await download_service.get_torrent_status_by_task_ids([task.id for task in tasks if task.id])
        if media_id is not None:
            active_commands = await command_service.list_media_active_commands(media_id)
        else:
            active_commands = await command_service.list_active_commands(
                target_type=CommandTargetType.TASK,
                target_ids=[task.id for task in tasks if task.id],
            )
        active_command_map = {
            command.target_id: command
            for command in active_commands
            if command.target_type == CommandTargetType.TASK and command.target_id
        }
        task_ids = [task.id for task in tasks if task.id]
        library_files_by_task = await library_service.get_files_by_tasks(task_ids)
        tags = settings_service.list_tags()
        action_contexts = await asyncio.gather(
            *[
                self._resolve_action_context(task_id, library_files)
                for task_id, library_files in library_files_by_task.items()
            ],
        )
        media_server_sync_available = {
            task_id: media_server_sync
            for task_id, media_server_sync, _danmu in action_contexts
        }
        danmu_generate_available = {
            task_id: danmu
            for task_id, _media_server_sync, danmu in action_contexts
        }
        items: list[TaskViewItem] = []
        for task in tasks:
            realtime = realtime_map[task.id] if task.id in realtime_map else None
            active_command = active_command_map[task.id] if task.id in active_command_map else None
            library_files = library_files_by_task.get(task.id, [])
            has_primary_library_files = any(
                library_service.is_primary_file(library_file)
                for library_file in library_files
            )
            items.append(
                self._build_task_view(
                    task,
                    realtime,
                    active_command,
                    has_primary_library_files,
                    can_media_server_sync=media_server_sync_available.get(task.id, False),
                    can_danmu_generate=danmu_generate_available.get(task.id, False),
                    tags=tags,
                )
            )
        return items

    async def _resolve_action_context(
        self,
        task_id: str,
        library_files: list,
    ) -> tuple[str, bool, bool]:
        media_server_sync_available, danmu_available = await asyncio.gather(
            media_server_sync_service.can_rerun_for_library_files(library_files),
            danmu_application_service.can_run_for_library_files(library_files),
        )
        return task_id, media_server_sync_available, danmu_available

    def _build_task_view(
        self,
        task: TaskData,
        realtime: TorrentStatus | None,
        active_command: CommandRecord | None,
        has_primary_library_files: bool,
        *,
        can_media_server_sync: bool = False,
        can_danmu_generate: bool = False,
        tags: list[Tag] | None = None,
    ) -> TaskViewItem:
        context = task.context
        search_result = context.search_result if context else None
        attributes, selected_season, selected_episodes, partial_selection = self._resolve_display_attributes(task)
        display_attributes = self._build_display_attributes(attributes, tags=tags or [])
        title = None
        if search_result and search_result.title:
            title = search_result.title
        elif context and context.resource_title:
            title = context.resource_title
        elif task.metadata and task.metadata.name:
            title = task.metadata.name

        description = search_result.description if search_result and search_result.description else None
        size = self._resolve_task_size(task)
        phase, phase_group, phase_label_key, attention_reason_key = self._resolve_phase(task, realtime)
        realtime_view = self._build_realtime_view(task, realtime)
        action_states = self._resolve_action_states(
            task,
            realtime,
            active_command,
            has_primary_library_files,
            can_media_server_sync=can_media_server_sync,
            can_danmu_generate=can_danmu_generate,
        )
        actions = [item.action for item in action_states if item.available]
        indexer = context.indexer if context else None
        site = search_result.site if search_result and search_result.site else indexer
        page_url = context.page_url if context else None
        detail_url = search_result.detail_url if search_result else None
        torrent_url = search_result.torrent_url if search_result else None
        directory_id = context.directory_id if context else None

        return TaskViewItem(
            id=task.id,
            status=task.status,
            phase=phase,
            phase_group=phase_group,
            phase_label="",
            phase_label_key=phase_label_key,
            actions=actions,
            action_states=action_states,
            error_stage=task.error_stage,
            error_key=task.error_key,
            error_params=task.error_params,
            attention_reason_key=attention_reason_key,
            progress=realtime.progress if realtime and realtime.progress is not None else task.progress,
            created_at=task.created_at,
            save_path=task.save_path,
            directory_id=directory_id,
            directory_name=self._directory_name(directory_id),
            media_type=task.media_id.media_type.value if task.media_id else None,
            media_id=str(task.media_id) if task.media_id else None,
            torrent_hash=task.torrent_hash,
            downloader_id=task.downloader_id,
            download_client=task.download_client,
            download_client_url=task.download_client_url,
            title=title,
            description=description,
            size=size,
            indexer=indexer,
            site=site,
            page_url=page_url,
            detail_url=detail_url,
            torrent_url=torrent_url,
            attributes=display_attributes,
            selected_season=selected_season,
            selected_episodes=selected_episodes,
            partial_selection=partial_selection,
            has_primary_library_files=has_primary_library_files,
            realtime=realtime_view,
            active_command_type=active_command.type.value if active_command else None,
            active_command_id=active_command.id if active_command else None,
        )

    def _directory_name(self, directory_id: str | None) -> str | None:
        if not directory_id:
            return None
        directory = settings_service.get_directory_by_id(directory_id)
        return directory.name if directory else None

    def _task_matches_season(self, task: TaskData, season_number: int) -> bool:
        coverage = download_service.resolve_task_episode_coverage_detail(task)
        return coverage.has_known_season and coverage.season_number == season_number

    def _resolve_display_attributes(self, task: TaskData) -> tuple[ResourceAttributes, int | None, list[int], bool]:
        context = task.context
        base_attributes = context.parsed_attributes if context and context.parsed_attributes else ResourceAttributes()
        attributes = self._merge_metadata_display_attributes(
            base_attributes,
            task.metadata.attrs if task.metadata and task.metadata.attrs else None,
        )
        disc_total = self._count_selected_disc_roots(task)
        if disc_total is not None:
            attributes = attributes.model_copy(update={"disc_number": None, "disc_total": disc_total})

        if task.media_id.media_type != MediaType.tv:
            return attributes, None, [], False

        selected_indices = set(context.selected_files or []) if context and context.selected_files else None
        if not task.metadata or not task.metadata.files or not selected_indices:
            return attributes, None, [], False

        selected_seasons: set[int] = set()
        selected_episodes: set[int] = set()
        for index, file_item in enumerate(task.metadata.files):
            if index not in selected_indices:
                continue
            if file_item.attrs and file_item.attrs.seasons:
                for season in file_item.attrs.seasons:
                    normalized_season = _as_positive_int(season)
                    if normalized_season is not None:
                        selected_seasons.add(normalized_season)
            if file_item.attrs and file_item.attrs.episodes:
                for episode in file_item.attrs.episodes:
                    normalized_episode = _as_positive_int(episode)
                    if normalized_episode is not None:
                        selected_episodes.add(normalized_episode)

        available_episodes = task.metadata.get_episodes()
        selected_episode_list = sorted(selected_episodes)
        selected_season = sorted(selected_seasons)[0] if selected_seasons else None
        if not available_episodes or not selected_episode_list:
            return attributes, selected_season, selected_episode_list, False

        partial_selection = selected_episodes != available_episodes
        return attributes, selected_season, selected_episode_list, partial_selection

    def _merge_metadata_display_attributes(
        self,
        base_attributes: ResourceAttributes,
        metadata_attributes: ResourceAttributes | None,
    ) -> ResourceAttributes:
        attributes = base_attributes.model_copy(deep=True)
        if metadata_attributes is None:
            return attributes

        updates = {}
        if (
            metadata_attributes.resource_form
            and (
                not attributes.resource_form
                or metadata_attributes.resource_form_evidence == ResourceFormEvidence.TORRENT_STRUCTURE
            )
        ):
            updates["resource_form"] = metadata_attributes.resource_form
            updates["resource_form_evidence"] = metadata_attributes.resource_form_evidence
        if metadata_attributes.package_layout and not attributes.package_layout:
            updates["package_layout"] = metadata_attributes.package_layout
        if metadata_attributes.sources:
            sources = list(attributes.sources or [])
            for source in metadata_attributes.sources:
                if source not in sources:
                    sources.append(source)
            updates["sources"] = sources
        if updates:
            attributes = attributes.model_copy(update=updates)
        return attributes

    def _build_display_attributes(self, attributes: ResourceAttributes, *, tags: list[Tag]) -> ResourceDisplayAttributes:
        return ResourceDisplayAttributes.model_validate(
            attributes.model_dump(mode="python") | {"tags": resolve_display_tags(attributes, tags=tags)}
        )

    def _count_selected_disc_roots(self, task: TaskData) -> int | None:
        if not task.metadata or not task.metadata.attrs or not task.metadata.attrs.package_layout:
            return None
        selected_indices = set(task.context.selected_files or []) if task.context and task.context.selected_files else None
        roots: set[str] = set()
        for index, file_item in enumerate(task.metadata.files):
            if selected_indices is not None and index not in selected_indices:
                continue
            parts = [part for part in file_item.filename.replace("\\", "/").split("/") if part]
            upper_parts = [part.upper() for part in parts]
            marker_index = next((upper_parts.index(marker) for marker in ("BDMV", "CERTIFICATE", "VIDEO_TS") if marker in upper_parts), -1)
            if marker_index > 0:
                roots.add("/".join(parts[:marker_index]))
                continue
            if task.metadata.attrs.package_layout == "ISO" and parts:
                roots.add(parts[0])
        if roots:
            return len(roots)
        if task.metadata.attrs.disc_number is not None and task.metadata.attrs.disc_number > 0:
            return 1
        return None

    def _build_realtime_view(self, task: TaskData, realtime: TorrentStatus | None) -> TaskRealtimeView:
        if realtime is None:
            return TaskRealtimeView(
                available=not self._expects_realtime_status(task),
                progress=task.progress if task.progress is not None else None,
            )
        return TaskRealtimeView(
            available=True,
            torrent_state=realtime.state,
            download_speed=realtime.download_speed,
            upload_speed=realtime.upload_speed,
            eta=realtime.eta,
            num_seeds=realtime.num_seeds,
            num_leechs=realtime.num_leechs,
            progress=realtime.progress,
        )

    def _expects_realtime_status(self, task: TaskData) -> bool:
        return task.status in [
            TaskStatus.PENDING,
            TaskStatus.DOWNLOADING,
            TaskStatus.PAUSED,
        ]

    def _resolve_phase(
        self,
        task: TaskData,
        realtime: TorrentStatus | None,
    ) -> tuple[TaskPhase, TaskPhaseGroup, str, str | None]:
        if task.status == TaskStatus.PENDING:
            if realtime and realtime.state == TorrentState.DOWNLOADING:
                return TaskPhase.DOWNLOADING, TaskPhaseGroup.DOWNLOADING, "taskLive.status.downloading", None
            if realtime and realtime.state == TorrentState.PAUSED:
                return TaskPhase.PAUSED, TaskPhaseGroup.DOWNLOADING, "taskLive.status.paused", None
            return TaskPhase.QUEUED, TaskPhaseGroup.QUEUED, "taskLive.status.queued", None
        if task.status == TaskStatus.DOWNLOADING:
            if realtime and realtime.state == TorrentState.PAUSED:
                return TaskPhase.PAUSED, TaskPhaseGroup.DOWNLOADING, "taskLive.status.paused", None
            return TaskPhase.DOWNLOADING, TaskPhaseGroup.DOWNLOADING, "taskLive.status.downloading", None
        if task.status == TaskStatus.PAUSED:
            if realtime and realtime.state == TorrentState.DOWNLOADING:
                return TaskPhase.DOWNLOADING, TaskPhaseGroup.DOWNLOADING, "taskLive.status.downloading", None
            return TaskPhase.PAUSED, TaskPhaseGroup.DOWNLOADING, "taskLive.status.paused", None
        if task.status == TaskStatus.FINISHED:
            return TaskPhase.READY_TO_IMPORT, TaskPhaseGroup.READY_TO_IMPORT, "taskLive.status.readyToImport", None
        if task.status == TaskStatus.TRANSFERRING:
            return TaskPhase.IMPORTING, TaskPhaseGroup.IMPORTING, "taskLive.status.importing", None
        if task.status == TaskStatus.MIGRATING:
            return TaskPhase.MIGRATING, TaskPhaseGroup.MIGRATING, "taskLive.status.migrating", None
        if task.status == TaskStatus.COMPLETED:
            return TaskPhase.COMPLETED, TaskPhaseGroup.COMPLETED, "taskLive.status.completed", None
        if task.status == TaskStatus.PARTIAL_MISSING:
            return TaskPhase.ATTENTION, TaskPhaseGroup.ATTENTION, "taskStatus.status.partialMissing", "taskStatus.warning.partialMissing"
        if task.status == TaskStatus.SEEDING_ABSENT:
            return TaskPhase.ATTENTION, TaskPhaseGroup.ATTENTION, "taskStatus.status.seedingAbsent", "taskStatus.warning.seedingAbsent"
        if task.status == TaskStatus.FILE_MISSING:
            return TaskPhase.ATTENTION, TaskPhaseGroup.ATTENTION, "taskStatus.status.fileMissing", "taskStatus.warning.fileMissing"
        if task.status == TaskStatus.ERROR:
            return TaskPhase.FAILED, TaskPhaseGroup.FAILED, "taskLive.status.failed", self._resolve_failed_reason(task)
        return TaskPhase.FAILED, TaskPhaseGroup.FAILED, "taskLive.status.failed", self._resolve_failed_reason(task)

    def _resolve_failed_reason(self, task: TaskData) -> str | None:
        if task.error_stage == TaskErrorStage.TRANSFER:
            return "taskStatus.stage.transfer"
        if task.error_stage == TaskErrorStage.DOWNLOAD:
            return "taskStatus.stage.download"
        if task.error_stage == TaskErrorStage.SYSTEM:
            return "taskStatus.stage.system"
        return task.error_key or None

    def _resolve_action_states(
        self,
        task: TaskData,
        realtime: TorrentStatus | None,
        active_command: CommandRecord | None,
        has_primary_library_files: bool,
        *,
        can_media_server_sync: bool = False,
        can_danmu_generate: bool = False,
    ) -> list[TaskActionState]:
        action_states = [TaskActionState(action=TaskAction.VIEW_DETAIL)]

        if task.status == TaskStatus.MIGRATING:
            action_states.extend(
                self._disabled_migrating_action(action)
                for action in (
                    TaskAction.TRANSFER,
                    TaskAction.MEDIA_SERVER_SYNC,
                    TaskAction.DANMU_GENERATE,
                    TaskAction.CHANGE_DOWNLOADER,
                    TaskAction.DELETE,
                )
            )
            return action_states

        if task.status in {TaskStatus.PENDING, TaskStatus.DOWNLOADING, TaskStatus.PAUSED}:
            torrent_state = realtime.state if realtime else None
            if torrent_state is None:
                if task.status == TaskStatus.DOWNLOADING:
                    torrent_state = TorrentState.DOWNLOADING
                elif task.status == TaskStatus.PAUSED:
                    torrent_state = TorrentState.PAUSED
            if torrent_state == TorrentState.DOWNLOADING:
                action_states.append(TaskActionState(action=TaskAction.PAUSE))
            elif torrent_state == TorrentState.PAUSED:
                action_states.append(TaskActionState(action=TaskAction.RESUME))

        if self._can_manual_transfer(task):
            action_states.append(TaskActionState(action=TaskAction.TRANSFER))

        if has_primary_library_files and can_media_server_sync:
            action_states.append(TaskActionState(action=TaskAction.MEDIA_SERVER_SYNC))
        if has_primary_library_files and can_danmu_generate:
            action_states.append(TaskActionState(action=TaskAction.DANMU_GENERATE))

        if task.status != TaskStatus.MIGRATING and task.downloader_id and task.torrent_hash and task.save_path:
            action_states.append(TaskActionState(action=TaskAction.CHANGE_DOWNLOADER))

        if task.status != TaskStatus.MIGRATING:
            action_states.append(TaskActionState(action=TaskAction.DELETE))
        if active_command is None:
            return action_states

        return [
            self._apply_active_command_state(item, active_command)
            for item in action_states
        ]

    @staticmethod
    def _disabled_migrating_action(action: TaskAction) -> TaskActionState:
        return TaskActionState(
            action=action,
            disabled=True,
            disabled_reason_key="taskLive.taskProcessing",
        )

    @staticmethod
    def _apply_active_command_state(action_state: TaskActionState, active_command: CommandRecord) -> TaskActionState:
        if action_state.action == TaskAction.VIEW_DETAIL:
            return action_state
        return action_state.model_copy(
            update={
                "loading": True,
                "disabled": True,
                "disabled_reason_key": "taskLive.taskProcessing",
                "active_command_id": active_command.id,
                "active_command_type": active_command.type.value,
            }
        )

    def _can_manual_transfer(self, task: TaskData) -> bool:
        if task.status in {
            TaskStatus.FINISHED,
            TaskStatus.COMPLETED,
            TaskStatus.PARTIAL_MISSING,
            TaskStatus.FILE_MISSING,
        }:
            return True
        if task.status == TaskStatus.ERROR:
            progress = task.progress or 0
            return (task.error_stage in {TaskErrorStage.TRANSFER, None}) and progress >= 0.999
        return False

    def _resolve_task_size(self, task: TaskData) -> int:
        search_result = task.context.search_result if task.context else None
        size_from_search = self._parse_size_to_int(search_result.size if search_result else None)
        size_from_metadata = int(task.metadata.size) if task.metadata and task.metadata.size else 0
        return size_from_search or size_from_metadata

    def _parse_size_to_int(self, value: str | None) -> int:
        if value is None:
            return 0
        raw = value.strip()
        if not raw:
            return 0
        if raw.isdigit():
            return int(raw)
        normalized = raw.replace(",", "").upper()
        units = [
            ("TB", 1024 ** 4),
            ("GB", 1024 ** 3),
            ("MB", 1024 ** 2),
            ("KB", 1024),
            ("B", 1),
        ]
        for unit, multiplier in units:
            if normalized.endswith(unit):
                number_part = normalized[:-len(unit)].strip()
                try:
                    return int(float(number_part) * multiplier)
                except ValueError:
                    return 0
        try:
            return int(float(normalized))
        except ValueError:
            return 0


task_view_service = TaskViewService()
