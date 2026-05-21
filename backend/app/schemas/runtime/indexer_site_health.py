from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class IndexerSiteHealthStatus(BaseModel):
    indexer_id: str
    indexer_name: str = ""
    site_id: str
    site_name: str = ""
    status: Literal["healthy", "unhealthy", "unknown"] = "unknown"
    checked_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    consecutive_failures: int = 0
    last_error_message: Optional[str] = None
    notify_pending: bool = False
    client_type: str = "jackett"


class IndexerSiteHealthGroup(BaseModel):
    indexer_id: str
    indexer_name: str = ""
    sites: List[IndexerSiteHealthStatus] = Field(default_factory=list)
