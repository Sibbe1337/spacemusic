from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from conftest import owner_cursor, receipt, sign_in
from fastapi.testclient import TestClient

from services.catalog_review.http import create_test_app
from services.catalog_review.security import ReviewError


def test_expired_invitation_recovery_queues_mail_but_does_not_log_in(backend):
    workspace = backend.ingest(receipt())["workspace_id"]
    original = backend.claim_invitation(workspace)["url"].split("#invitation=")[1]
    backend.clock.advance(901)
    assert backend.request_access(
        {"workspace_id": workspace, "email": "alex@example.com"}
    ) == {"status": "request_received"}
    with pytest.raises(ReviewError):
        backend.exchange_invitation(original)
    job = backend.claim_invitation(workspace)
    assert job["recipient"] == "alex@example.com"
    token = job["url"].split("#invitation=")[1]
    assert token != original
    session = backend.exchange_invitation(token)
    assert backend.view(session)["workspace_id"] == workspace


def test_unknown_mismatch_active_deleted_and_revoked_have_same_response(backend):
    workspace, owner, _ = sign_in(backend)
    data = {"workspace_id": workspace, "email": "alex@example.com"}
    expected = {"status": "request_received"}
    assert backend.request_access(data) == expected
    backend.clock.advance(901)
    assert backend.request_access({**data, "email": "wrong@example.com"}) == expected
    assert backend.request_access({**data, "workspace_id": str(uuid4())}) == expected
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS count FROM invitations")
        assert cur.fetchone()["count"] == 1
    backend.request_deletion(owner)
    assert backend.request_access(data) == expected
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS count FROM invitations")
        assert cur.fetchone()["count"] == 1


def test_recovery_is_concurrency_safe_and_preserves_usable_link(backend):
    workspace = backend.ingest(receipt())["workspace_id"]
    data = {"workspace_id": workspace, "email": "alex@example.com"}
    original = backend.claim_invitation(workspace)["url"]
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: backend.request_access(data), range(3)))
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS count FROM invitations")
        assert cur.fetchone()["count"] == 1
    backend.clock.advance(901)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: backend.request_access(data), range(3)))
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS count FROM invitations")
        assert cur.fetchone()["count"] == 2
    assert backend.claim_invitation(workspace)["url"] != original


def test_recovery_http_requires_origin_throttles_and_returns_no_secret(backend):
    workspace = backend.ingest(receipt())["workspace_id"]
    backend.clock.advance(901)
    data = {"workspace_id": workspace, "email": "alex@example.com"}
    with TestClient(
        create_test_app(backend), base_url="https://review.test"
    ) as browser:
        assert browser.post("/api/portal/access-request", json=data).status_code == 403
        for _ in range(10):
            response = browser.post(
                "/api/portal/access-request",
                json=data,
                headers={"origin": "https://review.test"},
            )
            assert response.status_code == 202
            assert response.json() == {"status": "request_received"}
            assert "set-cookie" not in response.headers
        assert browser.get("/api/portal/workspace").status_code == 401
        assert (
            browser.post(
                "/api/portal/access-request",
                json=data,
                headers={"origin": "https://review.test"},
            ).status_code
            == 429
        )


def test_consumed_link_recovery_after_cooldown_requires_fresh_mailbox_access(backend):
    workspace, prior_session, invitation = sign_in(backend)
    data = {"workspace_id": workspace, "email": "alex@example.com"}
    backend.request_access(data)
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS count FROM invitations")
        assert cur.fetchone()["count"] == 1
    backend.clock.advance(61)
    backend.request_access(data)
    job = backend.claim_invitation(workspace)
    assert job is not None
    assert backend.view(prior_session)["workspace_id"] == workspace
    with pytest.raises(ReviewError):
        backend.exchange_invitation(invitation)
    replacement = backend.exchange_invitation(job["url"].split("#invitation=")[1])
    assert backend.view(replacement)["workspace_id"] == workspace
    with pytest.raises(ReviewError):
        backend.view(prior_session)


def test_consumed_recovery_cannot_queue_more_than_five_links_per_hour(backend):
    workspace, _, _ = sign_in(backend)
    data = {"workspace_id": workspace, "email": "alex@example.com"}
    for _ in range(4):
        backend.clock.advance(61)
        backend.request_access(data)
        backend.exchange_invitation(
            backend.claim_invitation(workspace)["url"].split("#invitation=")[1]
        )
    backend.clock.advance(61)
    backend.request_access(data)
    assert backend.claim_invitation(workspace) is None
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS count FROM invitations")
        assert cur.fetchone()["count"] == 5
