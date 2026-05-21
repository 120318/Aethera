from app.db.sql.models import SchedulerRuntimeORM
from app.db.sql.session import SessionLocal
from app.schemas.runtime.scheduler_runtime import SchedulerRuntimeSnapshot


class SchedulerRuntimeRepository:
    @staticmethod
    def _to_model(row: SchedulerRuntimeORM) -> SchedulerRuntimeSnapshot:
        return SchedulerRuntimeSnapshot.model_validate(
            {
                "id": row.id,
                "running": bool(row.running),
                "items": row.items_json,
                "pending_manual_triggers": row.pending_manual_triggers_json,
                "updated_at": row.updated_at,
            }
        )

    async def get_snapshot(self) -> SchedulerRuntimeSnapshot | None:
        with SessionLocal() as session:
            row = session.get(SchedulerRuntimeORM, "runtime")
            return self._to_model(row) if row else None

    async def save_snapshot(self, snapshot: SchedulerRuntimeSnapshot) -> bool:
        with SessionLocal() as session:
            row = session.get(SchedulerRuntimeORM, snapshot.id)
            if row is None:
                row = SchedulerRuntimeORM(id=snapshot.id)
                session.add(row)

            row.running = bool(snapshot.running)
            row.items_json = [item.model_dump(mode="json") for item in snapshot.items]
            row.pending_manual_triggers_json = list(snapshot.pending_manual_triggers)
            row.updated_at = snapshot.updated_at
            session.commit()
            return True

    async def enqueue_manual_trigger(self, job_id: str) -> bool:
        snapshot = await self.get_snapshot()
        if snapshot is None:
            snapshot = SchedulerRuntimeSnapshot()
        snapshot.pending_manual_triggers.append(job_id)
        await self.save_snapshot(snapshot)
        return True

    async def pop_manual_triggers(self) -> list[str]:
        snapshot = await self.get_snapshot()
        if snapshot is None or not snapshot.pending_manual_triggers:
            return []
        pending = list(snapshot.pending_manual_triggers)
        snapshot.pending_manual_triggers = []
        await self.save_snapshot(snapshot)
        return pending
