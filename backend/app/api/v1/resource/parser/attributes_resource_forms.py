"""
textAPItext
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.domain.quality_values import QUALITY_RESOURCE_FORM_VALUES

router = APIRouter()


class AttributesListResponse(BaseModel):
    status: str
    message_key: str
    data: list[str]


@router.get("/attributes/resource-forms", response_model=AttributesListResponse)
async def get_available_resource_forms() -> AttributesListResponse:
    """
    text
    """
    return AttributesListResponse(
        status="ok",
        message_key="operationMessages.resourceParser.resourceFormsRetrieved",
        data=[str(item) for item in QUALITY_RESOURCE_FORM_VALUES],
    )
