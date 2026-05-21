from __future__ import annotations

from pathlib import Path

from app.schemas.config import TransferMode
from app.schemas.exception.exceptions import TransferException
from app.utils.fs_utils import fs_provider

from .interface import TransferMaterializer


class HardlinkMaterializer(TransferMaterializer):
    @property
    def mode(self) -> TransferMode:
        return TransferMode.HARDLINK

    def materialize(self, source_path: Path, destination_path: Path) -> None:
        if fs_provider.exists(destination_path):
            fs_provider.remove(destination_path)
        fs_provider.mkdir(destination_path.parent)
        success = fs_provider.hardlink(source_path, destination_path)
        if not success:
            raise TransferException(
                "backendErrors.transferHardlinkFailed",
                params={"source": str(source_path), "destination": str(destination_path)},
            )


hardlink_materializer = HardlinkMaterializer()
