from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

from app.schemas.runtime.auth_provider import ExternalAuthState
from app.services.config.settings_service import settings_service


class ExternalAuthStateService:
    COOKIE_NAME = "am_auth_state"
    TTL_SECONDS = 600

    def create_state(self, provider_id: str, next_path: str) -> ExternalAuthState:
        now = int(time.time())
        return ExternalAuthState(
            provider_id=provider_id,
            state=secrets.token_urlsafe(24),
            nonce=secrets.token_urlsafe(24),
            code_verifier=secrets.token_urlsafe(48),
            next_path=self._normalize_next_path(next_path),
            expires_at=now + self.TTL_SECONDS,
        )

    def encode(self, state: ExternalAuthState) -> str:
        payload = state.model_dump_json().encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
        signature = self._sign(payload_b64)
        return f"{payload_b64}.{signature}"

    def decode(self, value: str | None) -> ExternalAuthState | None:
        if not value or "." not in value:
            return None
        payload_b64, signature = value.split(".", 1)
        if not hmac.compare_digest(signature, self._sign(payload_b64)):
            return None
        payload = self._decode_payload(payload_b64)
        if payload is None:
            return None
        if payload.expires_at <= int(time.time()):
            return None
        return payload.model_copy(update={"next_path": self._normalize_next_path(payload.next_path)})

    def validate(self, value: str | None, provider_id: str, returned_state: str) -> ExternalAuthState | None:
        decoded = self.decode(value)
        if decoded is None:
            return None
        if decoded.provider_id != provider_id:
            return None
        if decoded.state != returned_state:
            return None
        return decoded

    def _sign(self, payload_b64: str) -> str:
        secret = self._secret().encode("utf-8")
        digest = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    def _secret(self) -> str:
        env_secret = os.getenv("AETHERA_AUTH_STATE_SECRET", "").strip()
        if env_secret:
            return env_secret
        password_hash = settings_service.get_base_auth_config().password_hash or ""
        if password_hash:
            return password_hash
        return "aethera-auth-state-secret"

    def _decode_payload(self, payload_b64: str) -> ExternalAuthState | None:
        padding = "=" * (-len(payload_b64) % 4)
        try:
            raw = base64.urlsafe_b64decode(f"{payload_b64}{padding}")
            return ExternalAuthState.model_validate_json(raw)
        except ValueError:
            return None

    def _normalize_next_path(self, next_path: str) -> str:
        if next_path.startswith("/"):
            return next_path
        return "/discover"


external_auth_state_service = ExternalAuthStateService()
