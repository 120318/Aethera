from pydantic import BaseModel


class AuthSessionRecord(BaseModel):
    token: str
    username: str
    expires_at: float
