"""
textAPItext
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.domain.resource.parser import resource_parser

router = APIRouter()


class AttributesListResponse(BaseModel):
    status: str
    message_key: str
    data: list[str]


@router.get("/attributes/versions", response_model=AttributesListResponse)
async def get_available_versions() -> AttributesListResponse:
    """
    text
    """
    versions = list(resource_parser.version_patterns.keys())
    
    return AttributesListResponse(
        status="ok",
        message_key="operationMessages.resourceParser.versionsRetrieved",
        data=versions,
    )
