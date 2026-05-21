from pydantic import BaseModel

from app.schemas.media_id import MediaID


class CommandActionContext(BaseModel):
    media_id: MediaID | None = None
    task_id: str | None = None
