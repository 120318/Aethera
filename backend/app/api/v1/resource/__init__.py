from app.api.v1.resource.delete import router as delete_router
from app.api.v1.resource.delete_post import router as delete_post_router
from app.api.v1.resource.download import router as download_router
from app.api.v1.resource.list import router as list_router
from app.api.v1.resource.pilot_episode import router as pilot_episode_router
from app.api.v1.resource.search import router as search_router
from app.api.v1.resource.search_status import router as search_status_router
from app.api.v1.resource.sites import router as sites_router
from app.api.v1.resource.transfer import router as transfer_router
from fastapi import APIRouter

router = APIRouter(prefix="/resource")

router.include_router(search_status_router)
router.include_router(search_router)
router.include_router(pilot_episode_router)
router.include_router(sites_router)
router.include_router(list_router)
router.include_router(transfer_router)
router.include_router(delete_router)
router.include_router(delete_post_router)
router.include_router(download_router)
