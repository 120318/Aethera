from __future__ import annotations

import logging

from app.schemas.domain.download import TaskData, TransferFileResult
from app.schemas.domain.import_upgrade import ImportUpgradeDecision, ImportUpgradeDecisionKind
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.exception.exceptions import TransferException
from app.services.domain.library.service import library_service
from app.services.domain.resource.quality import (
    compare_resource_attributes,
    has_any_resource_attributes,
    has_comparable_resource_attributes,
    resource_attributes_match,
)


logger = logging.getLogger("app.services.transfer")


class ImportUpgradePolicy:
    def decide(self, existing_file: LibraryFile, incoming_result: TransferFileResult) -> ImportUpgradeDecision:
        existing_attrs = existing_file.resource_attributes or ResourceAttributes()
        incoming_attrs = incoming_result.file_item.attrs or ResourceAttributes()

        comparison = compare_resource_attributes(existing_attrs, incoming_attrs)
        if comparison is not None:
            dimension, direction = comparison
            if direction > 0:
                return ImportUpgradeDecision(
                    kind=ImportUpgradeDecisionKind.BETTER,
                    reason=f"incoming {dimension} outranks existing file",
                    dimension=dimension,
                )
            return ImportUpgradeDecision(
                kind=ImportUpgradeDecisionKind.NOT_BETTER,
                reason=f"incoming {dimension} is worse than existing file",
                dimension=dimension,
            )

        if existing_file.file_size and incoming_result.file_item.size:
            if incoming_result.file_item.size > existing_file.file_size:
                return ImportUpgradeDecision(kind=ImportUpgradeDecisionKind.BETTER, reason="incoming file is larger than existing file", dimension="file_size")
            if incoming_result.file_item.size < existing_file.file_size:
                return ImportUpgradeDecision(kind=ImportUpgradeDecisionKind.NOT_BETTER, reason="incoming file is smaller than existing file", dimension="file_size")

        return ImportUpgradeDecision(kind=ImportUpgradeDecisionKind.UNKNOWN, reason="unable to determine whether incoming file is an upgrade")


import_upgrade_policy = ImportUpgradePolicy()


def is_idempotent_transfer_retry(task: TaskData, existing_file: LibraryFile, transfer_result: TransferFileResult) -> bool:
    if existing_file.task_id != task.id:
        return False
    existing_size = existing_file.file_size
    incoming_size = transfer_result.file_item.size
    if existing_size is not None and incoming_size is not None and existing_size != incoming_size:
        return False
    existing_attrs = existing_file.resource_attributes
    incoming_attrs = transfer_result.file_item.attrs or ResourceAttributes()
    if resource_attributes_match(existing_attrs, incoming_attrs):
        return True
    if not has_comparable_resource_attributes(existing_attrs, incoming_attrs):
        return True
    return not has_any_resource_attributes(existing_attrs) or not has_any_resource_attributes(incoming_attrs)


def _is_original_disc_transfer(transfer_result: TransferFileResult) -> bool:
    attrs = transfer_result.file_item.attrs
    return bool(attrs and attrs.package_layout)


async def validate_transfer_upgrade_policy(task: TaskData, transfer_results: list[TransferFileResult]) -> None:
    for transfer_result in transfer_results:
        existing_file = await library_service.find_file_by_path(transfer_result.destination_path)
        if not existing_file:
            continue
        if is_idempotent_transfer_retry(task, existing_file, transfer_result):
            continue
        if _is_original_disc_transfer(transfer_result):
            raise TransferException("backendErrors.transferDiscFileConflict")
        decision = import_upgrade_policy.decide(existing_file, transfer_result)
        logger.info(
            "Transfer path collision evaluated: task=%s media=%s path=%s decision=%s dimension=%s",
            task.id,
            task.media_id,
            transfer_result.destination_path,
            decision.kind.value,
            decision.dimension,
        )
        if decision.kind == ImportUpgradeDecisionKind.BETTER:
            continue
        if decision.kind == ImportUpgradeDecisionKind.NOT_BETTER:
            raise TransferException("backendErrors.transferFileNotBetter")
        raise TransferException("backendErrors.transferFileUpgradeUnknown")
