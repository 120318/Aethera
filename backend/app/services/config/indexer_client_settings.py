from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from app.db.repositories.indexer_site_health_repository import IndexerSiteHealthRepository
from app.db.repositories.settings_sqlite_repository import SettingsSqliteRepository
from app.schemas.config import IndexerConfig, IndexerProviderConfig
from app.schemas.exception import ConfigurationException
from app.schemas.runtime.indexer_runtime import IndexerSiteSearchOutcome
from app.schemas.runtime.indexer_site_health import IndexerSiteHealthStatus
from app.services.domain.alerts.workflow_alerts import (
    raise_indexer_site_alert,
    resolve_indexer_site_alert,
)


class IndexerSiteHealthState:
    def __init__(self, repo: IndexerSiteHealthRepository | None = None) -> None:
        self._repo = repo or IndexerSiteHealthRepository()

    def _get_record(self, indexer_id: str, site_id: str) -> IndexerSiteHealthStatus | None:
        return self._repo.find_one(indexer_id, site_id)

    def _upsert(self, status: IndexerSiteHealthStatus) -> IndexerSiteHealthStatus:
        return self._repo.upsert(status)

    def record_outcomes(self, outcomes: list[IndexerSiteSearchOutcome]) -> None:
        for outcome in outcomes:
            if outcome.success:
                self.record_success(
                    indexer_id=outcome.indexer_id,
                    indexer_name=outcome.indexer_name,
                    site_id=outcome.site.id,
                    site_name=outcome.site.name or outcome.site.id,
                    client_type=outcome.indexer_type,
                )
                continue
            self.record_failure(
                indexer_id=outcome.indexer_id,
                indexer_name=outcome.indexer_name,
                site_id=outcome.site.id,
                site_name=outcome.site.name or outcome.site.id,
                error_message=str(outcome.error or "unknown error"),
                client_type=outcome.indexer_type,
            )

    def record_success(
        self,
        *,
        indexer_id: str,
        indexer_name: str,
        site_id: str,
        site_name: str,
        client_type: str = "jackett",
    ) -> IndexerSiteHealthStatus:
        current = self._get_record(indexer_id, site_id)
        now = datetime.now()
        status = IndexerSiteHealthStatus(
            indexer_id=indexer_id,
            indexer_name=indexer_name,
            site_id=site_id,
            site_name=site_name,
            status="healthy",
            checked_at=now,
            last_success_at=now,
            last_failure_at=current.last_failure_at if current else None,
            consecutive_failures=0,
            last_error_message=None,
            notify_pending=False,
            client_type=client_type,
        )
        resolve_indexer_site_alert(indexer_id, site_id)
        return self._upsert(status)

    def record_failure(
        self,
        *,
        indexer_id: str,
        indexer_name: str,
        site_id: str,
        site_name: str,
        error_message: str,
        client_type: str = "jackett",
    ) -> IndexerSiteHealthStatus:
        current = self._get_record(indexer_id, site_id)
        now = datetime.now()
        previous_failures = current.consecutive_failures if current else 0
        consecutive_failures = previous_failures + 1
        status = IndexerSiteHealthStatus(
            indexer_id=indexer_id,
            indexer_name=indexer_name,
            site_id=site_id,
            site_name=site_name,
            status="unhealthy",
            checked_at=now,
            last_success_at=current.last_success_at if current else None,
            last_failure_at=now,
            consecutive_failures=consecutive_failures,
            last_error_message=error_message,
            notify_pending=consecutive_failures >= 3,
            client_type=client_type,
        )
        if consecutive_failures >= 3:
            raise_indexer_site_alert(
                indexer_id=indexer_id,
                indexer_name=indexer_name,
                site_id=site_id,
                site_name=site_name,
                consecutive_failures=consecutive_failures,
                error=error_message,
            )
        return self._upsert(status)

    def list_by_indexer(self, indexer_id: str) -> list[IndexerSiteHealthStatus]:
        return self._repo.list_by_indexer(indexer_id)

    def get_status_map_by_indexer(self) -> Mapping[str, list[IndexerSiteHealthStatus]]:
        grouped: dict[str, list[IndexerSiteHealthStatus]] = {}
        statuses = self._repo.get_all()
        for status in statuses:
            grouped.setdefault(status.indexer_id, []).append(status)
        for statuses in grouped.values():
            statuses.sort(key=lambda item: (item.site_name or item.site_id).lower())
        return grouped


class IndexerClientSettings:
    def __init__(self, repo: SettingsSqliteRepository) -> None:
        self._repo = repo

    def list(self) -> list[IndexerProviderConfig]:
        return self._repo.indexers.list()

    def list_enabled(self) -> list[IndexerConfig]:
        return [indexer for indexer in self.list() if indexer.enabled]

    def replace_all(self, indexers: list[IndexerProviderConfig]) -> None:
        self._repo.indexers.replace(indexers)

    def create(self, indexer: IndexerProviderConfig) -> IndexerProviderConfig:
        indexers = self.list()
        if any(item.id == indexer.id for item in indexers):
            raise ConfigurationException("backendErrors.config.indexerIdExists", params={"id": indexer.id})
        indexers.append(indexer)
        self.replace_all(indexers)
        return indexer

    def update(self, indexer_id: str, indexer: IndexerProviderConfig) -> IndexerProviderConfig:
        indexers = self.list()
        current_index = next((index for index, item in enumerate(indexers) if item.id == indexer_id), -1)
        if current_index == -1:
            raise ConfigurationException("backendErrors.config.indexerNotFound", params={"id": indexer_id})
        indexer.id = indexer_id
        indexers[current_index] = indexer
        self.replace_all(indexers)
        return indexer

    def delete(self, indexer_id: str) -> None:
        indexers = self.list()
        next_indexers = [item for item in indexers if item.id != indexer_id]
        if len(next_indexers) == len(indexers):
            raise ConfigurationException("backendErrors.config.indexerNotFound", params={"id": indexer_id})
        self.replace_all(next_indexers)
        if self.get_default_id() == indexer_id:
            self.clear_default()

    def reorder(self, indexers: list[IndexerProviderConfig]) -> None:
        self.replace_all(indexers)

    def set_default(self, indexer_id: str) -> None:
        indexer = next((item for item in self.list() if item.id == indexer_id and item.enabled), None)
        if indexer is None:
            raise ConfigurationException("backendErrors.config.indexerNotFoundOrDisabled", params={"id": indexer_id})
        self._repo.set_default("default_indexer_id", indexer_id)

    def clear_default(self) -> None:
        self._repo.set_default("default_indexer_id", None)

    def get_default_id(self) -> str | None:
        return self._repo.get_default("default_indexer_id")
