from fastapi import APIRouter

from app.api.v1.media_management.items import router as items_router
from app.api.v1.media_management.summary import router as summary_router

router = APIRouter(prefix="/media-management")

router.include_router(summary_router)
router.include_router(items_router)
