import os
import logging
from urllib.parse import urlencode

import httpx
from app.clients.base import MediaServerClient
from app.schemas.config import JellyfinConfig
from app.schemas.integration.media_server import JellyfinLibrary
from app.schemas.domain.media_server_link import MediaServerDetailLink
from app.schemas.domain.media_server_sync import MediaServerChange, MediaServerChangeType
from app.schemas.exception.exceptions import InvalidRequestException
from app.utils.path_utils import PathMapper


class JellyfinClient(MediaServerClient):
    """Jellyfintext"""
    
    def __init__(self, config: JellyfinConfig | None = None) -> None:
        """textJellyfintext
        
        Args:
            config: Jellyfintext
        """
        self.config = config
        self.url = config.url.rstrip('/') if config and config.url else ''
        self.api_key = config.api_key if config else ''
        self.timeout = 10
        self._logger = logging.getLogger("app.clients.jellyfin")
    
    def get_id(self) -> str:
        """identifier
        
        Returns:
            str: identifier
        """
        if self.config:
            return self.config.id
        return 'jellyfin_default'
    
    async def test_connection(self) -> bool:
        """textJellyfintext
        
        Returns:
            bool: textTrue，textFalse
        """
        if not self.url or not self.api_key:
            return False
        
        try:
            # Internal note.
            api_url = f"{self.url}/System/Info"
            headers = {
                'X-Emby-Token': self.api_key,
                'Accept': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(api_url, headers=headers)
                return response.status_code == 200
        except httpx.HTTPError:
            return False
    
    async def get_libraries(self) -> list[JellyfinLibrary]:
        """text
        
        Returns:
            List[JellyfinLibrary]: text
        """
        if not self.url or not self.api_key:
            return []
        
        try:
            # Internal note.
            api_url = f"{self.url}/Library/MediaFolders"
            headers = {
                'X-Emby-Token': self.api_key,
                'Accept': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(api_url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('Items', [])
                    return [JellyfinLibrary.model_validate(item) for item in items]
                return []
        except (httpx.HTTPError, ValueError):
            return []
    
    async def add_media(self, library_id: str, media_path: str) -> bool:
        """text
        
        Args:
            library_id: identifier
            media_path: text
            
        Returns:
            bool: textTrue，textFalse
        """
        if not self.url or not self.api_key or not library_id or not media_path:
            return False
        
        try:
            # Internal note.
            api_url = f"{self.url}/Library/VirtualFolders/{library_id}/Refresh"
            headers = {
                'X-Emby-Token': self.api_key,
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # Internal note.
            payload = {
                'Paths': [media_path],
                'Recursive': True
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(api_url, headers=headers, json=payload)
                return response.status_code == 204
        except httpx.HTTPError as exc:
            self._logger.warning("Jellyfin add_media failed: %s", exc)
            return False

    def _to_jellyfin_update_type(self, change_type: MediaServerChangeType) -> str:
        if change_type == MediaServerChangeType.CREATED:
            return "Created"
        if change_type == MediaServerChangeType.DELETED:
            return "Deleted"
        return "Modified"

    async def notify_changes(self, changes: list[MediaServerChange]) -> bool:
        if not self.url or not self.api_key or not changes:
            return False
        try:
            api_url = f"{self.url}/Library/Media/Updated"
            headers = {
                'X-Emby-Token': self.api_key,
                'Accept': 'text/html',
                'Content-Type': 'application/json'
            }
            updates = []
            debug_changes: list[dict[str, str | bool | None]] = []
            for change in changes:
                if not change.target_path:
                    continue
                mapped_path = self._map_media_path(change.target_path)
                update_type = self._to_jellyfin_update_type(change.change_type)
                updates.append({"Path": mapped_path, "UpdateType": update_type})
                debug_changes.append(
                    {
                        "path": change.target_path,
                        "mapped_path": mapped_path,
                        "change_type": change.change_type.value,
                        "update_type": update_type,
                        "is_media_root": change.is_media_root,
                    }
                )
            if not updates:
                return False
            payload = {
                "Updates": updates
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(api_url, headers=headers, json=payload)
                if response.status_code in (200, 204):
                    self._logger.debug(
                        "Jellyfin notify_changes succeeded: status=%s changes=%s",
                        response.status_code,
                        debug_changes,
                    )
                    return True
                body = ""
                try:
                    body = response.text[:500]
                except (TypeError, ValueError):
                    body = ""
                self._logger.warning(
                    "Jellyfin notify_changes failed: status=%s url=%s body=%s changes=%s",
                    response.status_code,
                    api_url,
                    body,
                    debug_changes,
                )
                return False
        except httpx.HTTPError as exc:
            self._logger.warning("Jellyfin notify_changes exception: %s", exc)
            return False

    async def notify_updated_media(self, media_paths: list[str]) -> bool:
        changes = [
            MediaServerChange(
                target_path=path,
                change_type=MediaServerChangeType.UPDATED,
            )
            for path in media_paths
            if path
        ]
        return await self.notify_changes(changes)

    async def refresh_library(self) -> bool:
        if not self.url or not self.api_key:
            return False
        try:
            api_url = f"{self.url}/Library/Refresh"
            headers = {
                'X-Emby-Token': self.api_key,
                'Accept': 'text/html',
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(api_url, headers=headers)
                if response.status_code in (200, 204):
                    self._logger.debug(
                        "Jellyfin refresh_library succeeded: status=%s url=%s",
                        response.status_code,
                        api_url,
                    )
                    return True
                body = ""
                try:
                    body = response.text[:500]
                except (TypeError, ValueError):
                    body = ""
                self._logger.warning(
                    "Jellyfin refresh_library failed: status=%s url=%s body=%s",
                    response.status_code,
                    api_url,
                    body,
                )
                return False
        except httpx.HTTPError as exc:
            self._logger.warning("Jellyfin refresh_library exception: %s", exc)
            return False

    async def resolve_detail_link(self, media_path: str) -> MediaServerDetailLink | None:
        if not self.url or not self.api_key or not media_path:
            return None
        mapped_path = self._map_media_path(media_path)
        item = await self._find_item_by_path(mapped_path)
        if not item:
            item = await self._find_parent_item_by_path(mapped_path)
        item_id = str(item.get("Id") or "").strip() if item else ""
        if not item_id:
            return None
        return MediaServerDetailLink(
            media_server_id=self.get_id(),
            media_server_type="jellyfin",
            detail_url=await self._build_web_detail_url(item_id),
        )

    async def _find_item_by_path(
        self,
        media_path: str,
        *,
        include_item_types: str = "Movie,Episode,Video",
    ) -> dict | None:
        target_path = self._normalize_path(media_path)
        file_name = os.path.basename(target_path)
        base_params = {
            "Recursive": "true",
            "Fields": "Path",
            "IncludeItemTypes": include_item_types,
        }
        params = dict(base_params)
        if file_name:
            params["SearchTerm"] = file_name.rsplit(".", 1)[0]
        item = await self._find_item_by_path_with_params(target_path, params)
        if item or "SearchTerm" not in params:
            return item
        return await self._find_item_by_path_with_params(target_path, base_params)

    async def _find_parent_item_by_path(self, media_path: str) -> dict | None:
        for path in self._detail_parent_paths(media_path):
            item = await self._find_item_by_path(
                path,
                include_item_types="Movie,Series,Season,Folder",
            )
            if item:
                return item
        return None

    async def _find_item_by_path_with_params(self, target_path: str, params: dict[str, str]) -> dict | None:
        try:
            api_url = f"{self.url}/Items"
            headers = {
                "X-Emby-Token": self.api_key,
                "Accept": "application/json",
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(api_url, headers=headers, params=params)
                if response.status_code in (401, 403):
                    raise InvalidRequestException("backendErrors.mediaServerAuthenticationFailed")
                if response.status_code != 200:
                    self._logger.warning(
                        "Jellyfin media server link lookup failed: status=%s path=%s",
                        response.status_code,
                        target_path,
                    )
                    return None
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            self._logger.warning("Jellyfin media server link lookup exception: path=%s error=%s", target_path, exc)
            return None

        for item in data.get("Items", []) or []:
            if self._normalize_path(str(item.get("Path") or "")) == target_path:
                return item
        return None

    async def _build_web_detail_url(self, item_id: str) -> str:
        server_id = await self._get_server_id()
        query = urlencode({"id": item_id, **({"serverId": server_id} if server_id else {})})
        return f"{self.url}/web/index.html#!/details?{query}"

    async def _get_server_id(self) -> str | None:
        try:
            api_url = f"{self.url}/System/Info"
            headers = {
                "X-Emby-Token": self.api_key,
                "Accept": "application/json",
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(api_url, headers=headers)
                if response.status_code != 200:
                    return None
                data = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        value = data.get("Id") or data.get("ServerId")
        return str(value).strip() if value else None

    def _normalize_path(self, path: str) -> str:
        normalized = os.path.normpath(path or "")
        return normalized.replace("\\", "/")

    def _map_media_path(self, media_path: str) -> str:
        """Internal helper."""
        mappings = self.config.path_mappings if self.config and self.config.path_mappings else []
        mapper = PathMapper(mappings)
        return mapper.to_remote(media_path)

    def _detail_parent_paths(self, media_path: str) -> list[str]:
        paths: list[str] = []
        current = self._normalize_path(media_path)
        for _ in range(2):
            parent = self._normalize_path(os.path.dirname(current))
            if not parent or parent in {".", "/", current}:
                break
            paths.append(parent)
            current = parent
        return paths

    def _extract_library_paths(self, library: JellyfinLibrary) -> list[str]:
        candidates = []
        if library.Locations:
            candidates.extend(library.Locations)
        if library.Paths:
            candidates.extend(library.Paths)
        if library.Path:
            candidates.append(library.Path)
        return [self._normalize_path(path) for path in candidates if path]

    def _find_library_id(self, libraries: list[JellyfinLibrary], media_path: str) -> str | None:
        target_path = self._normalize_path(media_path)
        best_library_id = None
        best_length = -1
        for library in libraries:
            library_id = library.ItemId or library.Id
            if not library_id:
                continue
            for library_path in self._extract_library_paths(library):
                if target_path == library_path or target_path.startswith(f"{library_path}/"):
                    if len(library_path) > best_length:
                        best_library_id = library_id
                        best_length = len(library_path)
        return best_library_id

    async def apply_changes(self, changes: list[MediaServerChange]) -> bool:
        if not self.url or not self.api_key or not changes:
            return False
        primary_change = next((change for change in changes if change.target_path), None)
        if primary_change is None:
            return False
        mapped_path = self._map_media_path(primary_change.target_path)
        self._logger.debug(
            "Jellyfin apply_changes start: primary_local_path=%s primary_mapped_path=%s changes=%s",
            primary_change.target_path,
            mapped_path,
            [
                {
                    "path": change.target_path,
                    "change_type": change.change_type.value,
                    "is_media_root": change.is_media_root,
                }
                for change in changes
            ],
        )
        updated_ok = await self.notify_changes(changes)
        if updated_ok:
            self._logger.debug(
                "Jellyfin apply_changes completed via media-updated: primary_local_path=%s primary_mapped_path=%s",
                primary_change.target_path,
                mapped_path,
            )
            return True
        self._logger.debug(
            "Jellyfin apply_changes falling back to library refresh: primary_local_path=%s primary_mapped_path=%s",
            primary_change.target_path,
            mapped_path,
        )
        return await self.refresh_library()

    async def refresh_path(self, media_path: str) -> bool:
        if not media_path:
            return False
        return await self.apply_changes(
            [
                MediaServerChange(
                    target_path=media_path,
                    change_type=MediaServerChangeType.UPDATED,
                )
            ]
        )
