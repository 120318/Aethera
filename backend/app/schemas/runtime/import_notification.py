from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.domain.addon_events import MediaImportCompletedEventMeta


class ImportStepStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


class ImportNotificationStep(BaseModel):
    name: str
    status: ImportStepStatus
    completed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0


class ImportNotificationMeta(MediaImportCompletedEventMeta):
    postprocessing: list[ImportNotificationStep] = Field(default_factory=list)
