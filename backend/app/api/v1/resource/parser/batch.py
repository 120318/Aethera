"""
textAPItext
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.schemas.exception import EmptyTitlesException
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.services.domain.resource.parser import ResourceParser

router = APIRouter()

# Internal note.
resource_parser = ResourceParser()


class ParseTitleData(BaseModel):
    title: str = Field(...)
    attributes: ResourceAttributes | None = None


class BatchParseTitleRequest(BaseModel):
    titles: list[str] = Field(...)


class BatchParseTitleResponse(BaseModel):
    results: list[ParseTitleData] = Field(...)
    total_count: int = Field(...)
    successful_count: int = Field(...)
    failed_count: int = Field(...)


@router.post("/batch", response_model=BatchParseTitleResponse)
async def parse_titles_batch(request: BatchParseTitleRequest) -> BatchParseTitleResponse:
    """
    text
    """
    if not request.titles:
        raise EmptyTitlesException()

    results: list[ParseTitleData] = []
    for title in request.titles:
        attributes = resource_parser.parse(title)
        result = ParseTitleData(
            title=title,
            attributes=attributes,
        )

        results.append(result)

    successful_count = sum(1 for result in results if result.attributes is not None)
    failed_count = len(results) - successful_count
    return BatchParseTitleResponse(
        results=results,
        total_count=len(results),
        successful_count=successful_count,
        failed_count=failed_count,
    )
