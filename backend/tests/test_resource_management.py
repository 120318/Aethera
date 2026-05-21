import os
import uuid
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.api.v1.library.manage import DeleteMediaRequest, delete_media_resources
from app.schemas.domain.command import CommandInitiator, CommandRecord, CommandTargetType, CommandType
from app.schemas.domain.media import MediaTarget


def _command() -> CommandRecord:
    from app.schemas.media_id import MediaID
    from app.schemas.domain.command import MediaDeleteCommandRecordPayload

    media_id = MediaID.parse("douban:tv:1")
    return CommandRecord(
        id="cmd-1",
        type=CommandType.MEDIA_DELETE,
        payload=MediaDeleteCommandRecordPayload(target=MediaTarget(media_id=media_id, season_number=1), mode="tasks_only"),
        initiator=CommandInitiator.MANUAL,
        media_id=media_id,
        target=MediaTarget(media_id=media_id, season_number=1),
        target_type=CommandTargetType.MEDIA,
        target_id=str(media_id),
    )


@pytest.mark.asyncio
async def test_delete_media_tasks_only_creates_media_delete_command(monkeypatch):
    create_command = AsyncMock(return_value=_command())
    monkeypatch.setattr("app.api.v1.library.manage.command_service.create_command", create_command)

    payload = DeleteMediaRequest(target={"media_id": "douban:tv:1", "season_number": 1}, mode="tasks_only", force=True, delete_files=True)
    resp = await delete_media_resources(payload)

    assert resp.command.type == CommandType.MEDIA_DELETE
    assert resp.command.payload.mode == "tasks_only"
    create_command.assert_awaited_once()
