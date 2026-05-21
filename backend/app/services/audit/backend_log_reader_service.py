from __future__ import annotations

import base64
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from app.core.storage_paths import get_log_dir
from app.services.config.settings_service import settings_service


@dataclass(frozen=True)
class BackendLogCursor:
    device: int | None
    inode: int | None
    offset: int


@dataclass(frozen=True)
class BackendLogReadResult:
    lines: list[str]
    cursor: str | None
    reset: bool
    source_file: str


class BackendLogReaderService:
    def read_backend_logs(self, *, limit: int = 200, cursor: str | None = None) -> BackendLogReadResult:
        base_path = self._get_base_path()

        if cursor:
            cursor_info = self._decode_cursor(cursor)
            if cursor_info is not None:
                return self._read_incremental(base_path=base_path, cursor=cursor_info, limit=limit)

        return self._read_snapshot(base_path=base_path, limit=limit, reset=bool(cursor))

    def _read_snapshot(self, *, base_path: Path, limit: int, reset: bool) -> BackendLogReadResult:
        lines: deque[str] = deque(maxlen=limit)
        for path in self._iter_snapshot_paths(base_path):
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as handle:
                    for raw_line in handle:
                        lines.append(raw_line.rstrip("\n"))
            except OSError:
                continue

        cursor = self._build_cursor(base_path)
        return BackendLogReadResult(
            lines=list(lines),
            cursor=cursor,
            reset=reset,
            source_file=str(base_path),
        )

    def _read_incremental(self, *, base_path: Path, cursor: BackendLogCursor, limit: int) -> BackendLogReadResult:
        try:
            stat = base_path.stat()
        except OSError:
            return self._read_snapshot(base_path=base_path, limit=limit, reset=True)

        if self._is_cursor_stale(stat=stat, cursor=cursor):
            return self._read_snapshot(base_path=base_path, limit=limit, reset=True)

        lines: list[str] = []
        try:
            with base_path.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(cursor.offset)
                while True:
                    raw_line = handle.readline()
                    if raw_line == "":
                        break
                    lines.append(raw_line.rstrip("\n"))
                    if len(lines) >= limit:
                        break
                next_offset = handle.tell()
        except OSError:
            return self._read_snapshot(base_path=base_path, limit=limit, reset=True)

        return BackendLogReadResult(
            lines=lines,
            cursor=self._encode_cursor(
                BackendLogCursor(
                    device=stat.st_dev,
                    inode=stat.st_ino,
                    offset=next_offset,
                )
            ),
            reset=False,
            source_file=str(base_path),
        )

    def _is_cursor_stale(self, *, stat, cursor: BackendLogCursor) -> bool:
        if stat.st_size < cursor.offset:
            return True
        if stat.st_dev != cursor.device:
            return True
        if stat.st_ino != cursor.inode:
            return True
        return False

    def _get_base_path(self) -> Path:
        logging_cfg = settings_service.get_logging_config().logging
        return Path(logging_cfg.dir or get_log_dir()) / (logging_cfg.file or "backend.log")

    def _iter_snapshot_paths(self, base_path: Path) -> list[Path]:
        paths = [base_path.with_name(f"{base_path.name}.{index}") for index in range(3, 0, -1)]
        paths.append(base_path)
        return [path for path in paths if path.exists() and path.is_file()]

    def _build_cursor(self, base_path: Path) -> str | None:
        try:
            stat = base_path.stat()
        except OSError:
            return None
        return self._encode_cursor(
            BackendLogCursor(
                device=stat.st_dev,
                inode=stat.st_ino,
                offset=stat.st_size,
            )
        )

    def _encode_cursor(self, cursor: BackendLogCursor) -> str:
        payload = {
            "device": cursor.device,
            "inode": cursor.inode,
            "offset": cursor.offset,
        }
        raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    def _decode_cursor(self, raw_cursor: str) -> BackendLogCursor | None:
        try:
            payload = json.loads(base64.urlsafe_b64decode(raw_cursor.encode("ascii")).decode("utf-8"))
        except (ValueError, TypeError, json.JSONDecodeError):
            return None

        if type(payload) is not dict:
            return None
        if "offset" not in payload or "device" not in payload or "inode" not in payload:
            return None

        offset = payload["offset"]
        if type(offset) is not int or offset < 0:
            return None

        device = payload["device"]
        inode = payload["inode"]
        if device is not None and type(device) is not int:
            return None
        if inode is not None and type(inode) is not int:
            return None

        return BackendLogCursor(device=device, inode=inode, offset=offset)


backend_log_reader_service = BackendLogReaderService()
