from fastapi import APIRouter

from app.api.v1.addons.jobs import router as jobs_router
from app.api.v1.addons.list import router as list_router

router = APIRouter(prefix="/addons")

router.include_router(list_router)
router.include_router(jobs_router)

