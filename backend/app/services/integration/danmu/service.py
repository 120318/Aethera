from __future__ import annotations

import logging

from app.schemas.domain.vendor import Vendor
from app.services.integration.danmu.base import BaseDanmuProvider
from app.services.integration.danmu.models import DanmuFetchInput, DanmuFetchResult
from app.services.integration.danmu.providers import (
    BilibiliDanmuProvider,
    IqiyiDanmuProvider,
    QQDanmuProvider,
    YoukuDanmuProvider,
)

logger = logging.getLogger("app.integration.danmu")


class DanmuProviderService:
    def __init__(self) -> None:
        self._providers: list[BaseDanmuProvider] = [
            IqiyiDanmuProvider(),
            BilibiliDanmuProvider(),
            YoukuDanmuProvider(),
            QQDanmuProvider(),
        ]

    def has_fetchable_vendor(self, vendors: list[Vendor], enabled_provider_ids: list[str]) -> bool:
        enabled = set(enabled_provider_ids)
        return any(
            provider.provider_id in enabled and provider.can_fetch(vendor)
            for vendor in vendors
            for provider in self._providers
        )

    async def fetch(
        self,
        vendors: list[Vendor],
        request: DanmuFetchInput,
        enabled_provider_ids: list[str],
    ) -> DanmuFetchResult | None:
        enabled = set(enabled_provider_ids)
        for vendor in vendors:
            for provider in self._providers:
                if provider.provider_id not in enabled or not provider.supports(vendor):
                    continue
                try:
                    result = await provider.fetch(vendor, request)
                except Exception as exc:
                    logger.warning("Danmu provider failed: provider=%s error=%s", provider.provider_id, exc)
                    continue
                if result and result.comments:
                    return result
        return None


danmu_provider_service = DanmuProviderService()
