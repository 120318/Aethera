from pydantic import BaseModel


class MediaServerDetailLink(BaseModel):
    media_server_id: str
    media_server_type: str
    detail_url: str

