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


@router.get("/attributes/sources", response_model=AttributesListResponse)
async def get_available_sources() -> AttributesListResponse:
    """
    text
    """
    sources = list(resource_parser.source_patterns.keys())
    
    return AttributesListResponse(
        status="ok",
        message_key="operationMessages.resourceParser.sourcesRetrieved",
        data=sources,
    )
