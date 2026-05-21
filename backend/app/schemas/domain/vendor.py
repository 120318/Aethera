from pydantic import BaseModel, Field
from typing import Optional, Dict


class Vendor(BaseModel):
    """Vendor/source information for a media item.

    Matches the normalization performed in `DoubanMediaService.info`:
    - `name`, `logo`, `url`, `id`, `vtype`, `is_paid`, `payment_desc`
    """
    name: Optional[str] = None
    logo: Optional[str] = None
    url: Optional[str] = None
    id: Optional[str] = None
    vtype: Optional[str] = None
