from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.orm import DeclarativeBase
from pydantic import TypeAdapter

from app.db.sql.models import (
    ConfigSectionORM,
    TagSettingORM,
    DirectorySettingORM,
    DirectoryIntegrityPolicySettingORM,
    DownloaderSettingORM,
    FilterPresetSettingORM,
    IndexerSettingORM,
    MediaServerSettingORM,
    NamingTemplateSettingORM,
    QualityProfileSettingORM,
    SettingsDefaultORM,
)
from app.db.sql.session import SessionLocal
from app.schemas.config import (
    Tag,
    DirectoryConfig,
    DownloaderProviderConfig,
    IndexerProviderConfig,
    MediaServerProviderConfig,
    NamingTemplateConfig,
)
from app.schemas.domain.filter_config import FilterConfig
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.runtime.directory_integrity import DirectoryIntegrityPolicy

T = TypeVar("T")
ORM = TypeVar("ORM", bound=DeclarativeBase)


class _OrderedPayloadRepository(Generic[T, ORM]):
    def __init__(self, orm_model: type[ORM], model_validate: callable) -> None:
        self.orm_model = orm_model
        self.model_validate = model_validate

    def list(self) -> list[T]:
        with SessionLocal() as session:
            rows = session.execute(
                select(self.orm_model).order_by(self.orm_model.sort_order.asc(), self.orm_model.id.asc())
            ).scalars().all()
            return [self.model_validate(row.payload_json) for row in rows]

    def replace(self, items: list[T]) -> None:
        with SessionLocal() as session:
            existing_ids = {
                row_id
                for row_id, in session.execute(select(self.orm_model.id)).all()
            }
            next_ids = {self._item_id(item) for item in items}
            for sort_order, item in enumerate(items):
                item_id = self._item_id(item)
                payload = self._dump(item)
                if item_id in existing_ids:
                    session.execute(
                        update(self.orm_model)
                        .where(self.orm_model.id == item_id)
                        .values(sort_order=sort_order, payload_json=payload)
                    )
                else:
                    session.add(
                        self.orm_model(
                            id=item_id,
                            sort_order=sort_order,
                            payload_json=payload,
                        )
                    )
            stale_ids = existing_ids - next_ids
            if stale_ids:
                session.execute(delete(self.orm_model).where(self.orm_model.id.in_(stale_ids)))
            session.commit()

    def _item_id(self, item: T) -> str:
        return str(getattr(item, "id"))

    def _dump(self, item: T):
        return item.model_dump(mode="json")


class _DirectoryIntegrityPolicyRepository(_OrderedPayloadRepository[DirectoryIntegrityPolicy, DirectoryIntegrityPolicySettingORM]):
    def _item_id(self, item: DirectoryIntegrityPolicy) -> str:
        return item.directory_id


class SettingsSqliteRepository:
    def __init__(self) -> None:
        downloader_adapter = TypeAdapter(DownloaderProviderConfig)
        indexer_adapter = TypeAdapter(IndexerProviderConfig)
        media_server_adapter = TypeAdapter(MediaServerProviderConfig)
        naming_template_adapter = TypeAdapter(NamingTemplateConfig)
        self.downloaders = _OrderedPayloadRepository(DownloaderSettingORM, downloader_adapter.validate_python)
        self.directories = _OrderedPayloadRepository(DirectorySettingORM, DirectoryConfig.model_validate)
        self.indexers = _OrderedPayloadRepository(IndexerSettingORM, indexer_adapter.validate_python)
        self.media_servers = _OrderedPayloadRepository(MediaServerSettingORM, media_server_adapter.validate_python)
        self.naming_templates = _OrderedPayloadRepository(NamingTemplateSettingORM, naming_template_adapter.validate_python)
        self.filter_presets = _OrderedPayloadRepository(FilterPresetSettingORM, FilterConfig.model_validate)
        self.quality_profiles = _OrderedPayloadRepository(QualityProfileSettingORM, QualityProfile.model_validate)
        self.tags = _OrderedPayloadRepository(TagSettingORM, Tag.model_validate)
        self.directory_integrity_policies = _DirectoryIntegrityPolicyRepository(
            DirectoryIntegrityPolicySettingORM,
            DirectoryIntegrityPolicy.model_validate,
        )

    def get_default(self, key: str) -> str | None:
        with SessionLocal() as session:
            row = session.get(SettingsDefaultORM, key)
            return row.value_text if row else None

    def set_default(self, key: str, value: str | None) -> None:
        with SessionLocal() as session:
            row = session.get(SettingsDefaultORM, key)
            if row is None:
                session.add(SettingsDefaultORM(key=key, value_text=value))
            else:
                row.value_text = value
            session.commit()

    def get_section(self, section: str):
        with SessionLocal() as session:
            row = session.get(ConfigSectionORM, section)
            return row.payload_json if row else None

    def set_section(self, section: str, payload) -> None:
        with SessionLocal() as session:
            row = session.get(ConfigSectionORM, section)
            if row is None:
                session.add(ConfigSectionORM(section=section, payload_json=payload))
            else:
                row.payload_json = payload
            session.commit()

    def replace_sections(self, sections) -> None:
        with SessionLocal() as session:
            for section, payload in sections.items():
                row = session.get(ConfigSectionORM, section)
                if row is None:
                    session.add(ConfigSectionORM(section=section, payload_json=payload))
                else:
                    row.payload_json = payload
            session.commit()
