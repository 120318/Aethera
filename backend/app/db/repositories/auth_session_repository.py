from __future__ import annotations

from sqlalchemy import delete, select, update

from app.db.sql.models import AuthSessionORM
from app.db.sql.session import SessionLocal
from app.schemas.persistence.auth_session import AuthSessionRecord


class AuthSessionRepository:
    def clear_all(self) -> int:
        with SessionLocal() as session:
            result = session.execute(delete(AuthSessionORM))
            session.commit()
            return int(result.rowcount or 0)

    def insert(self, token: str, username: str, expires_at: float) -> None:
        with SessionLocal() as session:
            session.add(AuthSessionORM(token=token, username=username, expires_at=expires_at))
            session.commit()

    def remove(self, token: str) -> bool:
        with SessionLocal() as session:
            result = session.execute(delete(AuthSessionORM).where(AuthSessionORM.token == token))
            session.commit()
            return bool(result.rowcount)

    def find_by_token(self, token: str) -> AuthSessionRecord | None:
        with SessionLocal() as session:
            row = session.get(AuthSessionORM, token)
            if row is None:
                return None
            return AuthSessionRecord(token=row.token, username=row.username, expires_at=row.expires_at)

    def remove_expired(self, now: float) -> int:
        with SessionLocal() as session:
            result = session.execute(
                delete(AuthSessionORM).where(
                    AuthSessionORM.expires_at > 0,
                    AuthSessionORM.expires_at <= now,
                )
            )
            session.commit()
            return int(result.rowcount or 0)

    def update_active_expirations(self, now: float, expires_at: float) -> int:
        with SessionLocal() as session:
            result = session.execute(
                update(AuthSessionORM)
                .where(
                    (AuthSessionORM.expires_at == 0) | (AuthSessionORM.expires_at > now)
                )
                .values(expires_at=expires_at)
            )
            session.commit()
            return int(result.rowcount or 0)

    def list_all(self) -> list[AuthSessionRecord]:
        with SessionLocal() as session:
            rows = session.execute(select(AuthSessionORM)).scalars().all()
            return [AuthSessionRecord(token=row.token, username=row.username, expires_at=row.expires_at) for row in rows]
