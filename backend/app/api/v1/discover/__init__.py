from fastapi import APIRouter

from app.api.v1.discover.lists import router as lists_router

router = APIRouter(prefix="/discover")
router.include_router(lists_router)
