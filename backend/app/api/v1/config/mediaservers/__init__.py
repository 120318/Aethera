from fastapi import APIRouter

from app.api.v1.config.mediaservers.list import router as list_router
from app.api.v1.config.mediaservers.add import router as add_router
from app.api.v1.config.mediaservers.update import router as update_router
from app.api.v1.config.mediaservers.delete import router as delete_router
from app.api.v1.config.mediaservers.set_default import router as set_default_router

router = APIRouter()

router.include_router(list_router)
router.include_router(add_router)
router.include_router(update_router)
router.include_router(delete_router)
router.include_router(set_default_router)
