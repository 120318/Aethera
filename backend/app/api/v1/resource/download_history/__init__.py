from app.api.v1.resource.download_history.media import router as media_router
from app.api.v1.resource.download_history.sync import router as sync_router
from fastapi import APIRouter

router = APIRouter(prefix="/download-history")

router.include_router(media_router)
router.include_router(sync_router)
