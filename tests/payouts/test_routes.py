from unittest.mock import patch
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from services.payouts.main import app as payouts_api_app


def test_retry_offer_payout_requires_internal_auth(monkeypatch):
    monkeypatch.setenv("SPACEMUSIC_INTERNAL_TOKEN", "internal-test-token")
    client = TestClient(payouts_api_app)

    response = client.post(f"/internal/payouts/offers/{uuid4()}/retry_payout")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@patch("services.payouts.routes.execute_payout.apply_async")
def test_retry_offer_payout_enqueues_safe_task(mock_apply_async, monkeypatch):
    monkeypatch.setenv("SPACEMUSIC_INTERNAL_TOKEN", "internal-test-token")
    client = TestClient(payouts_api_app)
    offer_id = uuid4()

    response = client.post(
        f"/internal/payouts/offers/{offer_id}/retry_payout",
        headers={"X-Internal-Token": "internal-test-token"},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["offer_id"] == str(offer_id)
    mock_apply_async.assert_called_once_with(args=[str(offer_id)], queue="payouts")


def test_payouts_health_check():
    client = TestClient(payouts_api_app)
    response = client.get("/payouts-health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "service": "payouts-api"}
