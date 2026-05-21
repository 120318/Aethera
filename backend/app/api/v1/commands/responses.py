from pydantic import BaseModel

from app.schemas.domain.command import CommandRecord


class CommandResponse(BaseModel):
    command: CommandRecord
