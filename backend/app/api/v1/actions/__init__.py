from fastapi import APIRouter

from app.api.v1.actions.list import router as list_router

router = APIRouter(prefix="/actions")
router.include_router(list_router)
