from __future__ import annotations

import os
from pathlib import Path


DEFAULT_CONFIG_ROOT = Path("/config")
DEFAULT_MEDIA_ROOT = Path("/data")
DEFAULT_DB_FILENAME = "aethera.db"
DEFAULT_CONFIG_FILENAME = "config.yaml"


def get_config_root() -> Path:
    configured = os.getenv("AETHERA_CONFIG_ROOT") or os.getenv("CONFIG_ROOT")
    if configured:
        return Path(configured)
    return DEFAULT_CONFIG_ROOT


def get_config_file_path() -> Path:
    return get_config_root() / DEFAULT_CONFIG_FILENAME


def get_database_path() -> Path:
    return get_config_root() / "db" / DEFAULT_DB_FILENAME


def get_cache_dir() -> Path:
    return get_config_root() / "cache"


def get_torrent_cache_dir() -> Path:
    return get_cache_dir() / "torrent_cache"


def get_torrent_store_dir() -> Path:
    return get_config_root() / "torrents"


def get_log_dir() -> Path:
    return get_config_root() / "logs"


def get_media_root() -> Path:
    return DEFAULT_MEDIA_ROOT


def get_library_root() -> Path:
    return get_media_root() / "library"


def get_download_root() -> Path:
    return get_media_root() / "download"
