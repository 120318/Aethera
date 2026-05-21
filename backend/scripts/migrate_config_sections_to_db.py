from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from app.db.repositories.config_file_repository import ConfigFileRepository
from app.db.repositories.settings_sqlite_repository import SettingsSqliteRepository
from app.schemas.config import ServicesConfig, SystemConfig

BOOTSTRAP_ONLY_KEYS = {"config_version"}


def _build_sections(config):
    return {
        "services": ServicesConfig(
            browse_source=config.browse_source,
            douban=config.douban,
            themoviedb=config.themoviedb,
        ).model_dump(mode="json"),
        "system": SystemConfig(
            cache=config.cache,
            scheduler=config.scheduler,
            download=config.download,
            library=config.library,
            logging=config.logging,
            onboarding_enabled=config.onboarding_enabled,
        ).model_dump(mode="json"),
        "addons": config.addons.model_dump(mode="json"),
        "auth": config.auth.model_dump(mode="json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate YAML config sections into the SQLite settings store.")
    parser.add_argument(
        "--remove-yaml",
        action="store_true",
        help="Back up config.yaml and remove it after DB sections are written.",
    )
    args = parser.parse_args()

    file_repo = ConfigFileRepository()
    payload = file_repo.load_payload()
    if payload is None:
        print(f"No YAML config found at {file_repo.file_path}; nothing to migrate.")
        return 0

    has_legacy_settings = any(key not in BOOTSTRAP_ONLY_KEYS for key in payload)
    if has_legacy_settings:
        config = file_repo.load()
        if config is None:
            print(f"No YAML config found at {file_repo.file_path}; nothing to migrate.")
            return 0
        SettingsSqliteRepository().replace_sections(_build_sections(config))
        print("Migrated services, system, addons, and auth sections into SQLite.")
    else:
        print("YAML contains no legacy settings; SQLite settings were left unchanged.")

    if args.remove_yaml:
        backup_path = _next_backup_path(file_repo.file_path)
        shutil.copy2(file_repo.file_path, backup_path)
        file_repo.file_path.unlink()
        print(f"Backed up YAML config to {backup_path} and removed config.yaml.")
    else:
        print("Left YAML config unchanged. Runtime settings are read from SQLite; re-run with --remove-yaml to back up and remove YAML.")

    return 0


def _next_backup_path(path: Path) -> Path:
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}.sections-backup-{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Unable to allocate backup path for {path}")


if __name__ == "__main__":
    raise SystemExit(main())
