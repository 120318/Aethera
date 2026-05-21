from __future__ import annotations

from pathlib import Path

from app.core.storage_paths import get_log_dir
from app.services.config.settings_service import settings_service


class ActionLogService:
    def list_action_logs(self, action_id: str, limit: int = 200) -> list[str]:
        if not action_id:
            return []
        needle = f"action_id={action_id}"
        lines: list[str] = []
        for path in self._log_paths():
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        if needle in line:
                            lines.append(line.rstrip("\n"))
            except OSError:
                continue
        if limit <= 0:
            return lines
        return lines[-limit:]

    def _log_paths(self) -> list[Path]:
        logging_cfg = settings_service.get_logging_config().logging
        base = Path(logging_cfg.dir or get_log_dir()) / (logging_cfg.file or "backend.log")
        paths = [base]
        for idx in range(1, 4):
            paths.append(Path(f"{base}.{idx}"))
        return paths


action_log_service = ActionLogService()
