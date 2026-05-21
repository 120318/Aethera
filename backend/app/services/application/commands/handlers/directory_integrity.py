from __future__ import annotations

import uuid
from hashlib import sha1

from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandRecord,
    CommandResult,
    CommandTargetType,
    CommandType,
    DirectoryIntegrityScanCommandRecordPayload,
    DirectoryIntegrityRepairCommandRecordPayload,
)
from app.schemas.runtime.command_runtime import CommandActionContext
from app.schemas.runtime.directory_integrity import DirectoryIntegrityIssueType, DirectoryIntegrityItem, DirectoryIntegrityRepairRequest
from app.services.application.workflows.directory_integrity import directory_integrity_service
from app.services.config.settings_service import settings_service


ISSUE_LABELS = {
    DirectoryIntegrityIssueType.unmanaged_library_file: "未管理的库文件",
    DirectoryIntegrityIssueType.missing_library_file: "库文件缺失",
    DirectoryIntegrityIssueType.unmanaged_download_entry: "未管理的下载项",
    DirectoryIntegrityIssueType.missing_download_file: "下载文件缺失",
    DirectoryIntegrityIssueType.missing_downloader_torrent: "下载器种子缺失",
    DirectoryIntegrityIssueType.unhealthy_downloader_torrent: "下载器种子异常",
}


DIRECTORY_INTEGRITY_SCAN_TARGET_ID = "directory_integrity"


class DirectoryIntegrityScanCommandHandler:
    command_type = CommandType.DIRECTORY_INTEGRITY_SCAN

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        directory_id = request.directory_id
        target_id = directory_id or DIRECTORY_INTEGRITY_SCAN_TARGET_ID
        directory = settings_service.get_directory_by_id(directory_id) if directory_id else None
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.DIRECTORY_INTEGRITY_SCAN,
            payload=DirectoryIntegrityScanCommandRecordPayload(directory_id=directory_id),
            initiator=body.initiator,
            uniq_key=f"command:{CommandType.DIRECTORY_INTEGRITY_SCAN.value}:{target_id}",
            target_type=CommandTargetType.DIRECTORY,
            target_id=target_id,
            target_label=directory.name if directory else "目录完整性扫描",
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        result = await directory_integrity_service.scan(command.payload.directory_id)
        return CommandResult(result_count=result.summary.total)

    def resolve_running_message(self) -> str:
        return "正在扫描目录完整性"

    def resolve_success_message(self, result: CommandResult) -> str:
        return "目录完整性扫描完成"

    def resolve_failed_message(self) -> str:
        return "目录完整性扫描失败"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        return CommandActionContext()


class DirectoryIntegrityRepairCommandHandler:
    command_type = CommandType.DIRECTORY_INTEGRITY_REPAIR

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        item_ids = list(request.item_ids or [])
        payload = DirectoryIntegrityRepairCommandRecordPayload(
            scan_id=request.scan_id,
            item_ids=item_ids,
        )
        target_id = item_ids[0] if len(item_ids) == 1 else request.scan_id
        item = await self._resolve_item(request.scan_id, target_id) if len(item_ids) == 1 else None
        target_label = self._target_label(item)
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.DIRECTORY_INTEGRITY_REPAIR,
            payload=payload,
            initiator=body.initiator,
            uniq_key=self._uniq_key(request.scan_id, item_ids),
            target_type=CommandTargetType.DIRECTORY,
            target_id=target_id,
            target_label=target_label,
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        result = await directory_integrity_service.repair(
            DirectoryIntegrityRepairRequest(scan_id=payload.scan_id, item_ids=list(payload.item_ids or []))
        )
        return CommandResult(
            result_count=result.repaired_count,
            repaired_count=result.repaired_count,
            failed_count=result.failed_count,
        )

    def resolve_running_message(self) -> str:
        return "正在修复目录完整性"

    def resolve_success_message(self, result: CommandResult) -> str:
        return "目录完整性修复完成"

    def resolve_failed_message(self) -> str:
        return "目录完整性修复失败"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        return CommandActionContext()

    @staticmethod
    def _uniq_key(scan_id: str, item_ids: list[str]) -> str:
        if len(item_ids) == 1:
            target = item_ids[0]
        else:
            digest = sha1(",".join(sorted(item_ids)).encode("utf-8")).hexdigest() if item_ids else "all"
            target = f"{scan_id}:{digest}"
        return f"command:{CommandType.DIRECTORY_INTEGRITY_REPAIR.value}:{target}"

    @staticmethod
    async def _resolve_item(scan_id: str, item_id: str) -> DirectoryIntegrityItem | None:
        latest = await directory_integrity_service.latest()
        if not latest or latest.scan_id != scan_id:
            return None
        return next((item for item in latest.items if item.id == item_id), None)

    @staticmethod
    def _target_label(item: DirectoryIntegrityItem | None) -> str:
        if item is None:
            return "目录差异"
        label = ISSUE_LABELS.get(item.issue_type, item.issue_type.value)
        media_label = item.media_title
        if media_label and item.media_year:
            media_label = f"{media_label} ({item.media_year})"
        path = media_label or item.display_name or item.relative_path or item.path
        return f"{label}：{path}" if path else label


def register_directory_integrity_command_handlers(registry) -> None:
    registry.register(DirectoryIntegrityScanCommandHandler())
    registry.register(DirectoryIntegrityRepairCommandHandler())
