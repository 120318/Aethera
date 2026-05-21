"""
textAPItext
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.schemas.domain.resource_attributes import ResourceAttributes
from app.services.domain.resource.parser import ResourceParser

router = APIRouter()

# Internal note.
resource_parser = ResourceParser()


class ParseTitleRequest(BaseModel):
    title: str = Field(...)
    desc: str | None = None


class ParseTitleResponse(BaseModel):
    title: str = Field(...)
    attributes: ResourceAttributes | None = None


@router.post("/title", response_model=ParseTitleResponse)
async def parse_title(request: ParseTitleRequest) -> ParseTitleResponse:
    """
    text，text
    """
    # Internal note.
    attributes = resource_parser.parse(request.title, desc=request.desc or "")
    
    # Internal note.
    response = ParseTitleResponse(
        title=request.title,
        attributes=attributes,
    )
    return response
