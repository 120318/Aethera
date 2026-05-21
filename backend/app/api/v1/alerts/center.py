from fastapi import APIRouter

from app.schemas.domain.alert import AlertCenterResponse
from app.services.domain.alerts import alert_service

router = APIRouter()


@router.get("/center", response_model=AlertCenterResponse)
async def get_alert_center() -> AlertCenterResponse:
    return alert_service.get_center()
