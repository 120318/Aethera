from fastapi import APIRouter

from app.api.v1.events.list import router as list_router

router = APIRouter(prefix="/events")
router.include_router(list_router)

