from __future__ import annotations

import os
from pathlib import Path

import yaml

from app.core.storage_paths import get_config_file_path
from app.schemas.config import AppConfig


class ConfigFileRepository:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or get_config_file_path()

    def load_payload(self) -> dict | None:
        if not self.file_path.exists():
            return None
        with self.file_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload if isinstance(payload, dict) else {}

    def load(self) -> AppConfig | None:
        payload = self.load_payload()
        if payload is None:
            return None
        if isinstance(payload, dict) and "addons" not in payload and "extensions" in payload:
            payload["addons"] = payload["extensions"]
            payload.pop("extensions", None)
        system_cfg = payload.setdefault("system", {})
        logging_cfg = payload.setdefault("logging", {})
        if isinstance(system_cfg, dict):
            system_cfg.pop("debug_enabled", None)
        payload.pop("debug_enabled", None)
        if isinstance(logging_cfg, dict):
            logging_cfg.pop("debug_enabled", None)
            if "level" not in logging_cfg or not logging_cfg["level"]:
                backend_mode = (os.getenv("BACKEND_MODE", "dev") or "dev").lower()
                logging_cfg["level"] = "DEBUG" if backend_mode != "prod" else "INFO"
        return AppConfig.model_validate(payload)
