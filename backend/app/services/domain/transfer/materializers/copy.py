from __future__ import annotations

from pathlib import Path

from app.schemas.config import TransferMode
from app.schemas.exception.exceptions import TransferException
from app.utils.fs_utils import fs_provider

from .interface import TransferMaterializer


class CopyMaterializer(TransferMaterializer):
    @property
    def mode(self) -> TransferMode:
        return TransferMode.COPY

    def materialize(self, source_path: Path, destination_path: Path) -> None:
        fs_provider.mkdir(destination_path.parent)
        success = fs_provider.copy(source_path, destination_path)
        if not success:
            raise TransferException(
                "backendErrors.transferCopyFailed",
                params={"source": str(source_path), "destination": str(destination_path)},
            )


copy_materializer = CopyMaterializer()
