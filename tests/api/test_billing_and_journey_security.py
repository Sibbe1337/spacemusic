"""
Security, Billing Entitlement, Webhook Validation, Server-Side Paywall Redaction,
SQLite Persistence, and Full Synthetic Customer Journey Tests (`Finding C` & `Step 4`).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

from services.spacemusic import routes as spacemusic_routes
from services.spacemusic.main import app
from services.spacemusic.paid_memo_service import PaidMemoStore, issue_customer_token


def _sign_webhook(secret: str, payload_bytes: bytes, ts: int | None = None) -> str:
    timestamp = ts if ts is not None else int(time.time())
    mac = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={mac}"


def test_anonymous_and_cross_customer_idor_blocked_on_autumn_endpoints(monkeypatch, tmp_path):
    """
    Anonymous callers (or callers holding a token for a different `customer_id`)
    must receive 401/403 on `/catalog-review/paid-memo/autumn/check`, `/track`,
    `/portal`, and `/customer/{customer_id}`.
    """
    db_file = tmp_path / "idor_test.sqlite3"
    store = PaidMemoStore(db_path=str(db_file))
    monkeypatch.setattr(spacemusic_routes, "_paid_memo_store", store)
    monkeypatch.setenv("SPACE_CUSTOMER_TOKEN_SECRET", "test_customer_signing_secret_2026")

    owner_client = TestClient(app)
    # 1. Owner registers victim customer profile and receives signed customer_token
    create_res = owner_client.post(
        "/catalog-review/paid-memo/autumn/customer",
        json={
            "customer_id": "victim@label.se",
            "name": "Victim Label AB",
            "email": "victim@label.se",
        },
    )
    assert create_res.status_code == 200
    victim_token = create_res.json()["customer_token"]
    assert victim_token.startswith("ctok_")

    # 2. Anonymous client (fresh TestClient with no cookies or headers) cannot read or mutate victim's balance
    anon_client = TestClient(app)

    assert (
        anon_client.post(
            "/catalog-review/paid-memo/autumn/check",
            json={"customer_id": "victim@label.se", "feature_id": "investment_memo_pdf", "send_event": True},
        ).status_code
        == 401
    )
    assert (
        anon_client.post(
            "/catalog-review/paid-memo/autumn/track",
            json={"customer_id": "victim@label.se", "feature_id": "investment_memo_pdf", "value": -50},
        ).status_code
        == 401
    )
    assert (
        anon_client.post(
            "/catalog-review/paid-memo/autumn/portal",
            json={"customer_id": "victim@label.se"},
        ).status_code
        == 401
    )
    assert anon_client.get("/catalog-review/paid-memo/autumn/customer/victim@label.se").status_code == 401
    assert (
        anon_client.post(
            "/catalog-review/paid-memo/autumn/customer",
            json={"customer_id": "victim@label.se", "name": "Overwrite Attempt"},
        ).status_code
        == 401
    )

    # 3. Attacker with their own valid token for `attacker@evil.io` gets 403 Forbidden when targeting `victim@label.se`
    attacker_token = issue_customer_token("attacker@evil.io")
    assert (
        anon_client.post(
            "/catalog-review/paid-memo/autumn/check",
            json={"customer_id": "victim@label.se", "feature_id": "investment_memo_pdf"},
            headers={"X-Customer-Token": attacker_token},
        ).status_code
        == 403
    )
    assert (
        anon_client.post(
            "/catalog-review/paid-memo/autumn/track",
            json={"customer_id": "victim@label.se", "feature_id": "investment_memo_pdf", "value": 1},
            headers={"X-Customer-Token": attacker_token},
        ).status_code
        == 403
    )
    assert (
        anon_client.get(
            "/catalog-review/paid-memo/autumn/customer/victim@label.se",
            headers={"X-Customer-Token": attacker_token},
        ).status_code
        == 403
    )

    # 4. Victim with valid `X-Customer-Token` succeeds
    ok_check = anon_client.post(
        "/catalog-review/paid-memo/autumn/check",
        json={"customer_id": "victim@label.se", "feature_id": "investment_memo_pdf", "send_event": False},
        headers={"X-Customer-Token": victim_token},
    )
    assert ok_check.status_code == 200


def test_webhook_strict_validation_and_no_public_fallback_secret(monkeypatch, tmp_path):
    """
    Verifies:
    - When `STRIPE_MEMO_WEBHOOK_SECRET` is not configured, webhook fails closed (503) and
      the old public fallback secret `whsec_space_memo_test_secret_2026` is rejected.
    - Unpaid/expired payment_status, wrong event type, mismatched checkout_session_id,
      underpaid amount_total, or wrong currency are all rejected with 400 and keep the order locked.
    """
    db_file = tmp_path / "webhook_security.sqlite3"
    store = PaidMemoStore(db_path=str(db_file))
    monkeypatch.setattr(spacemusic_routes, "_paid_memo_store", store)
    monkeypatch.delenv("STRIPE_MEMO_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("AUTUMN_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)

    client = TestClient(app)
    checkout_res = client.post(
        "/catalog-review/paid-memo/checkout",
        json={
            "artist_or_label_name": "Webhook Guard Test",
            "catalog_title": "Strict Validation Vol. 1",
            "contact_email": "security@spacemusic.io",
            "declared_ltm_amount": 35000.0,
            "currency": "USD",
        },
    )
    assert checkout_res.status_code == 201
    order = checkout_res.json()
    order_id = order["order_id"]
    app_id = order["application_id"]
    session_id = order["stripe_session_id"]

    # 1. With no configured webhook secret, signing with the old public fallback constant must fail closed (503)
    old_public_secret = "whsec_space_memo_test_secret_2026"
    valid_body = json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "client_reference_id": order_id,
                    "payment_status": "paid",
                    "amount_total": 29900,
                    "currency": "usd",
                }
            },
        }
    ).encode("utf-8")
    res_no_secret = client.post(
        "/webhooks/stripe-memo",
        content=valid_body,
        headers={"Stripe-Signature": _sign_webhook(old_public_secret, valid_body)},
    )
    assert res_no_secret.status_code == 503

    # Configure real test webhook secret
    live_secret = "whsec_strict_audit_secret_998877"
    monkeypatch.setenv("STRIPE_MEMO_WEBHOOK_SECRET", live_secret)

    # 2. Old public secret signature is rejected (400)
    res_wrong_sig = client.post(
        "/webhooks/stripe-memo",
        content=valid_body,
        headers={"Stripe-Signature": _sign_webhook(old_public_secret, valid_body)},
    )
    assert res_wrong_sig.status_code == 400

    # 3. Wrong event type (`checkout.session.expired`) is rejected (400)
    expired_event_body = json.dumps(
        {
            "type": "checkout.session.expired",
            "data": {
                "object": {
                    "id": session_id,
                    "client_reference_id": order_id,
                    "payment_status": "paid",
                    "amount_total": 29900,
                    "currency": "usd",
                }
            },
        }
    ).encode("utf-8")
    assert (
        client.post(
            "/webhooks/stripe-memo",
            content=expired_event_body,
            headers={"Stripe-Signature": _sign_webhook(live_secret, expired_event_body)},
        ).status_code
        == 400
    )

    # 4. `payment_status: "unpaid"` is rejected (400)
    unpaid_body = json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "client_reference_id": order_id,
                    "payment_status": "unpaid",
                    "amount_total": 29900,
                    "currency": "usd",
                }
            },
        }
    ).encode("utf-8")
    assert (
        client.post(
            "/webhooks/stripe-memo",
            content=unpaid_body,
            headers={"Stripe-Signature": _sign_webhook(live_secret, unpaid_body)},
        ).status_code
        == 400
    )

    # 5. Mismatched `checkout_session_id` is rejected (400)
    wrong_session_body = json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_live_wrong_session_999",
                    "client_reference_id": order_id,
                    "payment_status": "paid",
                    "amount_total": 29900,
                    "currency": "usd",
                }
            },
        }
    ).encode("utf-8")
    assert (
        client.post(
            "/webhooks/stripe-memo",
            content=wrong_session_body,
            headers={"Stripe-Signature": _sign_webhook(live_secret, wrong_session_body)},
        ).status_code
        == 400
    )

    # 6. Underpaid `amount_total` (100 cents instead of 29900 cents) is rejected (400)
    underpaid_body = json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "client_reference_id": order_id,
                    "payment_status": "paid",
                    "amount_total": 100,
                    "currency": "usd",
                }
            },
        }
    ).encode("utf-8")
    assert (
        client.post(
            "/webhooks/stripe-memo",
            content=underpaid_body,
            headers={"Stripe-Signature": _sign_webhook(live_secret, underpaid_body)},
        ).status_code
        == 400
    )

    # 7. Wrong currency (`sek` instead of `usd`) is rejected (400)
    wrong_currency_body = json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "client_reference_id": order_id,
                    "payment_status": "paid",
                    "amount_total": 29900,
                    "currency": "sek",
                }
            },
        }
    ).encode("utf-8")
    assert (
        client.post(
            "/webhooks/stripe-memo",
            content=wrong_currency_body,
            headers={"Stripe-Signature": _sign_webhook(live_secret, wrong_currency_body)},
        ).status_code
        == 400
    )

    # Confirm order is still locked (`402` on PDF)
    assert client.get(f"/catalog-review/{app_id}/investment-memo.pdf").status_code == 402


def test_server_side_locked_preview_redaction_and_vip_coupon_removal(monkeypatch, tmp_path):
    """
    Verifies:
    1. Hardcoded VIP coupons (`SPACE-PARTNER-VIP`, `SPACE-INTERNAL-100`, `AUTUMN-DESK-PASS`,
       `CLAUDE-FREE-UNLOCK`) do NOT mark orders `PAID` and `?receipt_token=SPACE-PARTNER-VIP`
       does NOT unlock HTML or PDF.
    2. When `locked_preview=True`, Slides 03-19 are redacted server-side (`LOCKED — SERVER ENTITLEMENT REQUIRED TO RENDER SLIDE CONTENT`)
       and raw financial/forensic content of Slides 03-19 is completely absent from the HTTP response.
    """
    db_file = tmp_path / "redaction_test.sqlite3"
    store = PaidMemoStore(db_path=str(db_file))
    monkeypatch.setattr(spacemusic_routes, "_paid_memo_store", store)

    client = TestClient(app)
    for legacy_coupon in ("SPACE-PARTNER-VIP", "SPACE-INTERNAL-100", "AUTUMN-DESK-PASS", "CLAUDE-FREE-UNLOCK"):
        res = client.post(
            "/catalog-review/paid-memo/checkout",
            json={
                "artist_or_label_name": "Coupon Bypass Attempt",
                "catalog_title": "Test Catalog",
                "declared_ltm_amount": 50000.0,
                "currency": "USD",
                "coupon_code": legacy_coupon,
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["payment_status"] == "PENDING_PAYMENT"
        assert data["receipt_token"] is None
        assert data["amount_usd"] == 299.0

    app_id = data["application_id"]

    # Attempt `?receipt_token=SPACE-PARTNER-VIP` on HTML and PDF
    vip_pdf = client.get(f"/catalog-review/{app_id}/investment-memo.pdf?receipt_token=SPACE-PARTNER-VIP")
    assert vip_pdf.status_code == 402

    locked_html_res = client.get(f"/catalog-review/{app_id}/investment-memo.html?receipt_token=SPACE-PARTNER-VIP")
    assert locked_html_res.status_code == 200
    html_text = locked_html_res.text

    # Slides 01-02 are visible, Slides 03-19 are server-redacted placeholders
    assert "Previewing Slides 01–02 of 19" in html_text
    assert "LOCKED — SERVER ENTITLEMENT REQUIRED TO RENDER SLIDE CONTENT" in html_text
    assert html_text.count("LOCKED — SERVER ENTITLEMENT REQUIRED TO RENDER SLIDE CONTENT") == 17

    # Ensure Slide 03-19 confidential data is NOT leaked in the locked HTML body
    stored_order = store.get_by_order_id(data["order_id"])
    assert stored_order is not None
    assert stored_order.deck.s06_bottom_note not in html_text
    assert stored_order.deck.s10_footer_caption not in html_text
    assert stored_order.deck.s14_quote_text not in html_text
    assert stored_order.deck.s16_headline not in html_text


def test_complete_end_to_end_synthetic_customer_journey_and_sqlite_persistence(monkeypatch, tmp_path):
    """
    Verifies the complete synthetic customer journey end-to-end:
    1. Stage 1 intake & Stage 2 verified European semicolon/comma CSV statement upload
    2. Engine valuation + checkout creation (`PENDING_PAYMENT`)
    3. Return URL before payment returns `402 Payment Required`
    4. Validated paid Stripe webhook unlocks order (`PAID`)
    5. Post-checkout return URL (`/catalog-review/paid-memo/return`) exchanges `return_token`
       for `receipt_token` and sets session cookie
    6. Unlocked 19-Slide HTML (`200 OK`, all 19 slides present) & PDF (`200 OK`, `%PDF-1.4`)
    7. Re-instantiating `PaidMemoStore` from SQLite disk preserves order, receipt token, and PDF access
    8. Authorized refund (`POST /catalog-review/paid-memo/orders/{order_id}/refund`) revokes access (`402`)
    """
    db_file = tmp_path / "e2e_journey.sqlite3"
    secret = "whsec_e2e_synthetic_journey_secret_2026"
    monkeypatch.setenv("STRIPE_MEMO_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("SPACE_CUSTOMER_TOKEN_SECRET", "cust_secret_e2e_2026")

    store1 = PaidMemoStore(db_path=str(db_file))
    monkeypatch.setattr(spacemusic_routes, "_paid_memo_store", store1)

    client = TestClient(app)

    # 1. Prepare 12 months of semicolon-separated CSV statements
    euro_csv = "reporting_month;title;isrc;store;country;quantity;earnings\n" + "\n".join(
        f"2025-{m:02d};Northern Lights Pt. {m};SE77725000{m:02d};Spotify;SE;185000;3450.50"
        for m in range(1, 13)
    )

    # 2. Create checkout order
    checkout_res = client.post(
        "/catalog-review/paid-memo/checkout",
        json={
            "artist_or_label_name": "Aurora Borealis Recordings AB",
            "catalog_title": "Northern Lights Anthology",
            "contact_name": "Astrid Lindholm",
            "contact_email": "astrid@auroraborealis.se",
            "declared_ltm_amount": 41406.0,
            "currency": "EUR",
            "distributor": "FUGA",
            "plan_tier": "SINGLE_MEMO_299",
            "raw_statement_csv": euro_csv,
        },
    )
    assert checkout_res.status_code == 201
    order_data = checkout_res.json()
    order_id = order_data["order_id"]
    app_id = order_data["application_id"]
    session_id = order_data["stripe_session_id"]
    return_token = order_data["checkout_return_token"]
    return_url = order_data["return_url"]
    customer_token = order_data["customer_token"]

    assert order_data["payment_status"] == "PENDING_PAYMENT"
    assert return_token.startswith("rtok_")
    assert customer_token.startswith("ctok_")

    # 3. Calling return URL before webhook payment returns 402 Payment Required
    pre_return_res = client.get(return_url)
    assert pre_return_res.status_code == 402

    # 4. Complete payment via validated Stripe webhook
    webhook_payload = json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "client_reference_id": order_id,
                    "payment_status": "paid",
                    "amount_total": 29900,
                    "currency": "usd",
                    "metadata": {"order_id": order_id, "application_id": app_id},
                }
            },
        }
    ).encode("utf-8")
    wh_res = client.post(
        "/webhooks/stripe-memo",
        content=webhook_payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": _sign_webhook(secret, webhook_payload),
        },
    )
    assert wh_res.status_code == 200
    assert wh_res.json()["payment_status"] == "PAID"

    # 5. Customer returns from Stripe checkout to `return_url` -> receives unlocked URLs + receipt cookie
    post_return_res = client.get(return_url)
    assert post_return_res.status_code == 200
    ret_body = post_return_res.json()
    assert ret_body["payment_status"] == "PAID"
    receipt_token = ret_body["receipt_token"]
    assert receipt_token

    # 6. Customer can now view full 19-slide HTML and download PDF (via receipt_token or return_token or cookie)
    unlocked_html_res = client.get(f"/catalog-review/{app_id}/investment-memo.html?return_token={return_token}")
    assert unlocked_html_res.status_code == 200
    assert "LOCKED — SERVER ENTITLEMENT REQUIRED TO RENDER SLIDE CONTENT" not in unlocked_html_res.text
    assert "16 · OFFER STRUCTURES" in unlocked_html_res.text

    unlocked_pdf_res = client.get(ret_body["unlocked_pdf_url"])
    assert unlocked_pdf_res.status_code == 200
    assert unlocked_pdf_res.content.startswith(b"%PDF-1.4")

    # 7. Simulate service restart by instantiating a brand-new `PaidMemoStore` pointing to the same SQLite DB
    store2 = PaidMemoStore(db_path=str(db_file))
    monkeypatch.setattr(spacemusic_routes, "_paid_memo_store", store2)

    persisted_pdf_res = client.get(
        f"/catalog-review/{app_id}/investment-memo.pdf?receipt_token={receipt_token}"
    )
    assert persisted_pdf_res.status_code == 200
    assert persisted_pdf_res.content.startswith(b"%PDF-1.4")

    # 8. Unauthorized refund attempt without customer token fails (401/403); authorized refund revokes access (402)
    anon_client = TestClient(app)
    assert anon_client.post(f"/catalog-review/paid-memo/orders/{order_id}/refund").status_code == 401

    refund_res = anon_client.post(
        f"/catalog-review/paid-memo/orders/{order_id}/refund",
        headers={"X-Customer-Token": customer_token},
    )
    assert refund_res.status_code == 200
    assert refund_res.json()["payment_status"] == "REFUNDED"
    assert refund_res.json()["access_revoked"] is True

    # Old receipt_token and return_token now return 402 Payment Required
    revoked_pdf_res = client.get(
        f"/catalog-review/{app_id}/investment-memo.pdf?receipt_token={receipt_token}"
    )
    assert revoked_pdf_res.status_code == 402
    assert client.get(return_url).status_code == 402


def test_buyer_router_rights_scope_and_stage1_unverified_guard():
    """
    Verifies:
    1. A `PUBLISHING`-only catalog never matches `MASTERS`-only buyers (like Duetti, beatBread, Symphonic).
    2. A Stage 1 or `statements_verified=False` catalog never receives `eligible_for_syndication=True`
       or `routing_status="READY_FOR_BUYER_SYNDICATION"`.
    """
    from datetime import date

    from services.spacemusic.buyer_router import route_catalog_to_institutional_buyers
    from services.spacemusic.models import CatalogApplication
    from services.valuation.engine import CatalogValuationInput, RightsScope, SpaceValuationEngine

    engine = SpaceValuationEngine(random_seed=42)

    pub_input = CatalogValuationInput(
        catalog_title="Nordic Songbook Publishing",
        artist_or_label_name="Stockholm Writers Collective",
        rights_scope=RightsScope.PUBLISHING,
        declared_ltm_amount=85000.0,
        declared_currency="EUR",
        statements_verified=True,
        genres=["pop", "electronic"],
    )
    pub_val = engine.evaluate(pub_input, reference_date=date(2026, 10, 15))
    pub_app = CatalogApplication(
        artist_or_label_name="Stockholm Writers Collective",
        rights_scope="publishing",
        pipeline_status="STAGE_2_STATEMENT_VERIFIED",
        valuation_stage="STAGE_2_STATEMENT_VERIFIED",
        statements_verified=True,
    )
    pub_routing = route_catalog_to_institutional_buyers(pub_app, pub_val)

    masters_only_buyers = {"duetti", "beatbread", "symphonic_distribution"}
    for match in pub_routing.recommended_buyers:
        assert match.partner_id not in masters_only_buyers

    # Stage 1 / unverified catalog must NOT be eligible for syndication
    unverified_input = pub_input.model_copy(update={"statements_verified": False})
    unverified_val = engine.evaluate(unverified_input, reference_date=date(2026, 10, 15))
    stage1_app = CatalogApplication(
        artist_or_label_name="Stockholm Writers Collective",
        rights_scope="publishing",
        pipeline_status="STAGE_1_INITIAL",
        valuation_stage="STAGE_1_INDICATIVE",
        statements_verified=False,
    )
    stage1_routing = route_catalog_to_institutional_buyers(stage1_app, unverified_val)
    assert stage1_routing.eligible_for_syndication is False
    assert stage1_routing.routing_status == "AWAITING_STATEMENT_VERIFICATION"


def test_inbox_ingestor_rejects_empty_attachments_and_mismatched_sender():
    """
    Verifies that `ingest_inbound_email_statements` does NOT mark an existing application
    `statements_verified=True` when:
      1. Zero valid statement rows are parsed, OR
      2. The inbound email `sender_email` does not match the applicant's registered `contact_email`.
    """
    import base64

    from services.spacemusic.inbox_ingestor import (
        InboundAttachmentPayload,
        InboundEmailStatementWebhook,
        ingest_inbound_email_statements,
    )
    from services.spacemusic.models import CatalogApplication
    from services.valuation.engine import SpaceValuationEngine

    app_row = CatalogApplication(
        artist_or_label_name="Verified Artist",
        contact_email="owner@verifiedartist.com",
        distributor_or_admin="DistroKid",
        declared_ltm_amount=25000.0,
        declared_currency="EUR",
        pipeline_status="STAGE_1_INITIAL",
        valuation_stage="STAGE_1_INDICATIVE",
        statements_verified=False,
    )
    applications_store = {app_row.id: app_row}
    engine = SpaceValuationEngine(random_seed=42)

    # Case 1: Matching sender, but 0 attachments / 0 valid rows -> quarantined, stays unverified
    empty_webhook = InboundEmailStatementWebhook(
        sender_email="owner@verifiedartist.com",
        subject=f"Statements for {app_row.id}",
        application_id=str(app_row.id),
        attachments=[],
    )
    res_empty = ingest_inbound_email_statements(
        webhook=empty_webhook,
        applications_store=applications_store,
        engine=engine,
    )
    assert res_empty.statements_verified is False
    assert res_empty.quarantined is True
    assert applications_store[app_row.id].statements_verified is False

    # Case 2: Valid CSV attachment, but sender_email does NOT match app_row.contact_email -> quarantined!
    valid_csv = (
        "reporting_month,title,isrc,store,country,quantity,earnings\n"
        "2025-10,Track One,SEAA12500001,Spotify,SE,120000,450.00\n"
        "2025-11,Track One,SEAA12500001,Spotify,SE,130000,490.00\n"
    )
    spoofed_webhook = InboundEmailStatementWebhook(
        sender_email="spoofed_attacker@untrusted.org",
        subject=f"Statements for {app_row.id}",
        application_id=str(app_row.id),
        attachments=[
            InboundAttachmentPayload(
                filename="statements.csv",
                content_type="text/csv",
                content_text=valid_csv,
            )
        ],
    )
    res_spoofed = ingest_inbound_email_statements(
        webhook=spoofed_webhook,
        applications_store=applications_store,
        engine=engine,
    )
    assert res_spoofed.statements_verified is False
    assert res_spoofed.sender_verified is False
    assert res_spoofed.quarantined is True
    assert applications_store[app_row.id].statements_verified is False

    # Case 3: Valid CSV attachment AND matching sender_email -> verified and upgraded to STAGE_2_STATEMENT_VERIFIED
    authentic_webhook = InboundEmailStatementWebhook(
        sender_email="owner@verifiedartist.com",
        subject=f"Statements for {app_row.id}",
        application_id=str(app_row.id),
        attachments=[
            InboundAttachmentPayload(
                filename="statements.csv",
                content_type="text/csv",
                content_base64=base64.b64encode(valid_csv.encode("utf-8")).decode("ascii"),
            )
        ],
    )
    res_authentic = ingest_inbound_email_statements(
        webhook=authentic_webhook,
        applications_store=applications_store,
        engine=engine,
    )
    assert res_authentic.statements_verified is True
    assert res_authentic.sender_verified is True
    assert res_authentic.quarantined is False
    assert applications_store[app_row.id].statements_verified is True
    assert applications_store[app_row.id].valuation_stage == "STAGE_2_STATEMENT_VERIFIED"

