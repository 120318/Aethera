from app.schemas.exception import SubscriptionNotFoundException
from app.schemas.domain.subscription_run_result import SubscriptionRunResponse
from app.services.application.workflows.subscription.run import subscription_run_application_service
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class RunRequest(BaseModel):
    sub_id: str


class RunSubscriptionResponse(BaseModel):
    data: SubscriptionRunResponse


@router.post("/run", response_model=RunSubscriptionResponse)
async def run_subscription(req: RunRequest):
    """Run a single subscription check for the provided `sub_id`.

    Request body: { "sub_id": "..." }
    """
    result = await subscription_run_application_service.run_one_by_sub_id(req.sub_id)
    return RunSubscriptionResponse(data=result)
