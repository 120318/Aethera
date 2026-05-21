from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.domain.library import LibraryFile


class ImportUpgradeDecisionKind(str, Enum):
    BETTER = "better"
    NOT_BETTER = "not_better"
    UNKNOWN = "unknown"


class ImportUpgradeDecision(BaseModel):
    kind: ImportUpgradeDecisionKind
    reason: str
    dimension: str | None = None


class LibraryReplacementPlan(BaseModel):
    replace_files: list[LibraryFile] = Field(default_factory=list)
    reason: str = ""

    @property
    def has_replacements(self) -> bool:
        return bool(self.replace_files)
