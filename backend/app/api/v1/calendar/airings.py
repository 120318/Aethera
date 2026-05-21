from fastapi import APIRouter, Query

from app.schemas.runtime.calendar import CalendarAiringsResponse, CalendarScope
from app.services.application.views.calendar.service import build_calendar_airings

router = APIRouter()


@router.get("/airings", response_model=CalendarAiringsResponse)
async def list_airings(
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    scope: CalendarScope = Query("all"),
) -> CalendarAiringsResponse:
    return await build_calendar_airings(from_date, to_date, scope)
