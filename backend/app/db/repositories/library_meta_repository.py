from __future__ import annotations

from typing import List, Optional

import time

from sqlalchemy import select

from app.db.sql.models import LibraryMetaORM
from app.db.sql.session import SessionLocal
from app.schemas.media_id import MediaID
from app.schemas.domain.library import LibraryMeta


class LibraryMetaRepository:
    @staticmethod
    def _to_model(row: LibraryMetaORM) -> LibraryMeta:
        return LibraryMeta.model_validate(
            {
                "media_id": row.media_id,
                "status": row.status,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )

    async def get_all(self) -> List[LibraryMeta]:
        with SessionLocal() as session:
            rows = session.execute(select(LibraryMetaORM)).scalars().all()
            return [self._to_model(row) for row in rows]

    async def insert(self, model: LibraryMeta) -> str:
        with SessionLocal() as session:
            session.add(
                LibraryMetaORM(
                    media_id=str(model.media_id),
                    status=model.status,
                    created_at=model.created_at,
                    updated_at=model.updated_at,
                )
            )
            session.commit()
            return str(model.media_id)

    async def find_by_media_id(self, media_id: MediaID) -> Optional[LibraryMeta]:
        with SessionLocal() as session:
            row = session.get(LibraryMetaORM, str(media_id))
            return self._to_model(row) if row else None

    async def upsert_meta(self, model: LibraryMeta) -> None:
        with SessionLocal() as session:
            row = session.get(LibraryMetaORM, str(model.media_id))
            if row is None:
                row = LibraryMetaORM(
                    media_id=str(model.media_id),
                    status=model.status,
                    created_at=model.created_at,
                    updated_at=model.updated_at,
                )
                session.add(row)
            else:
                row.status = model.status
                row.created_at = model.created_at
                row.updated_at = model.updated_at
            session.commit()

    async def archive_by_media_id(self, media_id: MediaID) -> bool:
        with SessionLocal() as session:
            row = session.get(LibraryMetaORM, str(media_id))
            if row is None:
                return False
            row.status = "archived"
            row.updated_at = time.time()
            session.commit()
            return True
