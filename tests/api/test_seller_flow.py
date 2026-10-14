from __future__ import annotations

import hashlib
from uuid import UUID, uuid4
import pytest
from fastapi.testclient import TestClient

from libs.catalog.payouts import TestPayoutAdapter
from services.spacemusic.main import app
from services.spacemusic.store import SellerStore


@pytest.fixture
def seller_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEMUSIC_INTERNAL_TOKEN", "test-internal-token")
    previous_store = app.state.seller_store
    previous_adapter = app.state.payout_adapter
    app.state.seller_store = SellerStore(str(tmp_path / "seller.db"), str(tmp_path / "documents"))
    app.state.payout_adapter = TestPayoutAdapter()
    with TestClient(app) as client:
        yield client
    app.state.seller_store = previous_store
    app.state.payout_adapter = previous_adapter


def make_history() -> list[dict[str, object]]:
    return [
        {
            "period_start": f"2025-{month:02d}-01",
            "period_end": f"2025-{month:02d}-28",
            "gross_cents": 10_000,
            "adjustments_cents": 0,
            "currency_code": "EUR",
            "source": "DISTRIBUTOR",
            "verified": True,
        }
        for month in range(1, 13)
    ]


def test_seller_happy_path_is_persisted_and_idempotent(seller_client: TestClient):
    application_response = seller_client.post(
        "/seller/applications",
        json={
            "contact_email": "seller@example.com",
            "seller_name": "Synthetic Seller",
            "artist_label": "Synthetic Soundscape Catalog",
            "consent_version": "seller-terms-v1",
            "territories": ["EU", "US"],
            "royalty_sources": ["DISTRIBUTOR"],
        },
    )
    assert application_response.status_code == 201
    created = application_response.json()
    application_id = created["application"]["id"]
    seller_token = created["seller_token"]
    headers = {"X-Seller-Token": seller_token}

    passport_response = seller_client.put(
        f"/seller/applications/{application_id}/passport",
        headers=headers,
        json={
            "artist_label": "Synthetic Soundscape Catalog",
            "tracks": [{"title": "Night Signal", "isrc": "SE-TEST-25-00001", "iswc": "T-900.000.001-1"}],
            "territories": ["EU", "US"],
            "royalty_sources": ["DISTRIBUTOR"],
            "revenue_history": make_history(),
            "metadata_completeness": 1.0,
            "anti_fraud_status": "CLEAR",
            "rights_ownership_share": 1.0,
            "top_track_revenue_share": 0.35,
        },
    )
    assert passport_response.status_code == 200

    content = b"synthetic royalty statement"
    document_response = seller_client.post(
        f"/seller/applications/{application_id}/documents",
        headers=headers,
        json={
            "document_type": "ROYALTY_STATEMENT",
            "original_filename": "royalties.csv",
            "content_type": "text/csv",
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    )
    assert document_response.status_code == 200
    upload_url = document_response.json()["upload_url"]
    upload_response = seller_client.put(upload_url, headers=headers, content=content)
    assert upload_response.status_code == 200
    assert upload_response.json()["document"]["status"] == "UPLOADED"

    document_id = document_response.json()["document"]["id"]
    admin_review = seller_client.post(
        f"/internal/applications/{application_id}/documents/{document_id}/review",
        headers={"X-Internal-Token": "test-internal-token"},
        json={"status": "VERIFIED"},
    )
    assert admin_review.status_code == 200

    valuation_response = seller_client.post(
        f"/seller/applications/{application_id}/valuation",
        headers=headers,
        json={
            "benchmark_version": "synthetic-benchmark-v1",
            "benchmark_multiple_low": 2.0,
            "benchmark_multiple_median": 3.0,
            "benchmark_multiple_high": 4.0,
            "valid_for_days": 14,
            "payment_terms_days": 5,
        },
    )
    assert valuation_response.status_code == 200
    offers = valuation_response.json()["offers"]
    assert {offer["sale_percentage"] for offer in offers} == {50, 75, 100}

    offer_id = next(offer["id"] for offer in offers if offer["sale_percentage"] == 100)
    acceptance_response = seller_client.post(
        f"/seller/applications/{application_id}/offers/{offer_id}/accept",
        headers=headers,
    )
    assert acceptance_response.status_code == 200
    assert acceptance_response.json()["status"] == "ACCEPTED"

    termsheet_response = seller_client.get(
        f"/seller/applications/{application_id}/termsheet",
        headers=headers,
    )
    assert termsheet_response.status_code == 200
    assert termsheet_response.json()["offer"]["sale_percentage"] == 100

    payout_payload = {"offer_id": offer_id, "recipient_token": "seller-recipient-token"}
    payout_headers = {**headers, "Idempotency-Key": "payout-test-001"}
    payout_response = seller_client.post(
        f"/seller/applications/{application_id}/payout",
        headers=payout_headers,
        json=payout_payload,
    )
    assert payout_response.status_code == 200
    assert payout_response.json()["payout"]["status"] == "SUCCEEDED"
    assert payout_response.json()["ledger_status"] == "RECORDED"

    retry_response = seller_client.post(
        f"/seller/applications/{application_id}/payout",
        headers=payout_headers,
        json=payout_payload,
    )
    assert retry_response.status_code == 200
    assert retry_response.json()["payout"]["id"] == payout_response.json()["payout"]["id"]

    conflicting_retry = seller_client.post(
        f"/seller/applications/{application_id}/payout",
        headers={**headers, "Idempotency-Key": "payout-test-001"},
        json={"offer_id": offer_id, "recipient_token": "different-recipient-token"},
    )
    assert conflicting_retry.status_code == 409
    assert conflicting_retry.json()["detail"] == "idempotency_key_conflict"

    duplicate_payout = seller_client.post(
        f"/seller/applications/{application_id}/payout",
        headers={**headers, "Idempotency-Key": "payout-test-002"},
        json=payout_payload,
    )
    assert duplicate_payout.status_code == 409
    assert duplicate_payout.json()["detail"] == "payout_already_succeeded"

    application = seller_client.get(f"/seller/applications/{application_id}", headers=headers)
    assert application.status_code == 200
    assert application.json()["status"] == "PAID"
    actions = [event["action"] for event in seller_client.get(f"/seller/applications/{application_id}/timeline", headers=headers).json()["events"]]
    assert actions == [
        "APPLICATION_SUBMITTED",
        "PASSPORT_UPDATED",
        "DOCUMENT_UPLOAD_REQUESTED",
        "DOCUMENT_UPLOADED",
        "DOCUMENT_REVIEWED",
        "REVIEW_STARTED",
        "VALUATION_COMPLETED",
        "OFFERS_CREATED",
        "OFFER_ACCEPTED",
        "PAYOUT_INTENT_CREATED",
        "PAYOUT_SUCCEEDED",
    ]


def test_verified_source_document_unlocks_seller_entered_history(seller_client: TestClient):
    application_response = seller_client.post(
        "/seller/applications",
        json={
            "contact_email": "history@example.com",
            "artist_label": "Seller-entered History",
            "consent_version": "seller-terms-v1",
            "royalty_sources": ["DISTRIBUTOR"],
        },
    )
    created = application_response.json()
    application_id = created["application"]["id"]
    headers = {"X-Seller-Token": created["seller_token"]}
    history = [dict(period, verified=False) for period in make_history()]

    passport_response = seller_client.put(
        f"/seller/applications/{application_id}/passport",
        headers=headers,
        json={
            "artist_label": "Seller-entered History",
            "tracks": [{"title": "Verified source track", "isrc": "SE-TEST-25-00009"}],
            "territories": ["EU"],
            "royalty_sources": ["DISTRIBUTOR"],
            "revenue_history": history,
            "metadata_completeness": 1.0,
            "anti_fraud_status": "CLEAR",
            "rights_ownership_share": 1.0,
        },
    )
    assert passport_response.status_code == 200

    content = b"verified source export"
    document_response = seller_client.post(
        f"/seller/applications/{application_id}/documents",
        headers=headers,
        json={
            "document_type": "DISTRIBUTOR_EXPORT",
            "original_filename": "export.csv",
            "content_type": "text/csv",
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    )
    document_id = document_response.json()["document"]["id"]
    seller_client.put(document_response.json()["upload_url"], headers=headers, content=content)
    review_response = seller_client.post(
        f"/internal/applications/{application_id}/documents/{document_id}/review",
        headers={"X-Internal-Token": "test-internal-token"},
        json={"status": "VERIFIED"},
    )
    assert review_response.status_code == 200

    valuation_response = seller_client.post(
        f"/seller/applications/{application_id}/valuation",
        headers=headers,
        json={
            "benchmark_version": "synthetic-benchmark-v1",
            "benchmark_multiple_low": 2.0,
            "benchmark_multiple_median": 3.0,
            "benchmark_multiple_high": 4.0,
        },
    )
    assert valuation_response.status_code == 200
    assert valuation_response.json()["valuation"]["median_cents"] > 0


def test_seller_token_is_required(seller_client: TestClient):
    response = seller_client.get("/seller/applications/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

    application_response = seller_client.post(
        "/seller/applications",
        json={
            "contact_email": "seller@example.com",
            "artist_label": "Catalog",
            "consent_version": "seller-terms-v1",
        },
    )
    application_id = application_response.json()["application"]["id"]
    protected = seller_client.get(f"/seller/applications/{application_id}")
    assert protected.status_code == 401


def test_receipt_download_is_bound_to_application(seller_client: TestClient):
    def create_application(email: str) -> tuple[str, str]:
        response = seller_client.post(
            "/seller/applications",
            json={
                "contact_email": email,
                "artist_label": "Catalog",
                "consent_version": "seller-terms-v1",
            },
        )
        payload = response.json()
        return payload["application"]["id"], payload["seller_token"]

    first_id, _ = create_application("first@example.com")
    second_id, _ = create_application("second@example.com")
    store = app.state.seller_store
    offer_id = uuid4()
    store._connection.execute(
        "UPDATE applications SET status = 'ACCEPTED', accepted_offer_id = ? WHERE id = ?",
        (str(offer_id), first_id),
    )
    payout = store.create_payout_intent(
        application_id=UUID(first_id),
        offer_id=offer_id,
        idempotency_key="receipt-bound-test",
        amount_cents=100,
        currency_code="EUR",
    )
    completed = store.complete_payout(payout.id, "test-provider-ref")
    token = store.receipt_download_token(completed.id)
    response = seller_client.get(
        f"/seller/applications/{second_id}/payouts/{completed.id}/receipt?download_token={token}"
    )
    assert response.status_code == 404
