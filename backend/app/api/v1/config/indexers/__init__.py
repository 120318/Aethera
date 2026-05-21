from app.api.v1.config.indexers.add import router as add_router
from app.api.v1.config.indexers.delete import router as delete_router
from app.api.v1.config.indexers.health import router as health_router
from app.api.v1.config.indexers.sites import router as sites_router
from app.api.v1.config.indexers.list import router as list_router
from app.api.v1.config.indexers.update import router as update_router
from fastapi import APIRouter

router = APIRouter()

router.include_router(list_router)
router.include_router(health_router)
router.include_router(sites_router)
router.include_router(add_router)
router.include_router(update_router)
router.include_router(delete_router)
