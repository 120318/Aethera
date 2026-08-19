from pydantic import BaseModel

from app.schemas.domain.media import MediaIdentity
from app.schemas.media_id import MediaID


class CommandActionContext(BaseModel):
    media: MediaIdentity | None = None
    media_id: MediaID | None = None
    task_id: str | None = None
