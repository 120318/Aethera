from fastapi import APIRouter

from app.api.v1.commands.active import router as active_router
from app.api.v1.commands.create import router as create_router
from app.api.v1.commands.detail import router as detail_router
from app.api.v1.commands.list import router as list_router

router = APIRouter(prefix="/commands")

router.include_router(create_router)
router.include_router(active_router)
router.include_router(list_router)
router.include_router(detail_router)
