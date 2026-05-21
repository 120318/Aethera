import hashlib
import logging
import time

from pydantic import ValidationError

from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.media_id import MediaID
from app.schemas.runtime.indexer_runtime import (
    CachedIndexerResultPayload,
    CachedIndexerSearchPayload,
    CachedIndexerSearchRecord,
)
from app.services.config.settings_service import settings_service
from app.services.domain.resource.search_policy import resource_search_result_policy
from app.services.platform.runtime_cache import runtime_cache

logger = logging.getLogger("app.services.application.workflows.resource_search.cache")


class ResourceSearchCache:
    def __init__(self) -> None:
        self._cache_ttl: int | None = None
        self._empty_cache_ttl = 60
        self._error_cache_ttl = 60
        self._result_ttl: int | None = None
        self.refresh_ttls()

    def refresh_ttls(self) -> None:
        cache_config = settings_service.get_base_system_config().cache
        self._cache_ttl = self._resolve_result_cache_ttl(cache_config.search_result_expire_seconds)
        self._empty_cache_ttl = self._resolve_optional_cache_ttl(cache_config.search_empty_expire_seconds)
        self._error_cache_ttl = self._resolve_optional_cache_ttl(cache_config.search_error_expire_seconds)
        self._result_ttl = self._resolve_result_cache_ttl(cache_config.search_result_expire_seconds)

    def media_site_cache_key(
        self,
        media_id: MediaID,
        indexer_id: str,
        site_id: str,
        cache_scope: str,
        season_number: int | None = None,
        query_scope: str | None = None,
    ) -> str:
        season_suffix = f":season:{season_number}" if season_number is not None and season_number > 0 else ""
        query_suffix = f":queries:{query_scope}" if query_scope else ""
        return self.generate_cache_key(
            f"ids:{str(media_id)}{season_suffix}{query_suffix}",
            indexer_id=f"{indexer_id}:{site_id}:{cache_scope}",
        )

    def generate_cache_key(
        self,
        query: str,
        category: str | None = None,
        indexers: list[str] | None = None,
        indexer_id: str | None = None,
    ) -> str:
        key_parts = [f"query:{query}"]
        if category:
            key_parts.append(f"category:{category}")
        if indexers:
            key_parts.append(f"indexers:{','.join(sorted(indexers))}")
        if indexer_id:
            key_parts.append(f"indexer_id:{indexer_id}")
        return "|".join(key_parts)

    def get_by_result_id(self, result_id: str) -> ResourceSearchResult | None:
        payload = runtime_cache.read(self.result_storage_key(result_id))
        if payload:
            return CachedIndexerResultPayload.model_validate(payload).result
        return None

    def get_search_results(self, key: str, *, allow_error: bool = False) -> list[ResourceSearchResult] | None:
        try:
            payload = runtime_cache.read(self.search_storage_key(key))
            if payload is None:
                return None
            return self._decode_cached_search_payload(key, payload, allow_error=allow_error)
        except (ValidationError, TypeError, ValueError) as e:
            logger.error("Error reading from cache for key %s: %s", key, e)
        return None

    def has_cached_results(self, key: str) -> bool:
        return runtime_cache.has(self.search_storage_key(key))

    def cache_media_results_for_site(
        self,
        media_id: MediaID,
        indexer_id: str,
        site_id: str,
        cache_scope: str,
        results: list[ResourceSearchResult],
        season_number: int | None = None,
        query_scope: str | None = None,
    ) -> None:
        cache_key = self.media_site_cache_key(media_id, indexer_id, site_id, cache_scope, season_number, query_scope)
        self.save_results(results)
        if results:
            self.save_search_results(cache_key, results, status="ok", ttl=self._cache_ttl)
            return
        self.save_search_results(cache_key, results, status="empty", ttl=self._empty_cache_ttl)

    def cache_media_search_error_for_site(
        self,
        media_id: MediaID,
        indexer_id: str,
        site_id: str,
        cache_scope: str,
        error: str,
        season_number: int | None = None,
        query_scope: str | None = None,
    ) -> None:
        cache_key = self.media_site_cache_key(media_id, indexer_id, site_id, cache_scope, season_number, query_scope)
        self.save_search_results(cache_key, [], status="error", error=error, ttl=self._error_cache_ttl)

    def cache_latest_media_results(
        self,
        media_id: MediaID,
        results: list[ResourceSearchResult],
        season_number: int | None = None,
        search_duration_seconds: float | None = None,
    ) -> None:
        normalized_results = self.normalize_results(results)
        self.save_results(normalized_results)
        payload = CachedIndexerSearchPayload(
            status="ok" if normalized_results else "empty",
            result_ids=[result.result_id for result in normalized_results],
            results=normalized_results,
            error=None,
            updated_at=time.time(),
            search_duration_seconds=search_duration_seconds,
        )
        runtime_cache.set(self.latest_media_storage_key(media_id, season_number), payload, None)

    def get_latest_media_cache_payload(
        self,
        media_id: MediaID,
        season_number: int | None = None,
    ) -> CachedIndexerSearchPayload | None:
        latest_payload = runtime_cache.read(self.latest_media_storage_key(media_id, season_number))
        if latest_payload is None:
            return None
        try:
            return CachedIndexerSearchPayload.model_validate(latest_payload)
        except (ValidationError, TypeError, ValueError) as e:
            logger.error("Error reading latest media cache metadata for %s: %s", media_id, e)
            return None

    def get_latest_media_cached_results(
        self,
        media_id: MediaID,
        season_number: int | None = None,
    ) -> list[ResourceSearchResult] | None:
        cached = self.get_latest_media_cache_payload(media_id, season_number)
        if cached is not None:
            results = self.get_results_by_result_ids(cached.result_ids) if cached.result_ids else []
            if results and len(results) >= len(cached.result_ids):
                return results
            fallback_results = cached.results
            if not fallback_results:
                return results
            normalized_results = self.normalize_results(fallback_results)
            self.save_results(normalized_results)
            return normalized_results

        records = self._find_latest_media_cache_records(media_id)
        if not records:
            return None
        records_by_key: dict[str, CachedIndexerSearchRecord] = {}
        for record in records:
            existing = records_by_key[record.key] if record.key in records_by_key else None
            if existing is None or record.updated_at > existing.updated_at:
                records_by_key[record.key] = record
        record_results = [
            self.get_results_by_result_ids(record.result_ids) if record.result_ids else record.results
            for record in records_by_key.values()
        ]
        merged_results = resource_search_result_policy.merge_results(*record_results)
        normalized_results = self.normalize_results(merged_results)
        self.save_results(normalized_results)
        return normalized_results

    def save_search_results(
        self,
        key: str,
        results: list[ResourceSearchResult],
        *,
        status: str = "ok",
        error: str | None = None,
        ttl: int | None = None,
    ) -> None:
        effective_ttl = self._cache_ttl if ttl is None else ttl
        if effective_ttl is not None and effective_ttl <= 0:
            runtime_cache.delete(self.search_storage_key(key))
            return
        normalized_results = self.normalize_results(results)
        self.save_results(normalized_results)
        payload = CachedIndexerSearchPayload(
            status=status,
            result_ids=[result.result_id for result in normalized_results],
            error=error,
            updated_at=time.time(),
        )
        runtime_cache.set(self.search_storage_key(key), payload, effective_ttl)

    def save_results(self, results: list[ResourceSearchResult]) -> None:
        if not results:
            return
        for result_id, payload in [self._to_result_store_record(result) for result in results]:
            runtime_cache.set(self.result_storage_key(result_id), payload, self._result_ttl)

    def get_results_by_result_ids(self, result_ids: list[str]) -> list[ResourceSearchResult]:
        results: list[ResourceSearchResult] = []
        seen: set[str] = set()
        for result_id in result_ids:
            if not result_id or result_id in seen:
                continue
            seen.add(result_id)
            result = self.get_by_result_id(result_id)
            if result is not None:
                results.append(result)
        return results

    def normalize_results(self, results: list[ResourceSearchResult]) -> list[ResourceSearchResult]:
        normalized: list[ResourceSearchResult] = []
        for result in results:
            item = result.model_copy(deep=True)
            item.result_id = self.stable_result_id(result)
            item.description = item.description or ""
            normalized.append(item)
        return normalized

    def stable_result_id(self, result: ResourceSearchResult) -> str:
        source_key = result.detail_url or result.download_url or result.torrent_url or resource_search_result_policy.result_identity_key(result)
        key = "|".join((
            str(result.indexer_id or "").strip().lower(),
            str(result.site or "").strip().lower(),
            source_key,
        ))
        return hashlib.sha1(key.encode("utf-8", errors="ignore")).hexdigest()

    def search_storage_key(self, key: str) -> str:
        return f"indexer:search:{key}"

    def result_storage_key(self, result_id: str) -> str:
        return f"indexer:result:{result_id}"

    def latest_media_storage_key(self, media_id: MediaID, season_number: int | None = None) -> str:
        suffix = f":season:{season_number}" if season_number is not None and season_number > 0 else ""
        return f"indexer:latest_media:{str(media_id)}{suffix}"

    def _to_result_store_record(self, result: ResourceSearchResult) -> tuple[str, CachedIndexerResultPayload]:
        stored = result.model_copy(deep=True)
        stored.result_id = self.stable_result_id(result)
        return stored.result_id, CachedIndexerResultPayload(result=stored)

    def _decode_cached_search_payload(
        self,
        key: str,
        payload,
        *,
        allow_error: bool = False,
    ) -> list[ResourceSearchResult] | None:
        cached = CachedIndexerSearchPayload.model_validate(payload)
        if cached.status == "error":
            if not allow_error:
                return None
            logger.warning("Indexer search error cache hit: key=%s error=%s", key, cached.error or "unknown error")
            return []
        if cached.result_ids:
            results = self.get_results_by_result_ids(cached.result_ids)
            expected_count = len({result_id for result_id in cached.result_ids if result_id})
            if len(results) >= expected_count:
                return results
            if cached.results:
                normalized_results = self.normalize_results(cached.results)
                self.save_results(normalized_results)
                return normalized_results
            logger.warning(
                "Indexer search cache detail miss: key=%s expected=%d resolved=%d",
                key,
                expected_count,
                len(results),
            )
            return None
        normalized_results = self.normalize_results(cached.results)
        self.save_results(normalized_results)
        return normalized_results

    def _find_latest_media_cache_records(self, media_id: MediaID) -> list[CachedIndexerSearchRecord]:
        key_prefix = self.search_storage_key(f"query:ids:{str(media_id)}|indexer_id:")
        try:
            records = runtime_cache.items_by_prefix(key_prefix)
            if not records:
                return []
            parsed_records = [
                CachedIndexerSearchRecord(
                    key=key,
                    status=payload.status,
                    result_ids=payload.result_ids,
                    results=payload.results,
                    error=payload.error,
                    updated_at=payload.updated_at,
                )
                for key, value in records
                if (payload := CachedIndexerSearchPayload.model_validate(value))
            ]
            return [record for record in parsed_records if record.status in {"ok", "empty"}]
        except (ValidationError, TypeError, ValueError) as e:
            logger.error("Error reading latest media cache for %s: %s", media_id, e)
            return []

    def _resolve_result_cache_ttl(self, cache_ttl: int | None) -> int | None:
        try:
            ttl = int(cache_ttl)
        except (TypeError, ValueError):
            return None
        if ttl == 0:
            return None
        return ttl if ttl > 0 else None

    def _resolve_optional_cache_ttl(self, cache_ttl: int | None, default: int = 60) -> int:
        try:
            ttl = int(cache_ttl)
        except (TypeError, ValueError):
            return default
        return ttl if ttl >= 0 else default
