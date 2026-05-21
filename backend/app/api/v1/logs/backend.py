from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.audit.backend_log_reader_service import backend_log_reader_service

router = APIRouter()


class BackendLogResponse(BaseModel):
    cursor: str | None = None
    reset: bool = False
    lines: list[str] = Field(default_factory=list)
    source_file: str


@router.get("/backend", response_model=BackendLogResponse)
async def get_backend_logs(
    limit: int = Query(default=200, ge=1, le=1000),
    cursor: str | None = None,
) -> BackendLogResponse:
    result = backend_log_reader_service.read_backend_logs(limit=limit, cursor=cursor)
    return BackendLogResponse(
        cursor=result.cursor,
        reset=result.reset,
        lines=result.lines,
        source_file=result.source_file,
    )
