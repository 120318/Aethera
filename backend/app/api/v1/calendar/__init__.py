from fastapi import APIRouter

from app.api.v1.calendar.airings import router as airings_router

router = APIRouter(prefix="/calendar")
router.include_router(airings_router)
