from __future__ import annotations

import uuid

from app.db.repositories.settings_sqlite_repository import SettingsSqliteRepository
from app.schemas.config import Tag
from app.services.config.default_tags import DEFAULT_TAG_SEED_KEY, DEFAULT_TAGS


class TagSettings:
    def __init__(self, repo: SettingsSqliteRepository) -> None:
        self._repo = repo

    def list(self) -> list[Tag]:
        return self._repo.tags.list()

    def ensure_defaults(self) -> None:
        if self._repo.get_default(DEFAULT_TAG_SEED_KEY) == "1":
            return
        existing = self.list()
        existing_names = {tag.name.strip() for tag in existing if tag.name.strip()}
        next_tags = list(existing)
        next_tags.extend(tag for tag in DEFAULT_TAGS if tag.name not in existing_names)
        self.replace_all(next_tags)
        self._repo.set_default(DEFAULT_TAG_SEED_KEY, "1")

    def replace_all(self, tags: list[Tag]) -> None:
        self._repo.tags.replace(tags)

    def find(self, tag_id: str) -> Tag | None:
        return next((tag for tag in self.list() if tag.id == tag_id), None)

    def create(
        self,
        name: str,
        include_keywords: list[str] | None = None,
        exclude_keywords: list[str] | None = None,
        regex: str | None = None,
    ) -> Tag:
        tags = self.list()
        tag = Tag(
            id=str(uuid.uuid4()),
            name=name,
            include_keywords=include_keywords or [],
            exclude_keywords=exclude_keywords or [],
            regex=regex or "",
        )
        tags.append(tag)
        self.replace_all(tags)
        return tag

    def update(
        self,
        tag_id: str,
        name: str | None = None,
        include_keywords: list[str] | None = None,
        exclude_keywords: list[str] | None = None,
        regex: str | None = None,
    ) -> Tag | None:
        tags = self.list()
        for index, tag in enumerate(tags):
            if tag.id != tag_id:
                continue
            updated = tag.model_copy(
                update={
                    "name": name if name is not None else tag.name,
                    "include_keywords": include_keywords if include_keywords is not None else tag.include_keywords,
                    "exclude_keywords": exclude_keywords if exclude_keywords is not None else tag.exclude_keywords,
                    "regex": regex if regex is not None else tag.regex,
                }
            )
            tags[index] = updated
            self.replace_all(tags)
            return updated
        return None

    def delete(self, tag_id: str) -> bool:
        tags = self.list()
        next_tags = [item for item in tags if item.id != tag_id]
        if len(next_tags) == len(tags):
            return False
        self.replace_all(next_tags)
        return True
