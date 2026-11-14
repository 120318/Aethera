from fastapi import APIRouter

from app.api.v1.task.list import router as list_router
from app.api.v1.task.detail import router as detail_router
from app.api.v1.task.torrent_progress import router as torrent_progress_router
from app.api.v1.task.control import router as control_router
from app.api.v1.task.delete import router as delete_router
from app.api.v1.task.downloader_change import router as downloader_change_router
from app.api.v1.task.downloader_change_submit import router as downloader_change_submit_router
from app.api.v1.task.sync_finished import router as sync_finished_router
from app.api.v1.task.episode_selection import router as episode_selection_router
from app.api.v1.task.episode_selection_update import router as episode_selection_update_router

router = APIRouter(prefix="/task")

router.include_router(list_router)
router.include_router(detail_router)
router.include_router(torrent_progress_router)
router.include_router(control_router)
router.include_router(delete_router)
router.include_router(downloader_change_router)
router.include_router(downloader_change_submit_router)
router.include_router(sync_finished_router)
router.include_router(episode_selection_router)
router.include_router(episode_selection_update_router)
