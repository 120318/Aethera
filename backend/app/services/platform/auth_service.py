from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from fastapi import Request

from app.db.repositories.auth_session_repository import AuthSessionRepository
from app.schemas.exception.exceptions import (
    AuthenticationRequiredException,
    InvalidCredentialsException,
    SystemAlreadyInitializedException,
)
from app.services.config.settings_service import settings_service

PBKDF2_ALG = "pbkdf2_sha256"
PERSISTENT_SESSION_COOKIE_MAX_AGE_SECONDS = 10 * 365 * 24 * 60 * 60


@dataclass(frozen=True)
class Session:
    token: str
    username: str
    expires_at: float


class AuthService:
    COOKIE_NAME = "am_session"
    USERNAME = "admin"

    def __init__(self) -> None:
        self._session_repo = AuthSessionRepository()

    def is_enabled(self) -> bool:
        return True

    def is_initialized(self) -> bool:
        return bool(self.get_password_hash())

    def is_configured(self) -> bool:
        return self.is_initialized()

    def get_password_hash(self) -> str | None:
        return settings_service.get_base_auth_config().password_hash or None

    def get_session_ttl_seconds(self) -> int:
        ttl = int(settings_service.get_base_auth_config().session_ttl_seconds or 0)
        if ttl == 0:
            return 0
        return ttl if ttl > 0 else 86400

    def get_session_cookie_max_age_seconds(self) -> int:
        ttl = self.get_session_ttl_seconds()
        if ttl == 0:
            return PERSISTENT_SESSION_COOKIE_MAX_AGE_SECONDS
        return ttl

    def set_password(self, password: str) -> None:
        auth_config = settings_service.get_base_auth_config()
        settings_service.update_auth_config(enabled=True, session_ttl_seconds=auth_config.session_ttl_seconds)
        settings_service.update_auth_password_hash(self.hash_password(password))
        # Internal note.
        self._session_repo.clear_all()

    def bootstrap(self, password: str) -> Session:
        if self.is_initialized():
            raise SystemAlreadyInitializedException()
        self.set_password(password)
        return self.issue_session()

    def change_password(self, old_password: str, new_password: str) -> None:
        stored = self.get_password_hash()
        if not stored or not self.verify_password(old_password, stored):
            raise InvalidCredentialsException()
        self.set_password(new_password)

    def issue_session(self) -> Session:
        now = time.time()
        ttl = self.get_session_ttl_seconds()
        token = secrets.token_urlsafe(32)
        expires_at = 0.0 if ttl == 0 else now + ttl
        sess = Session(token=token, username=self.USERNAME, expires_at=expires_at)
        # Internal note.
        self._session_repo.insert(token, sess.username, sess.expires_at)
        return sess

    def revoke_session(self, token: str) -> None:
        if token:
            # Internal note.
            self._session_repo.remove(token)

    def _get_session(self, token: str) -> Session | None:
        record = self._session_repo.find_by_token(token)
        if record is None:
            return None

        expires_at = float(record.expires_at or 0)
        if expires_at > 0 and expires_at <= time.time():
            self.revoke_session(token)
            return None

        return Session(
            token=token,
            username=record.username or self.USERNAME,
            expires_at=expires_at,
        )

    def extract_token(self, request: Request) -> str | None:
        auth = request.headers.get("authorization")
        if auth:
            parts = auth.split(" ", 1)
            if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
                return parts[1].strip()
        return request.cookies.get(self.COOKIE_NAME)

    def is_https_request(self, request: Request) -> bool:
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if forwarded_proto:
            first = next((part.strip().lower() for part in forwarded_proto.split(",") if part.strip()), "")
            if first:
                return first == "https"
        return request.url.scheme.lower() == "https"

    def cleanup_expired_sessions(self) -> int:
        """Internal helper."""
        now = time.time()
        return self._session_repo.remove_expired(now)

    def current_session(self, request: Request) -> Session | None:
        if not self.is_enabled():
            return None
        token = self.extract_token(request)
        if not token:
            return None
        return self._get_session(token)

    def require_session(self, request: Request) -> Session:
        sess = self.current_session(request)
        if not sess:
            raise AuthenticationRequiredException()
        return sess

    @staticmethod
    def hash_password(password: str, iterations: int = 200_000) -> str:
        if not password:
            raise ValueError("password required")
        salt = secrets.token_bytes(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return f"{PBKDF2_ALG}${iterations}${salt.hex()}${dk.hex()}"

    @staticmethod
    def _parse_hash(stored: str) -> tuple[int, bytes, bytes]:
        alg, iters_s, salt_hex, hash_hex = stored.split("$", 3)
        if alg != PBKDF2_ALG:
            raise ValueError("unsupported password hash")
        return int(iters_s), bytes.fromhex(salt_hex), bytes.fromhex(hash_hex)

    @classmethod
    def verify_password(cls, password: str, stored_hash: str) -> bool:
        try:
            iterations, salt, expected = cls._parse_hash(stored_hash)
        except ValueError:
            return False
        got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(got, expected)


auth_service = AuthService()
