import logging

from pydantic import BaseModel, Field

from app.schemas.config import Tag
from app.schemas.domain.media import MediaSimpleInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_attributes import ResourceAttributes, ResourceDisplayAttributes
from app.schemas.domain.resource_search import Resource as ParsedResource
from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.schemas.exception import MediaNotFoundException
from app.schemas.exception.exceptions import SearchMissingSeasonInfoException
from app.schemas.media_id import MediaID
from app.services.application.workflows.resource_search import resource_search_service
from app.services.domain.media import media_service
from app.services.domain.resource.filtering import matches_unmatched_rules
from app.services.domain.resource.parser import resource_parser
from app.services.domain.resource.tags import resolve_display_tags
from app.services.config.settings_service import settings_service
from app.services.domain.subscription.download_config_service import subscription_download_config_service

logger = logging.getLogger("app.services.application.views.resource_search")


class Resource(BaseModel):
    resource: ResourceSearchResult = Field(..., description="Field description")
    attributes: ResourceDisplayAttributes = Field(..., description="Field description")


class ResourceSearchResponse(BaseModel):
    media_info: MediaSimpleInfo
    results: list[Resource] | None
    searched_at: float | None = None
    search_duration_seconds: float | None = None


class ResourceSearchResultViewService:
    async def get_latest_results(
        self,
        *,
        media_id: MediaID,
        season_number: int | None,
        site_ids: list[str] | None = None,
    ) -> ResourceSearchResponse:
        media = await media_service.simple_info(media_id)
        if not media:
            raise MediaNotFoundException()
        media = media_service.apply_season_context(media, season_number)

        active_season_number = media.season_number
        if media.media_type == MediaType.tv and active_season_number is None:
            logger.warning("Missing season information: title=%s year=%s", media.title, media.year)
            raise SearchMissingSeasonInfoException()

        results = resource_search_service.get_latest_media_cached_results(
            media_id,
            season_number=active_season_number,
        )
        if results is None:
            return ResourceSearchResponse(media_info=media, results=None)
        searched_at, search_duration_seconds = resource_search_service.get_latest_media_search_metadata(
            media_id,
            season_number=active_season_number,
        )

        if site_ids:
            requested_sites = {item.strip() for item in site_ids if item and item.strip()}
            results = [
                result for result in results
                if (result.site or "").strip() in requested_sites
            ]

        unmatched_rules = await self._resolve_current_unmatched_rules(media_id, active_season_number)
        tags = settings_service.list_tags()
        resources = [
            self._build_resource(result, unmatched_rules, tags=tags)
            for result in results
        ]
        return ResourceSearchResponse(
            media_info=media,
            results=resources,
            searched_at=searched_at,
            search_duration_seconds=search_duration_seconds,
        )

    async def _resolve_current_unmatched_rules(
        self,
        media_id: MediaID,
        season_number: int | None,
    ) -> list[SubscriptionUnmatchedRule]:
        current = await subscription_download_config_service.find_by_media_id(media_id, season_number)
        return list(current.unmatched_rules) if current else []

    def _build_resource(
        self,
        result: ResourceSearchResult,
        unmatched_rules: list[SubscriptionUnmatchedRule],
        *,
        tags: list[Tag],
    ) -> Resource:
        attributes = resource_parser.parse(result.title, desc=result.description)
        display_attributes = self._build_display_attributes(attributes, tags=tags)
        annotated_result = result.model_copy(
            update={
                "matched_unmatched_rule": (
                    result.matched_by_id is False
                    and matches_unmatched_rules(
                        ParsedResource(resources=result, attrs=attributes),
                        unmatched_rules,
                    )
                ),
            }
        )
        return Resource(resource=annotated_result, attributes=display_attributes)

    def _build_display_attributes(self, attributes: ResourceAttributes, *, tags: list[Tag]) -> ResourceDisplayAttributes:
        return ResourceDisplayAttributes.model_validate(
            attributes.model_dump(mode="python") | {"tags": resolve_display_tags(attributes, tags=tags)}
        )


resource_search_result_view_service = ResourceSearchResultViewService()
