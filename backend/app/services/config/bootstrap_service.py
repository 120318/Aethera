from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from app.schemas.domain.media_types import MediaType
from app.services.config.settings_service import settings_service


BootstrapStep = Literal["password", "tmdb", "downloader", "indexer", "template", "directory", "complete"]


class BootstrapStatus(BaseModel):
    onboarding_enabled: bool
    password_ready: bool
    tmdb_ready: bool
    downloaders_ready: bool
    indexers_ready: bool
    directories_ready: bool
    templates_ready: bool
    completed: bool
    current_step: BootstrapStep


@dataclass(frozen=True)
class _BootstrapRuntimeState:
    password_ready: bool
    tmdb_ready: bool
    downloaders_ready: bool
    indexers_ready: bool
    directories_ready: bool
    templates_ready: bool
    completed: bool
    current_step: BootstrapStep


class BootstrapService:
    _STATE_KEY_PREFIX = "bootstrap_status"

    def is_onboarding_enabled(self) -> bool:
        return settings_service.is_onboarding_enabled()

    def is_password_ready(self) -> bool:
        return bool(settings_service.get_base_auth_config().password_hash)

    def get_status(self) -> BootstrapStatus:
        password_ready = self.is_password_ready()
        if not self.is_onboarding_enabled():
            return self._build_disabled_status(password_ready)

        runtime_state = self._load_runtime_state()
        if runtime_state is None:
            return self.recompute_status()
        return self._build_status(runtime_state, onboarding_enabled=True)

    def recompute_status(self) -> BootstrapStatus:
        password_ready = self.is_password_ready()
        if not self.is_onboarding_enabled():
            return self._build_disabled_status(password_ready)

        tmdb_ready = bool((settings_service.get_base_services_config().themoviedb.api_key or "").strip())

        downloaders = settings_service.list_downloaders()
        enabled_downloaders = [item for item in downloaders if item.enabled]
        default_downloader_id = settings_service.get_default_downloader_id()
        downloaders_ready = bool(
            enabled_downloaders
            and default_downloader_id
            and any(item.id == default_downloader_id for item in enabled_downloaders)
        )

        indexers_ready = any(item.enabled for item in settings_service.list_indexers())

        naming_templates = settings_service.list_naming_templates()
        enabled_movie_templates = [item for item in naming_templates if item.enabled and item.type == "movie"]
        enabled_tv_templates = [item for item in naming_templates if item.enabled and item.type == "tv"]
        templates_ready = bool(
            enabled_movie_templates
            and enabled_tv_templates
            and any(item.is_default for item in enabled_movie_templates)
            and any(item.is_default for item in enabled_tv_templates)
        )

        directories = settings_service.list_directories()
        enabled_movie_directories = [item for item in directories if item.enabled and item.media_type == MediaType.movie]
        enabled_tv_directories = [item for item in directories if item.enabled and item.media_type == MediaType.tv]
        directories_ready = bool(
            enabled_movie_directories
            and enabled_tv_directories
            and any(item.is_default for item in enabled_movie_directories)
            and any(item.is_default for item in enabled_tv_directories)
        )

        current_step = self._resolve_current_step(
            password_ready=password_ready,
            tmdb_ready=tmdb_ready,
            downloaders_ready=downloaders_ready,
            indexers_ready=indexers_ready,
            templates_ready=templates_ready,
            directories_ready=directories_ready,
        )
        completed = current_step == "complete"
        runtime_state = _BootstrapRuntimeState(
            password_ready=password_ready,
            tmdb_ready=tmdb_ready,
            downloaders_ready=downloaders_ready,
            indexers_ready=indexers_ready,
            directories_ready=directories_ready,
            templates_ready=templates_ready,
            completed=completed,
            current_step=current_step,
        )
        self._persist_runtime_state(runtime_state)
        return self._build_status(runtime_state, onboarding_enabled=True)

    def _build_disabled_status(self, password_ready: bool) -> BootstrapStatus:
        return BootstrapStatus(
            onboarding_enabled=False,
            password_ready=password_ready,
            tmdb_ready=True,
            downloaders_ready=True,
            indexers_ready=True,
            directories_ready=True,
            templates_ready=True,
            completed=True,
            current_step="password" if not password_ready else "complete",
        )

    def _build_status(self, state: _BootstrapRuntimeState, *, onboarding_enabled: bool) -> BootstrapStatus:
        return BootstrapStatus(
            onboarding_enabled=onboarding_enabled,
            password_ready=state.password_ready,
            tmdb_ready=state.tmdb_ready,
            downloaders_ready=state.downloaders_ready,
            indexers_ready=state.indexers_ready,
            directories_ready=state.directories_ready,
            templates_ready=state.templates_ready,
            completed=state.completed,
            current_step=state.current_step,
        )

    def _resolve_current_step(
        self,
        *,
        password_ready: bool,
        tmdb_ready: bool,
        downloaders_ready: bool,
        indexers_ready: bool,
        templates_ready: bool,
        directories_ready: bool,
    ) -> BootstrapStep:
        if not password_ready:
            return "password"
        if not tmdb_ready:
            return "tmdb"
        if not downloaders_ready:
            return "downloader"
        if not indexers_ready:
            return "indexer"
        if not templates_ready:
            return "template"
        if not directories_ready:
            return "directory"
        return "complete"

    def _state_key(self, suffix: str) -> str:
        return f"{self._STATE_KEY_PREFIX}.{suffix}"

    def _load_runtime_state(self) -> _BootstrapRuntimeState | None:
        current_step = settings_service.get_runtime_value(self._state_key("current_step"))
        if current_step not in {"password", "tmdb", "downloader", "indexer", "template", "directory", "complete"}:
            return None
        return _BootstrapRuntimeState(
            password_ready=self._read_bool("password_ready"),
            tmdb_ready=self._read_bool("tmdb_ready"),
            downloaders_ready=self._read_bool("downloaders_ready"),
            indexers_ready=self._read_bool("indexers_ready"),
            directories_ready=self._read_bool("directories_ready"),
            templates_ready=self._read_bool("templates_ready"),
            completed=self._read_bool("completed"),
            current_step=current_step,
        )

    def _persist_runtime_state(self, state: _BootstrapRuntimeState) -> None:
        self._write_bool("password_ready", state.password_ready)
        self._write_bool("tmdb_ready", state.tmdb_ready)
        self._write_bool("downloaders_ready", state.downloaders_ready)
        self._write_bool("indexers_ready", state.indexers_ready)
        self._write_bool("directories_ready", state.directories_ready)
        self._write_bool("templates_ready", state.templates_ready)
        self._write_bool("completed", state.completed)
        settings_service.set_runtime_value(self._state_key("current_step"), state.current_step)

    def _read_bool(self, suffix: str) -> bool:
        return settings_service.get_runtime_value(self._state_key(suffix)) == "1"

    def _write_bool(self, suffix: str, value: bool) -> None:
        settings_service.set_runtime_value(self._state_key(suffix), "1" if value else "0")


bootstrap_service = BootstrapService()
