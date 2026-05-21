from app.api.v1.resource.parser.attributes_groups import (
    router as attributes_groups_router,
)
from app.api.v1.resource.parser.attributes_resource_forms import (
    router as attributes_resource_forms_router,
)
from app.api.v1.resource.parser.attributes_sources import (
    router as attributes_sources_router,
)
from app.api.v1.resource.parser.attributes_versions import (
    router as attributes_versions_router,
)
from app.api.v1.resource.parser.batch import router as batch_router
from app.api.v1.resource.parser.parse_title import router as parse_title_router
from app.api.v1.resource.parser.parse_titles_batch import (
    router as parse_titles_batch_router,
)
from app.api.v1.resource.parser.test import router as test_router
from app.api.v1.resource.parser.title import router as title_router
from fastapi import APIRouter

router = APIRouter()

router.include_router(batch_router)
router.include_router(test_router)
router.include_router(title_router)
router.include_router(parse_title_router)
router.include_router(parse_titles_batch_router)
router.include_router(attributes_groups_router)
router.include_router(attributes_sources_router)
router.include_router(attributes_resource_forms_router)
router.include_router(attributes_versions_router)
