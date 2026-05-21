from app.schemas.config import MediaServerProviderConfig
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media_server_link import MediaServerDetailLink
from app.schemas.exception.exceptions import InvalidRequestException, ResourceNotFoundException
from app.schemas.runtime.library_resource_list import LibraryMediaServerLinkResolveRequest
from app.services.config.settings_service import settings_service
from app.services.domain.library.service import library_service
from app.services.integration.media_server import media_server_gateway
from app.utils.library_paths import build_library_file_path


class LibraryMediaServerLinkService:
    async def resolve(self, request: LibraryMediaServerLinkResolveRequest) -> MediaServerDetailLink:
        files = await self._resolve_target_files(request)
        candidate = self._select_detail_candidate(files)
        if not candidate:
            raise InvalidRequestException("backendErrors.mediaServerLinkUnavailable")

        media_server = self._resolve_media_server(candidate.directory_id)
        if not media_server:
            raise InvalidRequestException("backendErrors.mediaServerLinkUnavailable")

        detail_link = await media_server_gateway.resolve_detail_link(
            media_server,
            str(build_library_file_path(candidate.path, candidate.file_name)),
        )
        if not detail_link:
            raise InvalidRequestException("backendErrors.mediaServerLinkNotFound")
        return detail_link

    async def _resolve_target_files(self, request: LibraryMediaServerLinkResolveRequest) -> list[LibraryFile]:
        file = await library_service.find_file_by_id(request.file_id)
        if not file or file.media_id != request.target.media_id:
            raise ResourceNotFoundException("backendErrors.resourceFileNotFound")
        package_root = (request.package_root or "").strip()
        if not package_root:
            return [file]

        media_files = await library_service.get_files_by_media(
            request.target.media_id,
            season=request.target.season_number,
        )
        package_files = [
            item
            for item in media_files
            if item.task_id == file.task_id and library_service.matches_package_root(item, package_root)
        ]
        return package_files or [file]

    def _select_detail_candidate(self, files: list[LibraryFile]) -> LibraryFile | None:
        for file in sorted(files, key=lambda item: str(build_library_file_path(item.path, item.file_name))):
            if not library_service.is_primary_file(file):
                continue
            if self._resolve_media_server(file.directory_id):
                return file
        return None

    def _resolve_media_server(self, directory_id: str) -> MediaServerProviderConfig | None:
        if not directory_id:
            return None
        directory = settings_service.get_directory_by_id(directory_id)
        if not directory or not directory.enabled or not directory.media_server_id:
            return None
        return next(
            (
                media_server
                for media_server in settings_service.list_media_servers()
                if media_server.id == directory.media_server_id and media_server.enabled
            ),
            None,
        )


library_media_server_link_service = LibraryMediaServerLinkService()
