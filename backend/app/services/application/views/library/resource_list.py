import asyncio
from dataclasses import dataclass, field
import logging
import time

from app.schemas.domain.command import CommandRecord, CommandTargetType, CommandType
from app.schemas.config import DanmuAddonConfig, Tag
from app.schemas.domain.library import LibraryFile, LibraryPackageSummary
from app.schemas.domain.media import MediaFullInfo, MediaSimpleInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.media_id import MediaID
from app.schemas.runtime.library_resource_list import (
    LibraryListAttributes,
    LibraryListResponse,
    LibraryResourceAction,
    LibraryResourceActionState,
    LibraryResourceListItem,
)
from app.services.application.commands.service import command_service
from app.services.application.workflows.danmu import danmu_application_service
from app.services.application.workflows.danmu.source_resolver import danmu_source_resolver
from app.services.application.workflows.media_server_sync.config import media_server_sync_config
from app.services.config.settings_service import settings_service
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service
from app.services.domain.media import media_service
from app.services.domain.resource.tags import resolve_display_tags
from app.utils.library_paths import normalize_path_separators


logger = logging.getLogger("app.library_resource_list")


@dataclass(frozen=True)
class _LibraryActionAvailabilityContext:
    media_server_open_enabled_directory_ids: set[str]
    media_server_sync_enabled_directory_ids: set[str]
    danmu_enabled_directory_ids: set[str]
    danmu_media_available: bool
    existing_task_ids: set[str] = field(default_factory=set)


class LibraryResourceListService:
    def _record_elapsed(self, timings: dict[str, float], name: str, started_at: float) -> None:
        timings[name] = (time.perf_counter() - started_at) * 1000

    def _log_timing(
        self,
        *,
        timings: dict[str, float],
        started_at: float,
        media_id: MediaID,
        season_number: int | None,
        resource_count: int,
        file_count: int,
    ) -> None:
        total_ms = (time.perf_counter() - started_at) * 1000
        timing_text = " ".join(f"{key}_ms={value:.1f}" for key, value in sorted(timings.items()))
        logger.info(
            "library_resource_list_timing total_ms=%.1f media_id=%s season=%s resources=%s files=%s %s",
            total_ms,
            media_id,
            season_number,
            resource_count,
            file_count,
            timing_text,
        )

    async def list_resources(
        self,
        media_id: MediaID,
        *,
        season_number: int | None = None,
    ) -> LibraryListResponse:
        request_started_at = time.perf_counter()
        timings: dict[str, float] = {}

        phase_started_at = time.perf_counter()
        media = await media_service.simple_info(media_id)
        self._record_elapsed(timings, "simple_info", phase_started_at)
        if media:
            media = media_service.apply_season_context(media, season_number)
        active_season_number = media.season_number if media and media.media_type == MediaType.tv else None
        media_with_seasons = None
        if active_season_number is not None:
            phase_started_at = time.perf_counter()
            media_with_seasons = await media_service.cached_info(media_id)
            self._record_elapsed(timings, "cached_info", phase_started_at)
            if media_with_seasons is None:
                phase_started_at = time.perf_counter()
                media_with_seasons = await media_service.season_detail_for_library_view(
                    media_id,
                    season_number=active_season_number,
                )
                self._record_elapsed(timings, "season_detail", phase_started_at)
            elif media_with_seasons:
                media_with_seasons = media_service.apply_season_context(media_with_seasons, active_season_number)

        phase_started_at = time.perf_counter()
        active_commands, library_files = await asyncio.gather(
            command_service.list_media_active_commands(
                media_id,
                season_number=active_season_number,
            ),
            library_service.get_files_by_media(media_id, season=active_season_number),
        )
        self._record_elapsed(timings, "commands_and_files", phase_started_at)

        phase_started_at = time.perf_counter()
        response = await self._build_response(
            media_id=media_id,
            active_season_number=active_season_number,
            total_episodes=self._resolve_total_episodes(media, media_with_seasons),
            full_media=media_with_seasons,
            active_commands=active_commands,
            library_files=library_files,
        )
        self._record_elapsed(timings, "build_response", phase_started_at)
        self._log_timing(
            timings=timings,
            started_at=request_started_at,
            media_id=media_id,
            season_number=active_season_number,
            resource_count=len(response.resources),
            file_count=len(library_files),
        )
        return response

    async def _build_response(
        self,
        *,
        media_id: MediaID,
        active_season_number: int | None,
        total_episodes: int,
        full_media: MediaFullInfo | None,
        active_commands: list[CommandRecord],
        library_files: list[LibraryFile],
    ) -> LibraryListResponse:
        tags = settings_service.list_tags()
        resources = self._build_resource_list(library_files, tags=tags)
        resource_files_map = self._build_resource_files_map(resources, library_files)
        active_command_map = self._build_active_command_map(active_commands)
        action_context = await self._build_action_availability_context(
            library_files,
            media_id=media_id,
            season_number=active_season_number,
            full_media=full_media,
        )
        action_context_map = await self._resolve_action_context_map(resources, resource_files_map, action_context)
        return LibraryListResponse(
            media_id=media_id,
            total_episodes=total_episodes,
            resources=[
                self._apply_action_states(
                    resource,
                    active_command_map.get(self._resource_target_id(resource)),
                    action_context_map.get(self._resource_target_id(resource), (False, False)),
                )
                for resource in resources
            ],
        )

    def _resolve_total_episodes(
        self,
        simple_media: MediaSimpleInfo | None,
        full_media: MediaFullInfo | None,
    ) -> int:
        if full_media is not None:
            active_season_number = full_media.season_number if full_media.media_type == MediaType.tv else None
            total_episodes = full_media.episodes_count or 0
            if active_season_number is not None:
                matched_season = next(
                    (season for season in full_media.seasons if season.season_number == active_season_number),
                    None,
                )
                if matched_season and matched_season.episode_count is not None:
                    return int(matched_season.episode_count or 0)
            return int(total_episodes)
        return int(simple_media.episodes_count or 0) if simple_media else 0

    def _build_library_list_attributes(self, attrs: ResourceAttributes, *, tags: list[Tag]) -> LibraryListAttributes:
        return LibraryListAttributes(
            groups=attrs.groups or None,
            tags=resolve_display_tags(attrs, tags=tags) or None,
            sources=attrs.sources or None,
            versions=attrs.versions or None,
            seasons=attrs.seasons or None,
            episodes=attrs.episodes or None,
            resolution=attrs.resolution,
            video_codec=attrs.video_codec,
            audio_codec=attrs.audio_codec,
            hdr_type=attrs.hdr_type,
            audio_channels=attrs.audio_channels,
            color_depth=attrs.color_depth,
            language=attrs.language,
            subtitle=attrs.subtitle,
            desc=attrs.desc,
            content_type=attrs.content_type,
            resource_form=attrs.resource_form,
            package_layout=str(attrs.package_layout) if attrs.package_layout else None,
            disc_number=attrs.disc_number,
            disc_total=attrs.disc_total,
        )

    def _resolve_directory_and_filename(self, file: LibraryFile) -> tuple[str | None, str]:
        file_name = file.file_name or file.path.rsplit("/", 1)[-1] or "Unknown resource"
        normalized = normalize_path_separators(file.path or "")
        directory = f"/{normalized.lstrip('/')}" if normalized else "/"
        return directory, file_name

    def _directory_name(self, directory_id: str) -> str:
        directory = settings_service.get_directory_by_id(directory_id)
        return directory.name if directory else ""

    def _build_resource_list_item(self, file: LibraryFile, *, tags: list[Tag]) -> LibraryResourceListItem:
        attrs = file.resource_attributes or ResourceAttributes()
        directory, filename = self._resolve_directory_and_filename(file)
        return LibraryResourceListItem(
            id=file.id,
            task_id=file.task_id,
            directory_id=file.directory_id,
            directory_name=self._directory_name(file.directory_id),
            file_name=filename,
            resource_title=attrs.title or filename,
            directory=directory,
            size=file.file_size or 0,
            created_at=file.created_at,
            attributes=self._build_library_list_attributes(attrs, tags=tags),
        )

    def _build_package_list_item(self, package: LibraryPackageSummary, *, tags: list[Tag]) -> LibraryResourceListItem:
        return LibraryResourceListItem(
            id=package.id,
            task_id=package.task_id,
            directory_id=package.directory_id,
            directory_name=self._directory_name(package.directory_id),
            file_name=package.file_name,
            resource_title=package.resource_title,
            directory=package.directory,
            size=package.total_size,
            created_at=package.created_at,
            attributes=self._build_library_list_attributes(package.resource_attributes, tags=tags),
            is_package=True,
            file_count=package.file_count,
            package_root=package.package_root,
        )

    def _build_resource_list(self, files: list[LibraryFile], *, tags: list[Tag]) -> list[LibraryResourceListItem]:
        resources: list[LibraryResourceListItem] = []
        for file in files:
            if library_service.resolve_package_root(file):
                continue
            if library_service.is_displayable_file(file):
                resources.append(self._build_resource_list_item(file, tags=tags))
        resources.extend(
            self._build_package_list_item(package, tags=tags)
            for package in library_service.build_package_summaries(files)
        )
        return sorted(resources, key=lambda item: item.created_at, reverse=True)

    def _build_resource_files_map(
        self,
        resources: list[LibraryResourceListItem],
        files: list[LibraryFile],
    ) -> dict[str, list[LibraryFile]]:
        out: dict[str, list[LibraryFile]] = {}
        files_by_id = {file.id: file for file in files if file.id}
        for resource in resources:
            target_id = self._resource_target_id(resource)
            if resource.package_root:
                out[target_id] = [
                    file
                    for file in files
                    if file.task_id == resource.task_id and library_service.matches_package_root(file, resource.package_root)
                ]
            else:
                file = files_by_id.get(resource.id)
                out[target_id] = [file] if file else []
        return out

    def _build_active_command_map(self, commands: list[CommandRecord]) -> dict[str, CommandRecord]:
        library_command_types = {
            CommandType.LIBRARY_FILE_DELETE,
            CommandType.LIBRARY_FILE_STORAGE_CHANGE,
            CommandType.LIBRARY_FILE_MEDIA_SERVER_SYNC,
            CommandType.LIBRARY_FILE_DANMU_GENERATE,
        }
        out: dict[str, CommandRecord] = {}
        for command in commands:
            if command.target_type != CommandTargetType.LIBRARY_FILE:
                continue
            if command.type not in library_command_types:
                continue
            if not command.target_id or command.target_id in out:
                continue
            out[command.target_id] = command
        return out

    async def _resolve_action_context_map(
        self,
        resources: list[LibraryResourceListItem],
        resource_files_map: dict[str, list[LibraryFile]],
        context: _LibraryActionAvailabilityContext,
    ) -> dict[str, tuple[bool, bool, bool, bool]]:
        return {
            target_id: self._resolve_action_context(resource_files_map.get(target_id, []), context)
            for resource in resources
            if (target_id := self._resource_target_id(resource))
        }

    async def _build_action_availability_context(
        self,
        library_files: list[LibraryFile],
        *,
        media_id: MediaID,
        season_number: int | None,
        full_media: MediaFullInfo | None,
    ) -> _LibraryActionAvailabilityContext:
        task_ids = sorted({file.task_id for file in library_files if file.task_id})
        existing_tasks = await download_service.get_tasks_by_ids(task_ids)
        open_enabled_media_server_ids = {
            media_server.id
            for media_server in settings_service.list_media_servers()
            if media_server.id and media_server.enabled
        }
        media_server_open_enabled_directory_ids = {
            directory.id
            for directory in settings_service.list_directories()
            if directory.id and directory.enabled and directory.media_server_id in open_enabled_media_server_ids
        }
        sync_enabled_media_server_ids = {
            media_server.id
            for media_server in media_server_sync_config.list_enabled_servers()
            if media_server.id
        }
        media_server_sync_enabled_directory_ids = {
            directory.id
            for directory in settings_service.list_directories()
            if directory.id and directory.enabled and directory.media_server_id in sync_enabled_media_server_ids
        }
        danmu_config = danmu_application_service.config()
        danmu_enabled_directory_ids = set(danmu_config.directory_ids or []) if danmu_config.enabled else set()
        danmu_media_available = await self._resolve_danmu_media_available(
            media_id,
            season_number=season_number,
            full_media=full_media,
            danmu_enabled_directory_ids=danmu_enabled_directory_ids,
            danmu_config=danmu_config,
        )
        return _LibraryActionAvailabilityContext(
            media_server_open_enabled_directory_ids=media_server_open_enabled_directory_ids,
            media_server_sync_enabled_directory_ids=media_server_sync_enabled_directory_ids,
            danmu_enabled_directory_ids=danmu_enabled_directory_ids,
            danmu_media_available=danmu_media_available,
            existing_task_ids=set(existing_tasks.keys()),
        )

    async def _resolve_danmu_media_available(
        self,
        media_id: MediaID,
        *,
        season_number: int | None,
        full_media: MediaFullInfo | None,
        danmu_enabled_directory_ids: set[str],
        danmu_config: DanmuAddonConfig,
    ) -> bool:
        if not danmu_enabled_directory_ids:
            return False
        if full_media and danmu_source_resolver.has_fetchable_vendor(full_media, danmu_config):
            return True
        resolved = await danmu_source_resolver.media_with_fetchable_source(
            media_id,
            season_number=season_number,
            config=danmu_config,
        )
        return bool(resolved and danmu_source_resolver.has_fetchable_vendor(resolved, danmu_config))

    def _resolve_action_context(
        self,
        library_files: list[LibraryFile],
        context: _LibraryActionAvailabilityContext,
    ) -> tuple[bool, bool, bool, bool]:
        if not library_files:
            return False, False, False, False
        primary_existing_files = [
            library_file
            for library_file in library_files
            if library_service.is_primary_file(library_file)
        ]
        if not primary_existing_files:
            return False, False, False, False
        media_server_open_available = any(
            library_file.directory_id in context.media_server_open_enabled_directory_ids
            for library_file in primary_existing_files
        )
        media_server_sync_available = any(
            library_file.directory_id in context.media_server_sync_enabled_directory_ids
            for library_file in primary_existing_files
        )
        danmu_available = bool(
            context.danmu_media_available
            and any(library_file.directory_id in context.danmu_enabled_directory_ids for library_file in primary_existing_files)
        )
        directory_change_available = not any(library_file.task_id in context.existing_task_ids for library_file in library_files)
        return media_server_open_available, media_server_sync_available, danmu_available, directory_change_available

    def _apply_action_states(
        self,
        resource: LibraryResourceListItem,
        active_command: CommandRecord | None,
        action_context: tuple[bool, bool, bool, bool],
    ) -> LibraryResourceListItem:
        media_server_open_available, media_server_sync_available, danmu_available, *rest = action_context
        directory_change_available = rest[0] if rest else False
        states = [
            LibraryResourceActionState(action=LibraryResourceAction.VIEW_DETAIL),
            LibraryResourceActionState(action=LibraryResourceAction.DELETE),
        ]
        if media_server_open_available:
            states.append(LibraryResourceActionState(action=LibraryResourceAction.MEDIA_SERVER_OPEN))
        if media_server_sync_available:
            states.append(LibraryResourceActionState(action=LibraryResourceAction.MEDIA_SERVER_SYNC))
        if danmu_available:
            states.append(LibraryResourceActionState(action=LibraryResourceAction.DANMU_GENERATE))
        if directory_change_available:
            states.append(LibraryResourceActionState(action=LibraryResourceAction.CHANGE_DIRECTORY))
        if active_command:
            states = [self._apply_active_command_state(item, active_command) for item in states]
        return resource.model_copy(
            update={
                "actions": [item.action for item in states if item.available],
                "action_states": states,
            }
        )

    @staticmethod
    def _apply_active_command_state(
        state: LibraryResourceActionState,
        active_command: CommandRecord,
    ) -> LibraryResourceActionState:
        if state.action == LibraryResourceAction.VIEW_DETAIL:
            return state
        return state.model_copy(
            update={
                "loading": True,
                "disabled": True,
                "disabled_reason_key": "taskLive.taskProcessing",
                "active_command_id": active_command.id,
                "active_command_type": active_command.type.value,
            }
        )

    @staticmethod
    def _resource_target_id(resource: LibraryResourceListItem) -> str:
        return resource.package_root if resource.is_package and resource.package_root else resource.id


library_resource_list_service = LibraryResourceListService()
