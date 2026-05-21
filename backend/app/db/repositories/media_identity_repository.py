from __future__ import annotations

import json
import re
import time
from typing import Any

from sqlalchemy import text

from app.db.sql.session import SessionLocal
from app.schemas.media_id import MediaID, Provider


class MediaIdentityRepository:
    def merge_media_id(self, source_media_id: MediaID, target_media_id: MediaID) -> None:
        if source_media_id == target_media_id:
            return

        source = str(source_media_id)
        target = str(target_media_id)
        target_provider = target_media_id.provider.value
        target_provider_item_id = target_media_id.id

        with SessionLocal.begin() as session:
            self._replace_embedded_media_refs(session, source_media_id, target_media_id)
            self._merge_singleton_rows(session, source, target)
            self._merge_subscription_settings(session, source, target)
            self._merge_metadata_sync(session, source, target)

            for table in (
                "library_files",
                "library_episodes",
                "actions",
                "events",
                "media_subscription_cycles",
            ):
                session.execute(text(f"UPDATE {table} SET media_id = :target WHERE media_id = :source"), {"source": source, "target": target})

            session.execute(
                text(
                    """
                    UPDATE tasks
                    SET media_id = :target,
                        provider = :provider,
                        provider_item_id = :provider_item_id
                    WHERE media_id = :source
                    """
                ),
                {
                    "source": source,
                    "target": target,
                    "provider": target_provider,
                    "provider_item_id": target_provider_item_id,
                },
            )
            session.execute(
                text(
                    """
                    UPDATE commands
                    SET media_id = :target,
                        target_id = CASE WHEN target_type = 'media' AND target_id = :source THEN :target ELSE target_id END
                    WHERE media_id = :source OR (target_type = 'media' AND target_id = :source)
                    """
                ),
                {"source": source, "target": target},
            )

            self._retarget_source_mapping(session, source_media_id, target_media_id)
            session.execute(
                text(
                    """
                    UPDATE media_external_mappings
                    SET media_id = :target,
                        tmdb_id = CASE WHEN :target_provider = 'tmdb' THEN :target_tmdb_id ELSE tmdb_id END
                    WHERE media_id = :source
                    """
                ),
                {
                    "source": source,
                    "target": target,
                    "target_provider": target_provider,
                    "target_tmdb_id": int(target_media_id.id) if target_media_id.provider == Provider.tmdb else None,
                },
            )

    def _retarget_source_mapping(self, session, source_media_id: MediaID, target_media_id: MediaID) -> None:
        target_tmdb_id = int(target_media_id.id) if target_media_id.provider == Provider.tmdb else None
        session.execute(
            text(
                """
                UPDATE media_external_mappings
                SET media_id = :target,
                    tmdb_id = CASE WHEN :target_tmdb_id IS NOT NULL THEN :target_tmdb_id ELSE tmdb_id END,
                    updated_at = :updated_at
                WHERE source = :source_provider
                  AND source_id = :source_provider_item_id
                  AND media_type = :media_type
                """
            ),
            {
                "target": str(target_media_id),
                "target_tmdb_id": target_tmdb_id,
                "updated_at": time.time(),
                "source_provider": source_media_id.provider.value,
                "source_provider_item_id": source_media_id.id,
                "media_type": source_media_id.media_type.value,
            },
        )

    def _merge_singleton_rows(self, session, source: str, target: str) -> None:
        for table in ("library_meta", "managed_media_profiles"):
            target_exists = session.execute(
                text(f"SELECT 1 FROM {table} WHERE media_id = :target LIMIT 1"),
                {"target": target},
            ).first()
            if target_exists:
                session.execute(text(f"DELETE FROM {table} WHERE media_id = :source"), {"source": source})
                continue
            session.execute(text(f"UPDATE {table} SET media_id = :target WHERE media_id = :source"), {"source": source, "target": target})

    def _merge_subscription_settings(self, session, source: str, target: str) -> None:
        session.execute(
            text(
                """
                DELETE FROM media_subscription_settings
                WHERE media_id = :source
                  AND EXISTS (
                    SELECT 1
                    FROM media_subscription_settings target_rows
                    WHERE target_rows.media_id = :target
                      AND target_rows.season_number = media_subscription_settings.season_number
                  )
                """
            ),
            {"source": source, "target": target},
        )
        session.execute(
            text("UPDATE media_subscription_settings SET media_id = :target WHERE media_id = :source"),
            {"source": source, "target": target},
        )

    def _merge_metadata_sync(self, session, source: str, target: str) -> None:
        session.execute(
            text(
                """
                DELETE FROM metadata_sync
                WHERE media_id = :source
                  AND EXISTS (
                    SELECT 1
                    FROM metadata_sync target_rows
                    WHERE target_rows.media_id = :target
                      AND target_rows.media_server_id = metadata_sync.media_server_id
                  )
                """
            ),
            {"source": source, "target": target},
        )
        session.execute(
            text("UPDATE metadata_sync SET media_id = :target WHERE media_id = :source"),
            {"source": source, "target": target},
        )

    def _replace_embedded_media_refs(self, session, source_media_id: MediaID, target_media_id: MediaID) -> None:
        source = str(source_media_id)
        target = str(target_media_id)
        json_replacements = [
            ("tasks", ("context_json", "metadata_json", "error_params_json")),
            ("actions", ("meta_json", "message_params_json")),
            ("events", ("entities_json", "meta_json", "message_params_json")),
            ("commands", ("payload_json", "result_json", "message_params_json", "error_params_json")),
            ("media_subscription_settings", ("media_json", "upgrade_policy_json", "target_filters_json", "filters_json", "sites_json", "unmatched_rules_json")),
            ("media_subscription_cycles", ("warnings_json", "completion_snapshot_json")),
        ]
        for table, columns in json_replacements:
            for column in columns:
                self._replace_json_media_refs(session, table, column, source_media_id, target_media_id)

        for table in ("actions", "events"):
            self._replace_text_media_refs(session, table, "search_text", source, target)

    def _replace_json_media_refs(
        self,
        session,
        table: str,
        column: str,
        source_media_id: MediaID,
        target_media_id: MediaID,
    ) -> None:
        source = str(source_media_id)
        target = str(target_media_id)
        rows = session.execute(
            text(f"SELECT rowid, {column} FROM {table} WHERE {column} LIKE :source"),
            {"source": f"%{source}%"},
        ).all()
        for rowid, raw_value in rows:
            parsed = self._loads_json_value(raw_value)
            if parsed is _INVALID_JSON:
                continue
            replaced = self._replace_json_value(parsed, source_media_id, target_media_id)
            if replaced == parsed:
                continue
            session.execute(
                text(f"UPDATE {table} SET {column} = :value WHERE rowid = :rowid"),
                {"rowid": rowid, "value": json.dumps(replaced, ensure_ascii=False, separators=(",", ":"))},
            )

    def _replace_text_media_refs(self, session, table: str, column: str, source: str, target: str) -> None:
        pattern = re.compile(rf"(?<![A-Za-z0-9:_-]){re.escape(source)}(?![A-Za-z0-9:_-])")
        rows = session.execute(
            text(f"SELECT rowid, {column} FROM {table} WHERE {column} LIKE :source"),
            {"source": f"%{source}%"},
        ).all()
        for rowid, value in rows:
            if not isinstance(value, str):
                continue
            replaced = pattern.sub(target, value)
            if replaced == value:
                continue
            session.execute(
                text(f"UPDATE {table} SET {column} = :value WHERE rowid = :rowid"),
                {"rowid": rowid, "value": replaced},
            )

    @staticmethod
    def _loads_json_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return _INVALID_JSON
        return value

    def _replace_json_value(self, value: Any, source_media_id: MediaID, target_media_id: MediaID) -> Any:
        source = str(source_media_id)
        target = str(target_media_id)
        if isinstance(value, str):
            return target if value == source else value
        if isinstance(value, list):
            return [self._replace_json_value(item, source_media_id, target_media_id) for item in value]
        if isinstance(value, dict):
            references_source = self._dict_references_source_media(value, source_media_id)
            replaced = {key: self._replace_json_value(item, source_media_id, target_media_id) for key, item in value.items()}
            if references_source:
                replaced = self._replace_tmdb_id_fields(replaced, source_media_id, target_media_id)
            return replaced
        return value

    @staticmethod
    def _dict_references_source_media(value: dict[str, Any], source_media_id: MediaID) -> bool:
        source = str(source_media_id)
        return any(item == source for item in value.values())

    @staticmethod
    def _replace_tmdb_id_fields(
        value: dict[str, Any],
        source_media_id: MediaID,
        target_media_id: MediaID,
    ) -> dict[str, Any]:
        if source_media_id.provider != Provider.tmdb or target_media_id.provider != Provider.tmdb:
            return value
        source_tmdb_id = int(source_media_id.id)
        target_tmdb_id = int(target_media_id.id)
        for key, item in list(value.items()):
            if key == "tmdb_id" and item == source_tmdb_id:
                value[key] = target_tmdb_id
        return value


_INVALID_JSON = object()


media_identity_repository = MediaIdentityRepository()
