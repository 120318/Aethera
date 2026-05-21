from fastapi import APIRouter
from app.api.v1.subscription import dialog_save, download_config, end_current, run, state  # noqa: F401

router = APIRouter(prefix="/subscription")
router.include_router(state.router)
router.include_router(end_current.router)
router.include_router(download_config.router)
router.include_router(dialog_save.router)
router.include_router(run.router)
