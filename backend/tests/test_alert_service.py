from datetime import datetime

from app.schemas.domain.alert import (
    AlertCategory,
    AlertRaiseRequest,
    AlertRecord,
    AlertSeverity,
    AlertStatus,
)
from app.services.domain.alerts.service import AlertService


class _FakeAlertRepository:
    def __init__(self, existing: AlertRecord | None = None) -> None:
        self.alert = existing

    def find_by_fingerprint(self, fingerprint: str) -> AlertRecord | None:
        if self.alert and self.alert.fingerprint == fingerprint:
            return self.alert
        return None

    def upsert(self, alert: AlertRecord) -> AlertRecord:
        self.alert = alert
        return alert


def _request() -> AlertRaiseRequest:
    return AlertRaiseRequest(
        fingerprint="task.transfer:task-1",
        severity=AlertSeverity.error,
        category=AlertCategory.task_transfer,
        message_key="alertMessages.taskTransferFailed",
        message_params={"task": "Task", "reason_key": "backendErrors.transferFailed"},
    )


def test_repeated_active_alert_clears_acknowledgement():
    service = AlertService()
    service.repo = _FakeAlertRepository(
        AlertRecord(
            fingerprint="task.transfer:task-1",
            status=AlertStatus.active,
            severity=AlertSeverity.error,
            category=AlertCategory.task_transfer,
            message_key="alertMessages.taskTransferFailed",
            message_params={"task": "Task"},
            acknowledged_at=datetime.now(),
            occurrence_count=1,
        )
    )

    alert = service.raise_alert(_request())

    assert alert.status == AlertStatus.active
    assert alert.acknowledged_at is None
    assert alert.occurrence_count == 2
