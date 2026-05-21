from __future__ import annotations

import os
from pathlib import Path

from app.core.storage_paths import get_database_path as get_storage_database_path


def get_database_path() -> Path:
    return get_storage_database_path()


def get_database_url() -> str:
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    db_path = get_database_path().expanduser().resolve()
    return f"sqlite:///{db_path}"


def ensure_database_directory() -> Path:
    db_path = get_database_path().expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path
