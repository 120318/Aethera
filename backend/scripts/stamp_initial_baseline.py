from __future__ import annotations

import argparse

from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.db.sql import models  # noqa: F401
from app.db.sql.base import Base
from app.db.sql.config import get_database_url
from app.db.sql.models import ConfigSectionORM


BASELINE_REVISION = "0001_initial_schema"
KNOWN_PRELAUNCH_DRIFT = {
    "missing table: config_sections",
    "extra column: commands.lock_key",
}


def _schema_differences(engine) -> list[str]:
    inspector = inspect(engine)
    db_tables = {name for name in inspector.get_table_names() if not name.startswith("sqlite_")}
    expected_tables = set(Base.metadata.tables)
    comparable_db_tables = db_tables - {"alembic_version"}
    differences: list[str] = []

    for table_name in sorted(expected_tables - comparable_db_tables):
        differences.append(f"missing table: {table_name}")
    for table_name in sorted(comparable_db_tables - expected_tables):
        differences.append(f"extra table: {table_name}")

    for table_name in sorted(expected_tables & comparable_db_tables):
        db_columns = {column["name"] for column in inspector.get_columns(table_name)}
        expected_columns = set(Base.metadata.tables[table_name].columns.keys())
        for column_name in sorted(expected_columns - db_columns):
            differences.append(f"missing column: {table_name}.{column_name}")
        for column_name in sorted(db_columns - expected_columns):
            differences.append(f"extra column: {table_name}.{column_name}")

    return differences


def _repair_known_prelaunch_drift(engine) -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        if not inspector.has_table("config_sections"):
            ConfigSectionORM.__table__.create(connection, checkfirst=True)

        inspector = inspect(connection)
        if inspector.has_table("commands"):
            command_columns = {column["name"] for column in inspector.get_columns("commands")}
            if "lock_key" in command_columns:
                command_indexes = {index["name"] for index in inspector.get_indexes("commands")}
                if "ix_commands_lock_key" in command_indexes:
                    connection.execute(text("DROP INDEX ix_commands_lock_key"))
                connection.execute(text("ALTER TABLE commands DROP COLUMN lock_key"))


def _stamp_revision(engine, revision: str) -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("DELETE FROM alembic_version"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES (:revision)"), {"revision": revision})


def main() -> int:
    parser = argparse.ArgumentParser(description="Stamp an existing equivalent database to the initial baseline revision.")
    parser.add_argument("--force", action="store_true", help="Stamp even when schema differences are detected.")
    parser.add_argument(
        "--repair-known-prelaunch-drift",
        action="store_true",
        help="Repair known pre-launch schema drift before stamping. This only creates config_sections and drops commands.lock_key.",
    )
    args = parser.parse_args()

    database_url = get_database_url()
    engine = create_engine(database_url, future=True)
    try:
        with engine.connect() as connection:
            current_revision = MigrationContext.configure(connection).get_current_revision()
        if current_revision == BASELINE_REVISION:
            print(f"Database is already stamped at {BASELINE_REVISION}.")
            return 0

        differences = _schema_differences(engine)
        if differences and args.repair_known_prelaunch_drift:
            unknown_differences = set(differences) - KNOWN_PRELAUNCH_DRIFT
            if unknown_differences:
                print("Refusing automatic repair because unknown schema differences were detected:")
                for item in sorted(unknown_differences):
                    print(f"- {item}")
                return 2
            _repair_known_prelaunch_drift(engine)
            differences = _schema_differences(engine)

        if differences and not args.force:
            print("Refusing to stamp because the database schema is not equivalent to the current models:")
            for item in differences[:50]:
                print(f"- {item}")
            remaining = len(differences) - 50
            if remaining > 0:
                print(f"- ... {remaining} more")
            print("Back up config/ first, resolve the schema drift, or re-run with --force if you understand the risk.")
            return 2
    finally:
        engine.dispose()

    _stamp_revision(engine, BASELINE_REVISION)
    print(f"Stamped database from {current_revision or '<none>'} to {BASELINE_REVISION}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
