from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.config.directories.integrity import router
from app.schemas.domain.command import (
    CommandInitiator,
    CommandRecord,
    CommandStatus,
    CommandTargetType,
    CommandType,
    DirectoryIntegrityScanCommandRecordPayload,
)


def test_directory_integrity_scan_accepts_empty_body(monkeypatch):
    captured = []

    async def fake_create_command(request):
        captured.append(request)
        return CommandRecord(
            id="cmd-1",
            type=CommandType.DIRECTORY_INTEGRITY_SCAN,
            status=CommandStatus.QUEUED,
            payload=DirectoryIntegrityScanCommandRecordPayload(),
            initiator=CommandInitiator.MANUAL,
            target_type=CommandTargetType.DIRECTORY,
            target_id="directory_integrity",
            created_at=datetime.now(),
        )

    monkeypatch.setattr("app.api.v1.config.directories.integrity.command_service.create_command", fake_create_command)
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.post("/config/directories/integrity/scan")

    assert response.status_code == 200
    assert captured[0].payload.directory_id is None
