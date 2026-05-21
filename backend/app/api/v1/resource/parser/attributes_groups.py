"""
textAPItext
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class AttributesListResponse(BaseModel):
    status: str
    message_key: str
    data: list[str]


@router.get("/attributes/groups", response_model=AttributesListResponse)
async def get_available_groups() -> AttributesListResponse:
    """
    text
    （text）
    """
    # Internal note.
    # Internal note.
    common_groups = [
        "FRDS", "CHD", "WiKi", "NTb", "EPiC", "CtrlHD", 
        "MOMOHD", "BMF", "FLUX", "HDB", "PTer", "BBQDDQ"
    ]
    
    return AttributesListResponse(
        status="ok",
        message_key="operationMessages.resourceParser.groupsRetrieved",
        data=common_groups,
    )
