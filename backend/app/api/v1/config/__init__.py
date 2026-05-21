from fastapi import APIRouter

from app.api.v1.config.config import router as read_router
from app.api.v1.config.directories import router as directories_router
from app.api.v1.config.downloaders import router as downloaders_router
from app.api.v1.config.indexers import router as indexers_router
from app.api.v1.config.mediaservers import router as mediaservers_router
from app.api.v1.config.preview import router as preview_router
from app.api.v1.config.read_auth import router as read_auth_router
from app.api.v1.config.read_services import router as read_services_router
from app.api.v1.config.read_system import router as read_system_router
from app.api.v1.config.read_tabs import router as read_tabs_router
from app.api.v1.config.templates import router as templates_router
from app.api.v1.config.filters import router as filters_router
from app.api.v1.config.quality_profiles import router as quality_profiles_router
from app.api.v1.config.tags import router as tags_router
from app.api.v1.config.addons.addons import router as addons_router
from app.api.v1.config.test_connection import router as test_connection_router
from app.api.v1.config.test_directory import router as test_directory_router
from app.api.v1.config.tokens import router as tokens_router
from app.api.v1.config.update_auth import router as update_auth_router
from app.api.v1.config.update_services import router as update_services_router
from app.api.v1.config.update_system import router as update_system_router

router = APIRouter()

router.include_router(test_directory_router)
router.include_router(test_connection_router)
router.include_router(read_router)
router.include_router(read_auth_router)
router.include_router(read_services_router)
router.include_router(read_system_router)
router.include_router(read_tabs_router)
router.include_router(update_auth_router)
router.include_router(update_services_router)
router.include_router(update_system_router)
router.include_router(preview_router)
router.include_router(tokens_router)
router.include_router(downloaders_router)
router.include_router(indexers_router)
router.include_router(mediaservers_router)
router.include_router(directories_router)
router.include_router(templates_router)
router.include_router(filters_router, tags=["Config: Filters"])
router.include_router(quality_profiles_router, tags=["Config: Quality Profiles"])
router.include_router(tags_router, tags=["Config: Tags"])
router.include_router(addons_router, prefix="/config/addons", tags=["Config: Addons"])
