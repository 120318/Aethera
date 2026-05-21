from fastapi import APIRouter

from app.api.v1.scheduler.history import router as history_router
from app.api.v1.scheduler.jobs import router as jobs_router
from app.api.v1.scheduler.trigger import router as trigger_router

router = APIRouter()
router.include_router(history_router)
router.include_router(jobs_router)
router.include_router(trigger_router)
