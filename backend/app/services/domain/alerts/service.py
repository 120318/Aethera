from __future__ import annotations

from datetime import datetime

from app.db.repositories.alert_repository import AlertRepository
from app.schemas.domain.action import ActionStatus
from app.schemas.domain.alert import (
    AlertBellState,
    AlertCenterResponse,
    AlertRaiseRequest,
    AlertRecord,
    AlertResolveRequest,
    AlertSeverity,
    AlertStatus,
    AlertSummary,
)
from app.services.audit.action_service import action_service


class AlertService:
    def __init__(self) -> None:
        self.repo = AlertRepository()

    def raise_alert(self, request: AlertRaiseRequest) -> AlertRecord:
        now = datetime.now()
        existing = self.repo.find_by_fingerprint(request.fingerprint)
        if existing:
            update = {
                "status": AlertStatus.active,
                "severity": request.severity,
                "category": request.category,
                "message_key": request.message_key,
                "message_params": request.message_params,
                "target_type": request.target_type,
                "target_id": request.target_id,
                "media": request.media,
                "media_id": request.media_id,
                "task_id": request.task_id,
                "action_id": request.action_id,
                "occurrence_count": existing.occurrence_count + 1,
                "last_seen_at": now,
                "resolved_at": None,
                "updated_at": now,
            }
            update["acknowledged_at"] = None
            return self.repo.upsert(existing.model_copy(update=update))

        return self.repo.upsert(
            AlertRecord(
                fingerprint=request.fingerprint,
                severity=request.severity,
                category=request.category,
                message_key=request.message_key,
                message_params=request.message_params,
                target_type=request.target_type,
                target_id=request.target_id,
                media=request.media,
                media_id=request.media_id,
                task_id=request.task_id,
                action_id=request.action_id,
                first_seen_at=now,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
            )
        )

    def resolve_alert(self, request: AlertResolveRequest) -> AlertRecord | None:
        return self.repo.resolve(request.fingerprint, datetime.now())

    def acknowledge_alert(self, alert_id: str) -> AlertRecord | None:
        return self.repo.acknowledge(alert_id, datetime.now())

    def get_center(self) -> AlertCenterResponse:
        active_action_count, active_actions = action_service.list_actions(
            limit=50,
            statuses=[ActionStatus.queued, ActionStatus.running],
        )
        visible_alerts = self.repo.list_active(include_acknowledged=False)
        all_active_alerts = self.repo.list_active_all()
        unacknowledged_error_count = sum(
            1 for alert in visible_alerts if alert.severity == AlertSeverity.error
        )
        unacknowledged_warning_count = sum(
            1 for alert in visible_alerts if alert.severity == AlertSeverity.warning
        )
        if unacknowledged_error_count > 0:
            bell_state = AlertBellState.error
        elif active_actions:
            bell_state = AlertBellState.running
        else:
            bell_state = AlertBellState.idle
        return AlertCenterResponse(
            summary=AlertSummary(
                active_count=len(all_active_alerts),
                active_action_count=active_action_count,
                unacknowledged_error_count=unacknowledged_error_count,
                unacknowledged_warning_count=unacknowledged_warning_count,
                bell_state=bell_state,
            ),
            active_actions=active_actions,
            alerts=visible_alerts,
        )


alert_service = AlertService()
