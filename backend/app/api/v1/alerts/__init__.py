from fastapi import APIRouter

from app.api.v1.alerts.acknowledge import router as acknowledge_router
from app.api.v1.alerts.center import router as center_router

router = APIRouter(prefix="/alerts")
router.include_router(center_router)
router.include_router(acknowledge_router)
