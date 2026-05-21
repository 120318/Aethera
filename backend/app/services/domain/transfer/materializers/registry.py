from __future__ import annotations

from app.schemas.config import TransferMode
from app.schemas.exception.exceptions import TransferException

from .copy import copy_materializer
from .hardlink import hardlink_materializer
from .interface import TransferMaterializer


class TransferMaterializerRegistry:
    def __init__(self) -> None:
        self._materializers: dict[TransferMode, TransferMaterializer] = {
            copy_materializer.mode: copy_materializer,
            hardlink_materializer.mode: hardlink_materializer,
        }

    def resolve(self, transfer_mode: TransferMode) -> TransferMaterializer:
        materializer = self._materializers[transfer_mode] if transfer_mode in self._materializers else None
        if materializer is None:
            raise TransferException("backendErrors.transferModeUnsupported", params={"mode": transfer_mode.value})
        return materializer

    def supports(self, transfer_mode: TransferMode) -> bool:
        return transfer_mode in self._materializers


transfer_materializer_registry = TransferMaterializerRegistry()
