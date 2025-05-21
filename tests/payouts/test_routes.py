import pytest
from unittest.mock import patch, MagicMock
import uuid
from fastapi.testclient import TestClient
from fastapi import status

# Adjust import based on your project structure
# Assuming services.payouts.main contains the FastAPI app
# and services.payouts.routes is where the router is defined.
from services.payouts.main import app as payouts_api_app # The FastAPI app instance
# from services.payouts.worker import execute_payout # To mock its apply_async

client = TestClient(payouts_api_app)

# Mock the Celery task's apply_async method
# This is crucial because the endpoint calls execute_payout.apply_async
@patch("services.payouts.routes.execute_payout.apply_async")
def test_retry_offer_payout_success(mock_execute_payout_apply_async):
    mock_execute_payout_apply_async.return_value = MagicMock(id="test_task_id") # Mock Celery AsyncResult
    test_offer_id = uuid.uuid4()

    response = client.post(f"/internal/payouts/offers/{str(test_offer_id)}/retry_payout")

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == {
        "message": "Payout retry process initiated successfully.",
        "offer_id": str(test_offer_id)
    }
    # Assert that the Celery task was called with the correct arguments
    mock_execute_payout_apply_async.assert_called_once_with(
        args=[str(test_offer_id)], 
        queue="payouts"
    )

@patch("services.payouts.routes.execute_payout.apply_async", side_effect=Exception("Celery Broker Down"))
def test_retry_offer_payout_celery_failure(mock_execute_payout_apply_async_fails):
    test_offer_id = uuid.uuid4()

    response = client.post(f"/internal/payouts/offers/{str(test_offer_id)}/retry_payout")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": "Failed to enqueue payout task."}
    mock_execute_payout_apply_async_fails.assert_called_once_with(
        args=[str(test_offer_id)], 
        queue="payouts"
    )

def test_payouts_health_check():
    response = client.get("/payouts-health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "service": "payouts-api"}

# Add more tests, e.g., for authentication if implemented on the internal endpoint. 