import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

import yaml

from app.core.action_context import get_current_action_id
from app.core.storage_paths import get_config_file_path, get_log_dir

DEFAULT_LOG_LEVEL = "INFO"
TRACE_LEVEL_NUM = 5
DEFAULT_LOG_FILE = "backend.log"
DEFAULT_DEV_LOG_LEVEL = "DEBUG"
DEFAULT_PROD_LOG_LEVEL = "INFO"
DEFAULT_NOISY_LOGGERS = (
    "httpcore,httpx,urllib3,asyncio,uvicorn.access,uvicorn.error,aiosmtpd,sqlalchemy.engine,apscheduler,"
    "qbittorrentapi,qbittorrentapi.request,qbittorrentapi.auth,watchfiles.main,watchfiles.watcher"
)
_CURRENT_LOG_LEVEL = DEFAULT_LOG_LEVEL


def _default_log_level() -> str:
    backend_mode = (os.getenv("BACKEND_MODE", "dev") or "dev").lower()
    return DEFAULT_PROD_LOG_LEVEL if backend_mode == "prod" else DEFAULT_DEV_LOG_LEVEL


def _install_trace_level() -> None:
    if getattr(logging, "TRACE", None) != TRACE_LEVEL_NUM:
        logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")
        logging.TRACE = TRACE_LEVEL_NUM

    if not hasattr(logging.Logger, "trace"):
        def trace(self: logging.Logger, message, *args, **kwargs) -> None:
            if self.isEnabledFor(TRACE_LEVEL_NUM):
                self._log(TRACE_LEVEL_NUM, message, args, **kwargs)
        logging.Logger.trace = trace


def _resolve_log_level(level_text: str) -> int:
    normalized = str(level_text or "").strip().upper() or DEFAULT_LOG_LEVEL
    if normalized == "TRACE":
        return TRACE_LEVEL_NUM
    return getattr(logging, normalized, logging.INFO)


def _read_logging_settings() -> tuple[str, str, str]:
    config_path = get_config_file_path()
    if not config_path.exists():
        return _default_log_level(), DEFAULT_LOG_FILE, str(get_log_dir())

    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    logging_cfg = payload["logging"] if isinstance(payload, dict) and "logging" in payload and isinstance(payload["logging"], dict) else {}
    file_name = str(logging_cfg["file"]) if "file" in logging_cfg and logging_cfg["file"] else DEFAULT_LOG_FILE
    log_dir = str(logging_cfg["dir"]) if "dir" in logging_cfg and logging_cfg["dir"] else str(get_log_dir())
    log_level = str(logging_cfg["level"]) if "level" in logging_cfg and logging_cfg["level"] else _default_log_level()
    return log_level, file_name, log_dir


# Comma-separated list of noisy loggers to suppress when not debugging.
# Can be overridden via the NOISY_LOGGERS env var.
NOISY_LOGGERS = os.getenv("NOISY_LOGGERS", DEFAULT_NOISY_LOGGERS)

class ActionContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.action_id = get_current_action_id() or "-"
        return True


class SafeRotatingFileHandler(RotatingFileHandler):
    def _remove_if_exists(self, path: str) -> None:
        try:
            if os.path.exists(path):
                os.remove(path)
        except FileNotFoundError:
            return

    def _rotate_if_exists(self, source: str, target: str) -> None:
        try:
            if os.path.exists(source):
                self.rotate(source, target)
        except FileNotFoundError:
            return

    def doRollover(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                source = self.rotation_filename(f"{self.baseFilename}.{i}")
                target = self.rotation_filename(f"{self.baseFilename}.{i + 1}")
                self._remove_if_exists(target)
                self._rotate_if_exists(source, target)
            target = self.rotation_filename(f"{self.baseFilename}.1")
            self._remove_if_exists(target)
            self._rotate_if_exists(self.baseFilename, target)
        if not self.delay:
            self.stream = self._open()


def _configure_root_logger(log_level: str, log_file: str, log_dir_text: str) -> None:
    log_dir = Path(log_dir_text)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_file

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | action_id=%(action_id)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    action_filter = ActionContextFilter()

    root = logging.getLogger()
    resolved_level = _resolve_log_level(log_level)
    root.setLevel(resolved_level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except OSError:
            continue

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(resolved_level)
    ch.setFormatter(formatter)
    ch.addFilter(action_filter)
    root.addHandler(ch)

    # Rotating file handler
    fh = SafeRotatingFileHandler(str(log_path), maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setLevel(resolved_level)
    fh.setFormatter(formatter)
    fh.addFilter(action_filter)
    root.addHandler(fh)

    # Use configurable noisy logger list. NOISY_LOGGERS is a comma-separated
    # environment variable containing logger names to quiet (set to WARNING).
    noisy = [n.strip() for n in NOISY_LOGGERS.split(",") if n.strip()]
    for lname in noisy:
        try:
            logging.getLogger(lname).setLevel(logging.WARNING)
        except (TypeError, ValueError):
            # Safe to ignore any unexpected names
            continue


def apply_runtime_logging(*, log_level: str, log_file: str, log_dir_text: str) -> None:
    global _CURRENT_LOG_LEVEL
    effective_level = str(log_level or DEFAULT_LOG_LEVEL).upper()
    _configure_root_logger(effective_level, log_file, log_dir_text)
    _CURRENT_LOG_LEVEL = effective_level


def setup_logging() -> None:
    _install_trace_level()
    log_level, log_file, log_dir_text = _read_logging_settings()
    apply_runtime_logging(log_level=log_level, log_file=log_file, log_dir_text=log_dir_text)


def apply_logging_config_from_settings(system_config) -> None:
    _install_trace_level()
    log_dir_text = str(system_config.logging.dir or get_log_dir())
    log_file = str(system_config.logging.file or DEFAULT_LOG_FILE)
    apply_runtime_logging(log_level=system_config.logging.level, log_file=log_file, log_dir_text=log_dir_text)


def is_trace_enabled(logger_name: str | None = None) -> bool:
    logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    return logger.isEnabledFor(TRACE_LEVEL_NUM)


def get_logger(name: str) -> logging.Logger:
    """Internal helper."""
    return logging.getLogger(name)
