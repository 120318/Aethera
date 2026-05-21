from __future__ import annotations

import inspect
import logging
import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.request_perf_context import get_current_db_source, get_request_perf
from app.db.sql.config import ensure_database_directory, get_database_url

logger = logging.getLogger("app.db.sql_timing")
SLOW_SQL_WARNING_THRESHOLD_MS = 50
_IGNORED_SOURCE_PREFIXES = (
    "app.db.sql.session",
    "app.core.request_perf_context",
)


ensure_database_directory()

engine = create_engine(
    get_database_url(),
    future=True,
    pool_pre_ping=True,
    connect_args={
        "check_same_thread": False,
        "timeout": 5,
    },
)
@event.listens_for(engine, "connect")
def configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
    starts = conn.info.setdefault("query_start_time", [])
    starts.append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
    starts = conn.info.get("query_start_time") or []
    started_at = starts.pop() if starts else None
    if started_at is None:
        return

    duration_ms = max(0.0, (time.perf_counter() - started_at) * 1000)
    source = _resolve_db_source()
    perf_stats = get_request_perf()
    if perf_stats is not None:
        perf_stats.record_db_query(source, duration_ms)

    if duration_ms <= SLOW_SQL_WARNING_THRESHOLD_MS:
        return

    if perf_stats is not None:
        perf_stats.slow_db_queries += 1

    normalized_statement = " ".join((statement or "").split())
    logger.warning(
        "slow_sql_query source=%s duration_ms=%.1f rowcount=%s executemany=%s statement=%s",
        source,
        duration_ms,
        getattr(cursor, "rowcount", -1),
        str(bool(executemany)).lower(),
        normalized_statement[:300],
    )


def _resolve_db_source() -> str:
    explicit_source = get_current_db_source()
    if explicit_source:
        return explicit_source

    frame = inspect.currentframe()
    if frame is None:
        return "unknown"
    frame = frame.f_back
    while frame is not None:
        module_name = str(frame.f_globals.get("__name__", ""))
        if module_name.startswith("app.") and not module_name.startswith(_IGNORED_SOURCE_PREFIXES):
            function_name = str(frame.f_code.co_name or "<unknown>")
            return f"{module_name.removeprefix('app.')}:{function_name}"
        frame = frame.f_back
    return "unknown"
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)
