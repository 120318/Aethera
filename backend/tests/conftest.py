from __future__ import annotations

import os
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config


_TEST_DB_PATH = Path(f"/tmp/aethera-pytest-{uuid.uuid4()}.db").resolve()
_REAL_DB_PATH = Path("/config/db/aethera.db").resolve()


def _set_test_database_env() -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
    os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")


def _assert_not_real_database(url: str) -> None:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return
    db_path = Path(url[len(prefix):]).resolve()
    if db_path == _REAL_DB_PATH:
        raise RuntimeError(
            "pytest is attempting to use the real database /config/db/aethera.db; "
            "tests must run against an isolated test database."
        )


_set_test_database_env()
_assert_not_real_database(os.environ["DATABASE_URL"])


def pytest_sessionstart(session) -> None:
    _set_test_database_env()
    _assert_not_real_database(os.environ["DATABASE_URL"])

    backend_root = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(backend_root / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


def pytest_runtest_teardown(item, nextitem) -> None:
    from app.db.sql.session import engine

    engine.dispose()
