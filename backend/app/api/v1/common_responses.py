from pydantic import BaseModel, Field


class OperationResponse(BaseModel):
    ok: bool = True
    message_key: str | None = None
    params: dict[str, str] = Field(default_factory=dict)
