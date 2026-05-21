from app.api.v1.config.downloaders.add import router as add_router
from app.api.v1.config.downloaders.delete import router as delete_router
from app.api.v1.config.downloaders.list import router as list_router
from app.api.v1.config.downloaders.set_default import router as set_default_router
from app.api.v1.config.downloaders.update import router as update_router
from app.api.v1.config.downloaders.usage import router as usage_router
from fastapi import APIRouter

router = APIRouter()

router.include_router(list_router)
router.include_router(add_router)
router.include_router(update_router)
router.include_router(delete_router)
router.include_router(set_default_router)
router.include_router(usage_router)
