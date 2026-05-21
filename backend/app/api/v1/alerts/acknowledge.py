from fastapi import APIRouter

from app.schemas.domain.alert import AlertRecord
from app.schemas.exception.exceptions import ResourceNotFoundException
from app.services.domain.alerts import alert_service

router = APIRouter()


@router.post("/{alert_id}/acknowledge", response_model=AlertRecord)
async def acknowledge_alert(alert_id: str) -> AlertRecord:
    alert = alert_service.acknowledge_alert(alert_id)
    if not alert:
        raise ResourceNotFoundException("backendErrors.alertNotFound")
    return alert
