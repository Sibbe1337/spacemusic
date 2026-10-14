import asyncio
from threading import Event
from uuid import uuid4

import httpx
import pytest
from conftest import draft, receipt, sign_in
from fastapi.testclient import TestClient

from services.catalog_review.http import COOKIE, HEADERS, create_test_app


def client(service):
    return TestClient(create_test_app(service), base_url="https://review.test")


def invitation(service):
    workspace = service.ingest(receipt())["workspace_id"]
    return service.claim_invitation(workspace)["url"].split("#invitation=")[1]


def test_http_full_session_draft_submit_logout(backend):
    invitation_token = invitation(backend)
    with client(backend) as browser:
        # Mail/link scanner GET cannot consume the invitation.
        assert browser.get("/api/portal/session").status_code == 405
        response = browser.post(
            "/api/portal/session",
            json={"token": invitation_token},
            headers={"origin": "https://review.test"},
        )
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        for part in ("HttpOnly", "Secure", "SameSite=lax", "Path=/"):
            assert part in cookie
        assert "Domain=" not in cookie
        assert invitation_token not in response.text
        csrf = response.json()["csrf"]
        headers = {"origin": "https://review.test", "x-csrf-token": csrf}
        assert browser.get("/api/portal/workspace").status_code == 200
        assert browser.put(
            "/api/portal/draft", json={"revision": 0, "draft": draft()}, headers=headers
        ).json() == {"revision": 1}
        body = {"revision": 1, "request_id": str(uuid4()), "consent": True}
        assert (
            browser.post("/api/portal/submission", json=body, headers=headers).json()[
                "created"
            ]
            is True
        )
        assert (
            browser.post("/api/portal/submission", json=body, headers=headers).json()[
                "created"
            ]
            is False
        )
        assert browser.delete("/api/portal/session", headers=headers).status_code == 204
        assert browser.get("/api/portal/workspace").status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/apply/",
        "/api/test/login",
        "/api/portal/mailbox",
        "/api/reviewer/login",
        "/api/integrations/toolost/callback",
        "/docs",
        "/openapi.json",
    ],
)
def test_no_legacy_or_fixture_or_marketing_routes(backend, path):
    with client(backend) as browser:
        response = browser.get(path)
        assert response.status_code == 404
        for name, value in HEADERS.items():
            assert response.headers[name] == value


def test_cross_site_missing_origin_and_csrf(backend):
    token = invitation(backend)
    with client(backend) as browser:
        assert (
            browser.post("/api/portal/session", json={"token": token}).status_code
            == 403
        )
        assert (
            browser.post(
                "/api/portal/session",
                json={"token": token},
                headers={"origin": "https://evil.test"},
            ).status_code
            == 403
        )
        response = browser.post(
            "/api/portal/session",
            json={"token": token},
            headers={"origin": "https://review.test"},
        )
        assert response.status_code == 200
        assert (
            browser.put(
                "/api/portal/draft",
                json={"revision": 0, "draft": draft()},
                headers={"origin": "https://review.test"},
            ).status_code
            == 403
        )
        assert (
            browser.get(
                "/api/portal/workspace", headers={"sec-fetch-site": "cross-site"}
            ).status_code
            == 403
        )
        assert (
            browser.get(
                "/api/portal/workspace", headers={"host": "spacemusic.io"}
            ).status_code
            == 400
        )
        assert browser.get("/api/portal/workspace?token=private").status_code == 400
        assert browser.get("http://review.test/api/portal/workspace").status_code == 400


def test_query_tokens_and_invalid_payload_are_not_reflected(backend):
    with client(backend) as browser:
        for data in [
            {"token": "secret-do-not-echo"},
            {"token": "x" * 100, "email": "private@example.com"},
        ]:
            response = browser.post(
                "/api/portal/session",
                json=data,
                headers={"origin": "https://review.test"},
            )
            assert response.status_code == 422
            assert response.json() == {"error": "invalid_fields"}
        response = browser.post(
            "/api/portal/session",
            content="X" * 65537,
            headers={
                "origin": "https://review.test",
                "content-type": "application/json",
            },
        )
        assert response.status_code == 413
        response = browser.post(
            "/api/portal/session",
            content="text",
            headers={"origin": "https://review.test"},
        )
        assert response.status_code == 415


def test_invitation_throttled_and_resets(backend):
    with client(backend) as browser:
        for _ in range(10):
            assert (
                browser.post(
                    "/api/portal/session",
                    json={"token": "invalid"},
                    headers={"origin": "https://review.test"},
                ).status_code
                == 422
            )
        assert (
            browser.post(
                "/api/portal/session",
                json={"token": "invalid"},
                headers={
                    "origin": "https://review.test",
                    "x-forwarded-for": "different",
                },
            ).status_code
            == 429
        )
        backend.clock.advance(60)
        assert (
            browser.post(
                "/api/portal/session",
                json={"token": "invalid"},
                headers={"origin": "https://review.test"},
            ).status_code
            == 422
        )


def test_revoked_membership_and_database_failure_closed(backend, monkeypatch):
    _, token, _ = sign_in(backend)
    with client(backend) as browser:
        browser.cookies.set(COOKIE, token)

        def fail(*args):
            raise RuntimeError("postgres://sensitive:password@host/private")

        monkeypatch.setattr(backend, "view", fail)
        response = browser.get("/api/portal/workspace")
        assert response.status_code == 503
        assert response.json() == {"error": "temporarily_unavailable"}
        assert response.headers["cache-control"] == "no-store"


def test_slow_exchange_does_not_block_other_requests(backend, monkeypatch):
    _, token, invitation_token = sign_in(backend)
    entered, release = Event(), Event()

    def slow_exchange(_):
        entered.set()
        assert release.wait(5)
        return token

    monkeypatch.setattr(backend, "exchange_invitation", slow_exchange)

    async def exercise():
        async with httpx.AsyncClient(
            app=create_test_app(backend), base_url="https://review.test"
        ) as browser:
            exchange = asyncio.create_task(
                browser.post(
                    "/api/portal/session",
                    json={"token": invitation_token},
                    headers={"origin": "https://review.test"},
                )
            )
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                response = await asyncio.wait_for(browser.get("/missing"), timeout=1)
                assert response.status_code == 404
            finally:
                release.set()
                assert (await exchange).status_code == 200

    asyncio.run(exercise())
