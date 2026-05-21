from pydantic import BaseModel
from app.schemas.domain.subscription_filters import SubscriptionFilters

class FilterConfig(BaseModel):
    id: str
    name: str
    is_default: bool
    active_default: bool = False
    quality_profile_id: str | None = None
    filters: SubscriptionFilters
