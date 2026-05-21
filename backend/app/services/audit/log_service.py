from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.core.storage_paths import get_log_dir
from app.services.config.settings_service import settings_service


class LogService:
    def cleanup_retention(self) -> None:
        logging_cfg = settings_service.get_logging_config().logging
        retention_days = int(logging_cfg.server_retention_days or 0)
        if retention_days <= 0:
            return

        base_path = Path(logging_cfg.dir or get_log_dir()) / (logging_cfg.file or "backend.log")
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        for path in self._candidate_paths(base_path):
            if not path.exists() or not path.is_file():
                continue
            if path == base_path:
                continue
            modified_at = datetime.utcfromtimestamp(path.stat().st_mtime)
            if modified_at < cutoff:
                path.unlink(missing_ok=True)

    def _candidate_paths(self, base_path: Path) -> list[Path]:
        log_dir = base_path.parent
        base_name = base_path.name
        return sorted(log_dir.glob(f"{base_name}*"))


log_service = LogService()
