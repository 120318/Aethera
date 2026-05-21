from fastapi import APIRouter

from app.api.v1.logs.backend import router as backend_router

router = APIRouter(prefix="/logs")
router.include_router(backend_router)
