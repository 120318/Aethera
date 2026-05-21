from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.domain.vendor import Vendor
from app.services.integration.danmu.models import DanmuFetchInput, DanmuFetchResult


class BaseDanmuProvider(ABC):
    provider_id: str

    @abstractmethod
    def supports(self, vendor: Vendor) -> bool:
        raise NotImplementedError

    def can_fetch(self, vendor: Vendor) -> bool:
        return self.supports(vendor)

    @abstractmethod
    async def fetch(self, vendor: Vendor, request: DanmuFetchInput) -> DanmuFetchResult | None:
        raise NotImplementedError
