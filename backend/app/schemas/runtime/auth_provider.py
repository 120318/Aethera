from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuthProviderSummary(BaseModel):
    id: str
    type: str
    name: str


class AuthStartResult(BaseModel):
    redirect_url: str


class AuthIdentity(BaseModel):
    provider_id: str
    subject: str
    email: str
    username: str
    groups: list[str] = Field(default_factory=list)


class AuthCallbackContext(BaseModel):
    code: str
    redirect_uri: str
    code_verifier: str
    nonce: str


class OIDCDiscoveryDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str = ""
    jwks_uri: str


class OIDCTokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str
    id_token: str


class OIDCClaimsEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    sub: str = ""
    email: str = ""
    preferred_username: str = ""
    nonce: str = ""
    groups: list[str] = Field(default_factory=list)

    def read_string(self, key: str) -> str:
        if key == "sub":
            return self.sub
        if key == "email":
            return self.email
        if key == "preferred_username":
            return self.preferred_username
        if key == "nonce":
            return self.nonce
        extra = self.model_extra or {}
        value = extra[key] if key in extra else None
        return value if type(value) is str else ""

    def read_groups(self, key: str) -> list[str]:
        if key == "groups":
            return list(self.groups)
        extra = self.model_extra or {}
        value = extra[key] if key in extra else None
        if type(value) is not list:
            return []
        return [item for item in value if type(item) is str]


class ExternalAuthState(BaseModel):
    provider_id: str
    state: str
    nonce: str
    code_verifier: str
    next_path: str
    expires_at: int
