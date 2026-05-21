from fastapi import APIRouter

from app.api.v1.config.directories.add import router as add_router
from app.api.v1.config.directories.delete import router as delete_router
from app.api.v1.config.directories.integrity import router as integrity_router
from app.api.v1.config.directories.list import router as list_router
from app.api.v1.config.directories.migration import router as migration_router
from app.api.v1.config.directories.migration_submit import router as migration_submit_router
from app.api.v1.config.directories.set_default import router as set_default_router
from app.api.v1.config.directories.update import router as update_router
from app.api.v1.config.directories.usage import router as usage_router

router = APIRouter()

router.include_router(list_router)
router.include_router(add_router)
router.include_router(update_router)
router.include_router(delete_router)
router.include_router(set_default_router)
router.include_router(usage_router)
router.include_router(migration_router)
router.include_router(migration_submit_router)
router.include_router(integrity_router)
