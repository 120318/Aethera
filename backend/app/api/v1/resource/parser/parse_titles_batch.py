"""
textAPItext
"""

from fastapi import APIRouter

from app.schemas.exception import EmptyTitlesException
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.services.domain.resource.parser import resource_parser
from pydantic import BaseModel

router = APIRouter()


class BatchParseItem(BaseModel):
    success: bool
    title: str
    data: ResourceAttributes | None = None
    error: str | None = None


class BatchParseResponse(BaseModel):
    status: str
    message_key: str
    results: list[BatchParseItem]
    total_count: int
    successful_count: int
    failed_count: int


@router.post("/parse-titles-batch", response_model=BatchParseResponse)
async def parse_resource_titles_batch(titles: list[str]) -> BatchParseResponse:
    """
    text
    
    Args:
        titles: text
        
    Returns:
        text
    """
    if not titles:
        raise EmptyTitlesException()

    results: list[BatchParseItem] = []
    successful_count = 0
    failed_count = 0

    for title in titles:
        attributes = resource_parser.parse(title)

        results.append(
            BatchParseItem(
                success=True,
                title=title,
                data=attributes,
            )
        )
        successful_count += 1

    return BatchParseResponse(
        status="ok",
        message_key="operationMessages.resourceParser.batchParsed",
        results=results,
        total_count=len(titles),
        successful_count=successful_count,
        failed_count=failed_count,
    )
