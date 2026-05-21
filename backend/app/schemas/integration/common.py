from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")

class ClientOperationResult(BaseModel):
    """Internal helper."""
    success: bool = Field(True, description="Field description")
    message: str | None = Field(None, description="Field description")
    id: str | None = Field(None, description="Field description")

class PaginatedResponse(BaseModel, Generic[T]):
    """Internal helper."""
    items: list[T]
    total: int
    page: int
    size: int
