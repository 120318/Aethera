import logging

from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_search import MediaSearchQuery, Resource, ResourceSearchResult
from app.services.domain.resource.filtering import match_season
from app.services.domain.resource.parser import resource_parser

logger = logging.getLogger("app.services.domain.resource.search_policy")


class ResourceSearchResultPolicy:
    def result_identity_key(self, result: ResourceSearchResult) -> str:
        parts = (
            str(result.indexer_id or "").strip().lower(),
            str(result.site or "").strip().lower(),
            str(result.title or "").strip().lower(),
            str(result.size or ""),
            str(result.publish_date or ""),
        )
        return "|".join(parts)

    def merge_results(self, *result_groups: list[ResourceSearchResult] | None) -> list[ResourceSearchResult]:
        merged_by_identity: dict[str, ResourceSearchResult] = {}
        ordered_results: list[ResourceSearchResult] = []
        for group in result_groups:
            if not group:
                continue
            for result in group:
                key = self.result_identity_key(result)
                existing = merged_by_identity[key] if key in merged_by_identity else None
                if existing is None:
                    copied = result.model_copy(deep=True)
                    merged_by_identity[key] = copied
                    ordered_results.append(copied)
                    continue
                self._merge_duplicate_result(existing, result)
        return ordered_results

    def filter_media_results(
        self,
        results: list[ResourceSearchResult],
        query: MediaSearchQuery,
    ) -> list[ResourceSearchResult]:
        filtered: list[ResourceSearchResult] = []
        for result in results:
            matched = self.match_result_to_query(result, query)
            if matched is not None:
                filtered.append(matched)
        return filtered

    def filter_results_for_active_season(
        self,
        results: list[ResourceSearchResult],
        query: MediaSearchQuery,
    ) -> list[ResourceSearchResult]:
        if query.media_type != MediaType.tv or query.season_number is None:
            return results
        filtered: list[ResourceSearchResult] = []
        for result in results:
            attrs = resource_parser.parse(result.title, desc=result.description)
            if match_season(Resource(resources=result, attrs=attrs), query.season_number):
                filtered.append(result)
        logger.debug(
            "Resource search season filter: media_id=%s season_number=%s before=%s after=%s",
            str(query.media_id),
            query.season_number,
            len(results),
            len(filtered),
        )
        return filtered

    def resolve_match_source(self, result: ResourceSearchResult, query: MediaSearchQuery) -> str:
        expected_douban_id = self.expected_douban_id(query)
        expected_imdb_id = self.normalize_external_id(query.imdbid)
        result_douban_id = self.normalize_external_id(result.source_doubanid)
        result_imdb_id = self.normalize_external_id(result.source_imdbid)
        if result_douban_id and expected_douban_id and result_douban_id == expected_douban_id:
            return "doubanid"
        if result_imdb_id and expected_imdb_id and result_imdb_id == expected_imdb_id:
            return "imdbid"
        return "q"

    def match_result_to_query(
        self,
        result: ResourceSearchResult,
        query: MediaSearchQuery,
    ) -> ResourceSearchResult | None:
        if result.matched_by_id:
            return result.model_copy(update={"matched_by_id": True})

        expected_douban_id = self.expected_douban_id(query)
        expected_imdb_id = self.normalize_external_id(query.imdbid)
        result_douban_id = self.normalize_external_id(result.source_doubanid)
        result_imdb_id = self.normalize_external_id(result.source_imdbid)

        matched_by_id = False
        has_id_mismatch = False

        if result_douban_id and expected_douban_id and result_douban_id == expected_douban_id:
            matched_by_id = True
        if result_imdb_id and expected_imdb_id and result_imdb_id == expected_imdb_id:
            matched_by_id = True
        if result_douban_id and expected_douban_id and result_douban_id != expected_douban_id:
            has_id_mismatch = True
        if result_imdb_id and expected_imdb_id and result_imdb_id != expected_imdb_id:
            has_id_mismatch = True

        if has_id_mismatch and not matched_by_id:
            logger.debug(
                "Resource search result filtered by ID mismatch: site=%s title=%s expected_media_id=%s expected_imdbid=%s result_doubanid=%s result_imdbid=%s detail_url=%s",
                result.site,
                result.title,
                query.media_id.id,
                query.imdbid,
                result.source_doubanid,
                result.source_imdbid,
                result.detail_url,
            )
            return None

        if matched_by_id:
            return result.model_copy(update={"matched_by_id": True})
        return result.model_copy(update={"matched_by_id": False})

    def expected_douban_id(self, query: MediaSearchQuery) -> str | None:
        value = query.douban_id or (query.media_id.id if query.media_id.provider.value == "douban" else None)
        return self.normalize_external_id(value)

    def normalize_external_id(self, value: str | None) -> str | None:
        normalized = str(value or "").strip()
        if not normalized:
            return None
        return normalized.lower()

    def _merge_duplicate_result(self, existing: ResourceSearchResult, result: ResourceSearchResult) -> None:
        if result.matched_by_id and not existing.matched_by_id:
            existing.id = result.id
            existing.title = result.title
            existing.description = result.description
            existing.site = result.site
            existing.site_name = result.site_name
            existing.indexer_id = result.indexer_id
            existing.indexer_name = result.indexer_name
            existing.indexer_type = result.indexer_type
            existing.category = result.category
            existing.size = result.size
            existing.seeders = result.seeders
            existing.leechers = result.leechers
            existing.publish_date = result.publish_date
            existing.torrent_url = result.torrent_url
            existing.download_url = result.download_url
            existing.detail_url = result.detail_url
            existing.result_id = result.result_id
            existing.download_volume_factor = result.download_volume_factor
            existing.upload_volume_factor = result.upload_volume_factor
            existing.source_imdbid = result.source_imdbid
            existing.source_doubanid = result.source_doubanid
            existing.matched_by_id = result.matched_by_id
            return
        if not existing.source_imdbid and result.source_imdbid:
            existing.source_imdbid = result.source_imdbid
        if not existing.source_doubanid and result.source_doubanid:
            existing.source_doubanid = result.source_doubanid
        if not existing.site_name and result.site_name:
            existing.site_name = result.site_name
        if not existing.indexer_id and result.indexer_id:
            existing.indexer_id = result.indexer_id
        if not existing.indexer_name and result.indexer_name:
            existing.indexer_name = result.indexer_name
        if not existing.indexer_type and result.indexer_type:
            existing.indexer_type = result.indexer_type
        if result.matched_by_id:
            existing.matched_by_id = True


resource_search_result_policy = ResourceSearchResultPolicy()
