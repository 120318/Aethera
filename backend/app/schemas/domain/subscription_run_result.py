from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class SubscriptionRunResponse(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(from_attributes=True)

    checked: int = Field(default=0, description="Field description")
    added: int = Field(default=0, description="Field description")
