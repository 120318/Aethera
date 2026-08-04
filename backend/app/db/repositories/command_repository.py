from __future__ import annotations

import json
from typing import Any

from datetime import datetime

from sqlalchemy import delete, desc, select, text, update

from app.db.repositories.action_repository import ActionRepository
from app.db.sql.models import ActionORM, CommandORM
from app.db.sql.session import SessionLocal
from app.schemas.domain.action import ActionRecord
from app.schemas.domain.command import CommandRecord, CommandStatus, CommandTargetType, CommandType


ACTIVE_COMMAND_STATUSES = [
    CommandStatus.READY.value,
    CommandStatus.QUEUED.value,
    CommandStatus.RUNNING.value,
]
DEDUPLICATED_COMMAND_STATUSES = [
    CommandStatus.READY.value,
    CommandStatus.QUEUED.value,
    CommandStatus.RUNNING.value,
]


class CommandRepository:
    def cond_id(self, command_id: str) -> str:
        return command_id

    @staticmethod
    def _normalize_params(raw) -> dict[str, Any]:
        if type(raw) is dict:
            return {str(key): value for key, value in raw.items() if value is not None}
        if type(raw) is str and raw:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            if type(data) is dict:
                return {str(key): value for key, value in data.items() if value is not None}
        return {}

    @staticmethod
    def _to_model(row: CommandORM) -> CommandRecord:
        payload = {
            "id": row.id,
            "type": row.type,
            "status": row.status,
            "message_key": row.message_key,
            "message_params": CommandRepository._normalize_params(row.message_params_json),
            "payload": row.payload_json,
            "result": row.result_json,
            "error": row.error,
            "error_key": row.error_key,
            "error_params": CommandRepository._normalize_params(row.error_params_json),
            "initiator": row.initiator,
            "media_id": row.media_id,
            "target_season_number": row.target_season_number,
            "uniq_key": row.uniq_key,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "target_label": row.target_label,
            "created_at": row.created_at,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }
        return CommandRecord.model_validate(payload)

    async def get_all(self) -> list[CommandRecord]:
        with SessionLocal() as session:
            rows = session.execute(select(CommandORM).order_by(desc(CommandORM.created_at))).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_id(self, command_id: str) -> CommandRecord | None:
        with SessionLocal() as session:
            row = session.get(CommandORM, command_id)
            return self._to_model(row) if row else None

    async def insert(self, command: CommandRecord) -> str:
        with SessionLocal() as session:
            session.add(
                CommandORM(
                    id=command.id,
                    type=command.type.value,
                    status=command.status.value,
                    message_key=command.message_key,
                    message_params_json=command.message_params,
                    payload_json=command.payload.model_dump(mode="json"),
                    result_json=command.result.model_dump(mode="json") if command.result else None,
                    error=command.error,
                    error_key=command.error_key,
                    error_params_json=command.error_params,
                    initiator=command.initiator.value,
                    media_id=str(command.media_id) if command.media_id else None,
                    target_season_number=command.target_season_number,
                    uniq_key=command.uniq_key,
                    target_type=command.target_type.value,
                    target_id=command.target_id,
                    target_label=command.target_label,
                    created_at=command.created_at.isoformat(),
                    started_at=command.started_at.isoformat() if command.started_at else None,
                    finished_at=command.finished_at.isoformat() if command.finished_at else None,
                )
            )
            session.commit()
            return command.id

    async def update(self, command: CommandRecord, cond: str) -> bool:
        command_id = cond
        values = {
            "type": command.type.value,
            "status": command.status.value,
            "message_key": command.message_key,
            "message_params_json": command.message_params,
            "payload_json": command.payload.model_dump(mode="json"),
            "result_json": command.result.model_dump(mode="json") if command.result else None,
            "error": command.error,
            "error_key": command.error_key,
            "error_params_json": command.error_params,
            "initiator": command.initiator.value,
            "media_id": str(command.media_id) if command.media_id else None,
            "target_season_number": command.target_season_number,
            "uniq_key": command.uniq_key,
            "target_type": command.target_type.value,
            "target_id": command.target_id,
            "target_label": command.target_label,
            "created_at": command.created_at.isoformat(),
            "started_at": command.started_at.isoformat() if command.started_at else None,
            "finished_at": command.finished_at.isoformat() if command.finished_at else None,
        }
        with SessionLocal() as session:
            result = session.execute(update(CommandORM).where(CommandORM.id == command_id).values(**values))
            session.commit()
            return bool(result.rowcount)

    async def cancel_queued_command(self, command_id: str, finished_at_iso: str) -> bool:
        with SessionLocal() as session:
            result = session.execute(
                update(CommandORM)
                .where(CommandORM.id == command_id, CommandORM.status == CommandStatus.QUEUED.value)
                .values(
                    status=CommandStatus.CANCELLED.value,
                    message_key=None,
                    message_params_json={},
                    error=None,
                    error_key=None,
                    error_params_json={},
                    finished_at=finished_at_iso,
                )
            )
            session.commit()
            return bool(result.rowcount)

    async def publish_staged_command(
        self,
        command: CommandRecord,
        action: ActionRecord,
    ) -> bool:
        with SessionLocal() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(CommandORM, command.id)
            if row is None or row.status != CommandStatus.READY.value:
                session.rollback()
                return False
            ActionRepository.add_to_session(session, action)
            row.status = CommandStatus.QUEUED.value
            row.message_key = command.message_key
            row.message_params_json = command.message_params
            try:
                session.commit()
            except Exception:
                session.rollback()
                raise
            return True

    async def mark_staged_command_ready(self, command_id: str) -> bool:
        with SessionLocal() as session:
            result = session.execute(
                update(CommandORM)
                .where(
                    CommandORM.id == command_id,
                    CommandORM.status == CommandStatus.STAGED.value,
                )
                .values(status=CommandStatus.READY.value)
            )
            session.commit()
            return bool(result.rowcount)

    def finalize_staged_replacement(self, command_id: str, before_ready) -> None:
        with SessionLocal.begin() as session:
            before_ready(session)
            self._finalize_staged_replacement(session, command_id)

    @staticmethod
    def _finalize_staged_replacement(session, command_id: str) -> None:
        row = session.get(CommandORM, command_id)
        if row is None or row.status != CommandStatus.STAGED.value:
            raise RuntimeError(f"Staged command disappeared before finalization: {command_id}")

        finished_at = datetime.now().isoformat()
        superseded_ids = [
            item[0]
            for item in session.execute(
                select(CommandORM.id).where(
                    CommandORM.uniq_key == row.uniq_key,
                    CommandORM.status == CommandStatus.QUEUED.value,
                    CommandORM.id != command_id,
                )
            ).all()
        ]
        if superseded_ids:
            session.execute(
                update(CommandORM)
                .where(CommandORM.id.in_(superseded_ids))
                .values(
                    status=CommandStatus.CANCELLED.value,
                    message_key=None,
                    message_params_json={},
                    error=None,
                    error_key=None,
                    error_params_json={},
                    finished_at=finished_at,
                )
            )
            session.execute(
                update(ActionORM)
                .where(
                    ActionORM.id.in_(superseded_ids),
                    ActionORM.status == "queued",
                )
                .values(status="cancelled", finished_at=finished_at)
            )
        row.status = CommandStatus.READY.value

    async def reserve_ready_command(self, command_id: str) -> bool:
        with SessionLocal() as session:
            result = session.execute(
                update(CommandORM)
                .where(
                    CommandORM.id == command_id,
                    CommandORM.status == CommandStatus.READY.value,
                )
                .values(status=CommandStatus.STAGED.value)
            )
            session.commit()
            return bool(result.rowcount)

    async def find_next_ready(self) -> CommandRecord | None:
        with SessionLocal() as session:
            row = session.execute(
                select(CommandORM)
                .where(CommandORM.status == CommandStatus.READY.value)
                .order_by(CommandORM.created_at.asc())
                .limit(1)
            ).scalars().first()
            return self._to_model(row) if row else None

    async def delete_expired_staged_commands(self, created_before_iso: str) -> int:
        with SessionLocal() as session:
            result = session.execute(
                delete(CommandORM).where(
                    CommandORM.status == CommandStatus.STAGED.value,
                    CommandORM.created_at < created_before_iso,
                )
            )
            session.commit()
            return int(result.rowcount or 0)

    async def delete_staged_command(self, command_id: str) -> bool:
        with SessionLocal() as session:
            result = session.execute(
                delete(CommandORM).where(
                    CommandORM.id == command_id,
                    CommandORM.status == CommandStatus.STAGED.value,
                )
            )
            session.commit()
            return bool(result.rowcount)

    async def find_active(self) -> list[CommandRecord]:
        with SessionLocal() as session:
            rows = session.execute(
                select(CommandORM)
                .where(CommandORM.status.in_(ACTIVE_COMMAND_STATUSES))
                .order_by(desc(CommandORM.created_at))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_running(self) -> list[CommandRecord]:
        with SessionLocal() as session:
            rows = session.execute(
                select(CommandORM)
                .where(CommandORM.status == CommandStatus.RUNNING.value)
                .order_by(desc(CommandORM.created_at))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_next_queued(self) -> CommandRecord | None:
        with SessionLocal() as session:
            row = session.execute(
                select(CommandORM)
                .where(CommandORM.status == CommandStatus.QUEUED.value)
                .order_by(CommandORM.created_at.asc())
                .limit(1)
            ).scalars().first()
            return self._to_model(row) if row else None

    async def find_active_filtered(
        self,
        target_type: CommandTargetType | None = None,
        target_ids: list[str] | None = None,
        target_season_number: int | None = None,
        command_types: list[CommandType] | None = None,
    ) -> list[CommandRecord]:
        with SessionLocal() as session:
            stmt = select(CommandORM).where(
                CommandORM.status.in_(ACTIVE_COMMAND_STATUSES)
            )
            if target_type:
                stmt = stmt.where(CommandORM.target_type == target_type.value)
            if target_ids:
                stmt = stmt.where(CommandORM.target_id.in_(target_ids))
            if target_season_number is not None:
                stmt = stmt.where(CommandORM.target_season_number == target_season_number)
            if command_types:
                stmt = stmt.where(CommandORM.type.in_([command_type.value for command_type in command_types]))
            stmt = stmt.order_by(desc(CommandORM.created_at))
            rows = session.execute(stmt).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_active_by_media(
        self,
        media_id: str,
        *,
        target_season_number: int | None = None,
        command_types: list[CommandType] | None = None,
    ) -> list[CommandRecord]:
        with SessionLocal() as session:
            stmt = select(CommandORM).where(
                CommandORM.media_id == media_id,
                CommandORM.status.in_(ACTIVE_COMMAND_STATUSES),
            )
            if target_season_number is not None:
                stmt = stmt.where(CommandORM.target_season_number == target_season_number)
            if command_types:
                stmt = stmt.where(CommandORM.type.in_([command_type.value for command_type in command_types]))
            stmt = stmt.order_by(desc(CommandORM.created_at))
            rows = session.execute(stmt).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_active_by_uniq_key(self, uniq_key: str) -> CommandRecord | None:
        with SessionLocal() as session:
            row = session.execute(
                select(CommandORM)
                .where(
                    CommandORM.uniq_key == uniq_key,
                    CommandORM.status.in_(DEDUPLICATED_COMMAND_STATUSES),
                )
                .order_by(desc(CommandORM.created_at))
                .limit(1)
            ).scalars().first()
            return self._to_model(row) if row else None

    async def find_recent(self, limit: int = 20, statuses: list[CommandStatus] | None = None) -> list[CommandRecord]:
        with SessionLocal() as session:
            stmt = select(CommandORM)
            if statuses:
                stmt = stmt.where(CommandORM.status.in_([status.value for status in statuses]))
            stmt = stmt.order_by(desc(CommandORM.created_at)).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [self._to_model(row) for row in rows]
