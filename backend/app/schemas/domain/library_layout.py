from __future__ import annotations

from pydantic import BaseModel, Field


class LibraryLayoutTargetFile(BaseModel):
    destination_path: str
    episode_number: int | None = None


class LibraryLayoutDecision(BaseModel):
    anchor_file: str | None = None
    media_root_dir: str | None = None
    updated_paths: list[str] = Field(default_factory=list)
    target_files: list[LibraryLayoutTargetFile] = Field(default_factory=list)
