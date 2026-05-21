from app.api.v1.library.list import router as list_router
from app.api.v1.library.overview import router as overview_router
from app.api.v1.library.manage import router as manage_router
from app.api.v1.library.file_delete import router as file_delete_router
from app.api.v1.library.file_detail import router as file_detail_router
from app.api.v1.library.file_directory_change import router as file_directory_change_router
from app.api.v1.library.file_directory_change_submit import router as file_directory_change_submit_router
from app.api.v1.library.media_server_link import router as media_server_link_router
from fastapi import APIRouter

router = APIRouter(prefix="/library")

router.include_router(list_router)
router.include_router(overview_router)
router.include_router(manage_router)
router.include_router(file_delete_router)
router.include_router(file_detail_router)
router.include_router(file_directory_change_router)
router.include_router(file_directory_change_submit_router)
router.include_router(media_server_link_router)
