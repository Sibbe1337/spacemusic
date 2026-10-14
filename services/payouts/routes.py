import hmac
import os
import uuid
from fastapi import APIRouter, Header, HTTPException, status
import structlog

# Assuming .worker imports the celery_app and the task
from .worker import execute_payout # Import the task
# If celery_app is not directly exposed, you might need to import task by its registered name
# from celery import current_app # And then send_task

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/internal/payouts", # Matches POST /internal/offers/{id}/retry_payout, adjusted for service focus
    tags=["payouts-internal"],
)


def _require_internal_token(provided: str) -> None:
    configured = os.getenv("SPACEMUSIC_INTERNAL_TOKEN")
    if not configured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Internal access is not configured")
    if not provided or not hmac.compare_digest(configured, provided):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token")

@router.post("/offers/{offer_id}/retry_payout", status_code=status.HTTP_202_ACCEPTED)
async def retry_offer_payout(
    offer_id: uuid.UUID,
    x_internal_token: str = Header(default=""),
):
    """
    Manually triggers or retries the payout process for a given offer.
    This endpoint should be protected and only accessible by admin/internal services.
    """
    _require_internal_token(x_internal_token)
    logger.info("Received request to retry payout for offer", offer_id=str(offer_id))

    # Send task to Celery worker
    # Ensure the task name matches how it's registered by Celery in worker.py
    # If using `name=` in @celery_app.task, use that. Otherwise, it's module.function_name.
    # The task name was set to "services.payouts.worker.execute_payout"
    task_name = "services.payouts.worker.execute_payout"

    # Using background_tasks to send Celery task to avoid blocking the request if Celery broker is slow
    # However, for critical tasks, direct .delay() or .apply_async() is common.
    # background_tasks.add_task(execute_payout.delay, str(offer_id))
    # For direct call:
    try:
        # payouts_celery_app.send_task(task_name, args=[str(offer_id)], queue="payouts") # if app not imported directly
        execute_payout.apply_async(args=[str(offer_id)], queue="payouts") # Recommended way
        logger.info("Payout retry task sent to Celery queue", offer_id=str(offer_id), task_name=task_name)
    except Exception as e:
        logger.error("Failed to send payout retry task to Celery", offer_id=str(offer_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to enqueue payout task.")

    return {"message": "Payout retry process initiated successfully.", "offer_id": str(offer_id)}

# Placeholder for main FastAPI app in payouts service (if this service also has its own API)
# If payouts is only a worker, this routes.py might be part of another service's API (e.g. an Admin API)
# or this service has a minimal API just for this internal endpoint.
# from fastapi import FastAPI
# app = FastAPI(title="Payouts Internal API")
# app.include_router(router)
