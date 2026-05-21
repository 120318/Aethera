from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.config import TransferMode


class TransferMaterializer(ABC):
    @property
    @abstractmethod
    def mode(self) -> TransferMode:
        pass

    @abstractmethod
    def materialize(self, source_path: Path, destination_path: Path) -> None:
        pass
