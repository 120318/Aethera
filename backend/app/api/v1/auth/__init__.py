from fastapi import APIRouter

from app.api.v1.auth.auth import router as auth_router
from app.api.v1.auth.handle_provider_callback import router as provider_callback_router
from app.api.v1.auth.list_providers import router as list_providers_router
from app.api.v1.auth.start_provider_login import router as start_provider_login_router

router = APIRouter(prefix="/auth")
router.include_router(auth_router)
router.include_router(list_providers_router)
router.include_router(start_provider_login_router)
router.include_router(provider_callback_router)
