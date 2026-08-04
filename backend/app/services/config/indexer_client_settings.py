from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timedelta

from app.db.repositories.indexer_site_health_repository import IndexerSiteHealthRepository
from app.db.repositories.settings_sqlite_repository import SettingsSqliteRepository
from app.schemas.config import IndexerConfig, IndexerProviderConfig
from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.event import EventCreate, EventEntityRef, EventLevel, EventSource
from app.schemas.exception import ConfigurationException
from app.schemas.runtime.indexer_runtime import IndexerSiteSearchOutcome
from app.schemas.runtime.indexer_site_health import IndexerSiteHealthStatus
from app.services.audit.event_service import event_service


INDEXER_SITE_FAILURE_NOTIFY_THRESHOLD = 3
INDEXER_SITE_FAILURE_NOTIFY_COOLDOWN = timedelta(hours=24)
logger = logging.getLogger("app.services.config.indexer_client_settings")


class IndexerSiteHealthState:
    def __init__(self, repo: IndexerSiteHealthRepository | None = None) -> None:
        self._repo = repo or IndexerSiteHealthRepository()

    def _get_record(self, indexer_id: str, site_id: str) -> IndexerSiteHealthStatus | None:
        return self._repo.find_one(indexer_id, site_id)

    def _upsert(self, status: IndexerSiteHealthStatus) -> IndexerSiteHealthStatus:
        return self._repo.upsert(status)

    @staticmethod
    def _unhealthy_event_correlation_id(indexer_id: str, site_id: str) -> str:
        return f"indexer:{indexer_id}:site:{site_id}:unhealthy"

    def _emit_unhealthy_event(self, status: IndexerSiteHealthStatus) -> bool:
        try:
            event_service.emit(
                EventCreate(
                    type=EventTypes.INDEXER_SITE_UNHEALTHY,
                    level=EventLevel.warning,
                    source=EventSource.base,
                    message_params={
                        "indexer_id": status.indexer_id,
                        "indexer_name": status.indexer_name,
                        "site_id": status.site_id,
                        "site_name": status.site_name,
                        "client_type": status.client_type,
                        "consecutive_failures": str(status.consecutive_failures),
                        "error": status.last_error_message or "",
                    },
                    entities=[
                        EventEntityRef(type="indexer", id=status.indexer_id),
                        EventEntityRef(type="indexer_site", id=status.site_id),
                    ],
                    correlation_id=self._unhealthy_event_correlation_id(status.indexer_id, status.site_id),
                )
            )
            return True
        except Exception as exc:
            logger.error(
                "Failed to emit indexer site unhealthy event for %s/%s: %s",
                status.indexer_id,
                status.site_id,
                exc,
            )
            return False

    def _acknowledge_unhealthy_event(self, status: IndexerSiteHealthStatus) -> bool:
        try:
            applied, acknowledged_count = self._repo.acknowledge_recovered_unhealthy_events(
                status,
                self._unhealthy_event_correlation_id(status.indexer_id, status.site_id),
            )
            if acknowledged_count:
                logger.info(
                    "Acknowledged recovered indexer site unhealthy events: indexer=%s site=%s count=%s",
                    status.indexer_id,
                    status.site_id,
                    acknowledged_count,
                )
            return applied
        except Exception as exc:
            logger.error(
                "Failed to acknowledge recovered indexer site unhealthy events for %s/%s: %s",
                status.indexer_id,
                status.site_id,
                exc,
            )
            return False

    def _reopen_unhealthy_event(self, status: IndexerSiteHealthStatus) -> None:
        try:
            applied, reopened_count = self._repo.reopen_unhealthy_events(
                status,
                self._unhealthy_event_correlation_id(status.indexer_id, status.site_id),
            )
            if applied and reopened_count:
                logger.info(
                    "Reopened recurring indexer site unhealthy events: indexer=%s site=%s count=%s",
                    status.indexer_id,
                    status.site_id,
                    reopened_count,
                )
        except Exception as exc:
            logger.error(
                "Failed to reopen recurring indexer site unhealthy events for %s/%s: %s",
                status.indexer_id,
                status.site_id,
                exc,
            )

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
        should_acknowledge_unhealthy_event = bool(
            current and (current.status == "unhealthy" or current.notify_pending)
        )
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
            notify_pending=should_acknowledge_unhealthy_event,
            last_notified_at=current.last_notified_at if current else None,
            client_type=client_type,
        )
        saved = self._upsert(status)
        if should_acknowledge_unhealthy_event:
            self._acknowledge_unhealthy_event(saved)
            return self._get_record(indexer_id, site_id) or saved
        return saved

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
        should_emit = (
            consecutive_failures >= INDEXER_SITE_FAILURE_NOTIFY_THRESHOLD
            and self._notify_cooldown_elapsed(current.last_notified_at if current else None, now)
        )
        should_reopen = bool(
            consecutive_failures >= INDEXER_SITE_FAILURE_NOTIFY_THRESHOLD
            and not should_emit
            and current
            and current.last_success_at
            and current.last_notified_at
            and current.last_success_at > current.last_notified_at
        )
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
            notify_pending=consecutive_failures >= INDEXER_SITE_FAILURE_NOTIFY_THRESHOLD,
            last_notified_at=current.last_notified_at if current else None,
            client_type=client_type,
        )
        saved = self._upsert(status)
        if should_emit and self._emit_unhealthy_event(saved):
            saved.last_notified_at = now
            saved = self._upsert(saved)
        elif should_reopen:
            self._reopen_unhealthy_event(saved)
        return saved

    @staticmethod
    def _notify_cooldown_elapsed(last_notified_at: datetime | None, now: datetime) -> bool:
        return last_notified_at is None or (now - last_notified_at) >= INDEXER_SITE_FAILURE_NOTIFY_COOLDOWN

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
