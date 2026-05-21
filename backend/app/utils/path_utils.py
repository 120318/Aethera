import os
import logging
from pathlib import Path
from typing import List, Optional, Union
from app.schemas.config import PathMapping

logger = logging.getLogger("app.utils.path_mapper")

class PathMapper:
    """Internal helper."""

    def __init__(self, mappings: List[PathMapping]):
        self.mappings = mappings

    def _normalize_path(self, path: Union[str, Path]) -> str:
        """Internal helper."""
        if not path:
            return ""
        normalized = os.path.normpath(str(path))
        return normalized.replace("\\", "/")

    def to_local(self, remote_path: str) -> str:
        """Internal helper."""
        if not remote_path:
            return ""
            
        target_path = self._normalize_path(remote_path)
        
        # Internal note.
        sorted_mappings = sorted(self.mappings, key=lambda m: len(m.remote_path), reverse=True)
        
        for mapping in sorted_mappings:
            m_remote = self._normalize_path(mapping.remote_path)
            m_local = self._normalize_path(mapping.local_path)
            
            if m_remote and m_local and (target_path == m_remote or target_path.startswith(f"{m_remote}/")):
                suffix = target_path[len(m_remote):].lstrip("/")
                mapped = f"{m_local}/{suffix}" if suffix else m_local
                logger.debug("Mapped remote path %s to local path %s", remote_path, mapped)
                return mapped
                
        return target_path

    def to_remote(self, local_path: str) -> str:
        """Internal helper."""
        if not local_path:
            return ""
            
        target_path = self._normalize_path(local_path)
        
        # Internal note.
        sorted_mappings = sorted(self.mappings, key=lambda m: len(m.local_path), reverse=True)
        
        for mapping in sorted_mappings:
            m_remote = self._normalize_path(mapping.remote_path)
            m_local = self._normalize_path(mapping.local_path)
            
            if m_remote and m_local and (target_path == m_local or target_path.startswith(f"{m_local}/")):
                suffix = target_path[len(m_local):].lstrip("/")
                mapped = f"{m_remote}/{suffix}" if suffix else m_remote
                logger.debug("Mapped local path %s to remote path %s", local_path, mapped)
                return mapped
                
        return target_path
