"""
textAPItext
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.schemas.domain.resource_attributes import ResourceAttributes
from app.services.domain.resource.parser import resource_parser

router = APIRouter()


class ParseTitleRequest(BaseModel):
    title: str = Field(...)
    desc: str | None = None


class ParseTitleResponse(BaseModel):
    title: str = Field(...)
    attributes: ResourceAttributes | None = None
    success: bool = True
    message_key: str | None = None


@router.post("/parse-title", response_model=ParseTitleResponse)
async def parse_resource_title(request: ParseTitleRequest) -> ParseTitleResponse:
    """
    text，text
    
    Args:
        request: text
        
    Returns:
        text
    """
    attributes = resource_parser.parse(
        title=request.title,
        desc=request.desc or "",
    )

    return ParseTitleResponse(
        title=request.title,
        attributes=attributes,
        success=True,
        message_key=None,
    )
