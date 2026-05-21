from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from app.db.sql.config import get_database_url

logger = logging.getLogger("app.migration")


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    alembic_ini = backend_root / "alembic.ini"
    if not alembic_ini.exists():
        raise RuntimeError(f"Alembic config not found: {alembic_ini}")
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", get_database_url())
    return cfg


def assert_database_schema_is_current() -> None:
    alembic_cfg = _alembic_config()
    script = ScriptDirectory.from_config(alembic_cfg)
    head_revision = script.get_current_head()

    engine = create_engine(get_database_url(), future=True)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_revision = context.get_current_revision()
    engine.dispose()

    if current_revision != head_revision:
        if current_revision:
            try:
                script.get_revision(current_revision)
            except Exception as exc:
                raise RuntimeError(
                    f"Database schema uses pre-baseline revision {current_revision}. "
                    "Back up config/ and run `./aethera.sh db-baseline-stamp` if this database already matches "
                    f"the {head_revision} schema."
                ) from exc
        logger.error(
            "Database schema is not current: current_revision=%s head_revision=%s",
            current_revision,
            head_revision,
        )
        raise RuntimeError(
            f"Database schema is not current: current_revision={current_revision}, head_revision={head_revision}. "
            "Run `alembic upgrade head` before starting the application."
        )
