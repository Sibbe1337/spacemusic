"""Full routing composition with real PostgreSQL/cryptography, no external calls."""

import base64
import hashlib
import hmac
import json
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_connected_identity import connected_staff  # noqa: F401
from test_intake_pilot import SOURCE_KEY, WEBHOOK_KEY, inbox, payload  # noqa: F401
from test_lifecycle import journal
from test_operations_config import configuration
from test_operations_gates import ready_states
from test_staff_identity import enrolled, step_up

from services.catalog_review.http import COOKIE
from services.catalog_review.operations.gates import LaunchGate
from services.catalog_review.runtime import compose_portal
from services.catalog_review.staff.http import SESSION_COOKIE


@pytest.fixture
def composed(backend, request):
    staff = request.getfixturevalue("connected_staff")
    intake_service = request.getfixturevalue("inbox")
    config = replace(configuration("staging"), synthetic_staging=True)
    backend.settings = replace(
        backend.settings,
        mode="staging",
        origin=config.origin,
        generation=config.generation,
        source_identity_key=SOURCE_KEY,
    )
    settings = replace(
        staff.settings,
        origin=config.origin,
        rp_id="review-staging.spacemusic.io",
        generation=config.generation,
        client_id=config.google_client_id,
    )
    staff.settings = staff.service.settings = staff.admin.settings = settings
    staff.service.oidc_verifier.client_id = settings.client_id
    staff.admin.set_role(
        staff.principal, "operator", supervision_reference="test-supervised-role"
    )
    journal(backend)
    manifest, runtime, restore = ready_states(config)
    gate = LaunchGate(config, manifest)
    app = compose_portal(
        config=config,
        gate=gate,
        status_provider=lambda: (runtime, restore),
        service=backend,
        document_store=backend.test_blobs,
        staff=staff.service,
        intake=intake_service,
    )
    return TestClient(app, base_url=config.origin), staff, config


def post_webhook(client, *, valid=True):
    raw = json.dumps(payload()).encode()
    signature = (
        "sha256="
        + base64.b64encode(hmac.new(WEBHOOK_KEY, raw, hashlib.sha256).digest()).decode()
    )
    return client.post(
        "/api/intake/typeform",
        content=raw,
        headers={
            "content-type": "application/json",
            "typeform-signature": signature if valid else "wrong",
        },
    )


def test_composed_intake_admission_and_staff_context(composed, backend):
    client, staff, config = composed
    assert client.get("/health/ready").status_code == 200
    assert post_webhook(client, valid=False).status_code == 401
    assert post_webhook(client).status_code == 202
    assert post_webhook(client).status_code == 202
    assert (
        client.get(
            "/api/staff/intakes", headers={"sec-fetch-site": "same-origin"}
        ).status_code
        == 401
    )
    session, keys = enrolled(staff)
    step_up(staff, session, keys[0])
    client.cookies.set(SESSION_COOKIE, session)
    headers = {
        "origin": config.origin,
        "sec-fetch-site": "same-origin",
        "x-csrf-token": staff.service.csrf(session),
    }
    listing = client.get("/api/staff/intakes", headers=headers)
    assert listing.status_code == 200, listing.text
    entries = listing.json()["intakes"]
    assert len(entries) == 1
    uri = "/api/staff/intakes/" + entries[0]["intake_id"] + "/approve"
    data = {"request_id": str(uuid4()), "owner_authority_confirmed": True}
    approved = client.post(uri, json=data, headers=headers)
    assert approved.status_code == 200, approved.text
    workspace = approved.json()["workspace_id"]
    # The owner's export includes the encrypted-at-rest admitted receipt, not
    # another customer's application or staff IDs. No actual email is sent.
    with backend.db.transaction(workspace) as db:
        db.execute("SELECT invitation_id FROM invitations")
        invitation = str(db.fetchone()["invitation_id"])
    owner = backend.exchange_invitation(backend.invitation_token(workspace, invitation))
    exported = backend.export_case(owner)
    assert exported["intake"]["receipt"]["email"] == "owner@example.com"
    assert exported["contact"] == [{"recipient": "owner@example.com"}]
    assert "payload_cipher" not in str(exported) and "source_digest" not in str(
        exported
    )
    assert (
        client.post(uri, json=data, headers=headers).json()["workspace_id"] == workspace
    )
    assert client.get("/api/staff/workspaces", headers=headers).json() == {
        "workspace_ids": []
    }
    staff.admin.assign(
        staff.principal, workspace, active=True, supervision_reference="assigned-test"
    )
    assert client.get("/api/staff/workspaces", headers=headers).json() == {
        "workspace_ids": [workspace]
    }
    context = client.post(
        "/api/staff/workspaces/" + workspace + "/context", json={}, headers=headers
    )
    assert context.status_code == 200, context.text
    assert (
        "Secure" in context.headers["set-cookie"]
        and "HttpOnly" in context.headers["set-cookie"]
    )
    token = client.cookies.get(COOKIE)
    assert backend.view(token)["role"] == "reviewer"
    for origin in ("https://spacemusic.io", "https://evil.test"):
        assert (
            client.get(
                "/api/staff/workspaces",
                headers={**headers, "origin": origin, "sec-fetch-site": "same-site"},
            ).status_code
            == 403
        )
    staff.service.logout(session)
    assert client.get("/api/staff/workspaces", headers=headers).status_code == 401


def test_composed_webhook_and_private_pages_obey_fail_closed_gate(composed):
    client, _, _ = composed
    for path in ("/workspace/", "/staff/"):
        response = client.get(path)
        assert response.status_code == 200
        assert "noindex" in response.headers["x-robots-tag"]
        assert "no-store" in response.headers["cache-control"]
    response = client.post(
        "/api/intake/typeform",
        content=b"{}",
        headers={"content-type": "application/json", "origin": "https://spacemusic.io"},
    )
    assert response.status_code == 403
    client.app.status_provider = lambda: (None, None)
    assert client.get("/health/ready").status_code == 503
    assert post_webhook(client).status_code == 503


def test_staff_callback_redirect_navigation_is_allowed_but_sibling_api_is_not(composed):
    client, _, _ = composed
    navigation = {
        "sec-fetch-site": "cross-site",
        "sec-fetch-mode": "navigate",
        "sec-fetch-dest": "document",
    }
    # Browser keeps cross-site across Google's callback 303 to the staff shell.
    assert client.get("/staff/", headers=navigation).status_code == 200
    assert client.get("/api/staff/session", headers=navigation).status_code == 403
    assert (
        client.get(
            "/staff/", headers={**navigation, "sec-fetch-mode": "cors"}
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/staff/", headers={**navigation, "sec-fetch-dest": "iframe"}
        ).status_code
        == 403
    )
