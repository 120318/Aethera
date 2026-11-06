from fastapi import APIRouter

from app.api.v1.addons.subtitles.install import router as install_router
from app.api.v1.addons.subtitles.preview import router as preview_router
from app.api.v1.addons.subtitles.search import router as search_router

router = APIRouter(prefix="/subtitles")
router.include_router(search_router)
router.include_router(preview_router)
router.include_router(install_router)
