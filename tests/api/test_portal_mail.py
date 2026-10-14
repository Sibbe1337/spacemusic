from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from services.spacemusic.portal.app import Settings, create_app
from services.spacemusic.portal.mail import (
    RECIPIENT,
    ResendTestSender,
    message,
    read_key,
    write_key,
)
from services.spacemusic.portal.store import Conflict, LocalPortalStore

KEY = "re_synthetic_test_credential_not_real"
ORIGIN = "http://127.0.0.1:4194"
PROVIDER_ID = str(uuid4())
HEADERS = {"Origin": ORIGIN, "X-Space-Request": "portal-v1"}


@pytest.fixture
def mail_portal(tmp_path):
    calls = []
    replies = []

    def handle(request):
        calls.append(request)
        if replies:
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        return httpx.Response(200, json={"id": PROVIDER_ID})

    now = [1789109474]
    db = LocalPortalStore(tmp_path / "records", b"x" * 32, lambda: now[0])
    sender = ResendTestSender(KEY, httpx.MockTransport(handle))
    settings = Settings(tmp_path / "records", b"x" * 32, b"y" * 32)
    app = create_app(settings, db, sender)
    with TestClient(app, base_url=ORIGIN, headers=HEADERS) as client:
        client.post("/api/development/seed", json={})
        yield client, db, sender, calls, replies, now
    db.close()


def request_body():
    return {"request_id": str(uuid4()), "confirm_owner_test": True}


def test_real_mail_requires_explicit_startup_opt_in(tmp_path):
    app = create_app(Settings(tmp_path, b"x" * 32, b"y" * 32))
    with TestClient(app, base_url=ORIGIN, headers=HEADERS) as client:
        assert client.get("/api/development/email-test").json()["enabled"] is False
        assert (
            client.post("/api/development/email-test", json=request_body()).status_code
            == 503
        )


def test_default_portal_does_not_require_httpx(tmp_path):
    script = """
import builtins, sys
from pathlib import Path
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == "httpx" or name.startswith("httpx."):
        raise ImportError("httpx unavailable")
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from services.spacemusic.portal.app import Settings, create_app
app = create_app(Settings(Path(sys.argv[1]), b"x" * 32, b"y" * 32))
app.state.store.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_acceptance_fixed_recipient_and_no_secret_leak(mail_portal):
    client, db, sender, calls, _, _ = mail_portal
    body = request_body()
    result = client.post("/api/development/email-test", json=body)
    assert result.status_code == 200
    assert result.json()["status"] == "accepted_by_provider"
    assert "not yet verified" in result.json()["message"]
    assert result.json()["recipient"] == RECIPIENT
    req = calls[0]
    assert str(req.url) == "https://api.resend.com/emails"
    assert req.headers["authorization"] == "Bearer " + KEY
    assert req.headers["idempotency-key"].endswith(body["request_id"])
    payload = json.loads(req.content)
    assert payload["to"] == [RECIPIENT]
    assert payload["from"] == "SPACE <hello@spacemusic.io>"
    assert payload["reply_to"] == RECIPIENT
    assert payload["subject"].startswith("[TEST]")
    assert "same computer" in payload["text"]
    assert "alex@example.com" in payload["text"]
    assert "<img" not in payload["html"]
    assert not {"cc", "bcc", "attachments"} & payload.keys()
    url = next(line for line in payload["text"].splitlines() if line.startswith("http"))
    token = urlsplit(url).fragment.removeprefix("sign-in=")
    assert token not in result.text
    assert KEY not in result.text + repr(sender)
    assert client.get("/api/development/mailbox").json()["messages"] == []
    dump = "\n".join(db.db.iterdump())
    assert KEY not in dump and token not in dump
    assert client.post("/api/auth/consume", json={"token": token}).status_code == 200
    assert client.post("/api/auth/consume", json={"token": token}).status_code == 401


def test_duplicate_request_reuses_provider_receipt(mail_portal):
    client, _, _, calls, _, _ = mail_portal
    body = request_body()
    first = client.post("/api/development/email-test", json=body)
    again = client.post("/api/development/email-test", json=body)
    assert first.json() == again.json()
    assert len(calls) == 1


def test_retry_after_timeout_keeps_identical_payload_and_key(mail_portal):
    client, _, _, calls, replies, _ = mail_portal
    replies.append(httpx.ReadTimeout("secret provider details " + KEY))
    body = request_body()
    first = client.post("/api/development/email-test", json=body)
    assert first.status_code == 502 and KEY not in first.text
    assert client.post("/api/development/email-test", json=body).status_code == 200
    assert calls[0].content == calls[1].content
    assert calls[0].headers["idempotency-key"] == calls[1].headers["idempotency-key"]


@pytest.mark.parametrize("code", [401, 403, 409, 429, 500, 503, 302])
def test_provider_errors_not_disclosed_or_called_delivered(mail_portal, code):
    client, _, _, calls, replies, _ = mail_portal
    replies.append(
        httpx.Response(
            code,
            text="private data " + KEY,
            headers={"Location": "https://evil.example"},
        )
    )
    result = client.post("/api/development/email-test", json=request_body())
    assert result.status_code == 502
    assert KEY not in result.text and "private data" not in result.text
    assert len(calls) == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"id": "not-an-id"}),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={"id": 123}),
        httpx.Response(200, json={"id": {}}),
        httpx.Response(200, content=b"x" * 70000),
    ],
)
def test_invalid_success_response_is_not_acceptance(mail_portal, response):
    client, _, _, _, replies, _ = mail_portal
    replies.append(response)
    assert (
        client.post("/api/development/email-test", json=request_body()).status_code
        == 502
    )


def test_input_origin_host_and_recipient_cannot_be_overridden(mail_portal):
    client, _, _, calls, _, _ = mail_portal
    for body in (
        {},
        {"request_id": "wrong", "confirm_owner_test": True},
        {**request_body(), "confirm_owner_test": False},
        {**request_body(), "to": "someone@example.com"},
        {**request_body(), "html": "custom body"},
    ):
        assert client.post("/api/development/email-test", json=body).status_code == 422
    for headers in (
        {"Origin": "https://evil.example"},
        {"Host": "evil.example"},
        {"X-Space-Request": ""},
        {"Sec-Fetch-Site": "cross-site"},
    ):
        assert client.post(
            "/api/development/email-test", json=request_body(), headers=headers
        ).status_code in (400, 403)
    assert calls == []


def test_owner_send_rate_limit_and_expired_retry(mail_portal):
    client, _, _, calls, replies, now = mail_portal
    body = request_body()
    replies.append(httpx.Response(503))
    assert client.post("/api/development/email-test", json=body).status_code == 502
    now[0] += 901
    assert client.post("/api/development/email-test", json=body).status_code == 409
    for _ in range(4):
        assert (
            client.post("/api/development/email-test", json=request_body()).status_code
            == 200
        )
    assert (
        client.post("/api/development/email-test", json=request_body()).status_code
        == 429
    )
    assert len(calls) == 5


def test_retry_is_stable_across_database_restart(tmp_path):
    directory = tmp_path / "records"
    secret = b"x" * 32
    store = LocalPortalStore(directory, secret, lambda: 1000)
    store.ingest(
        "test",
        {
            "_date": "2026-09-11",
            "email": "alex@example.com",
            "artistLabel": "Fictional",
        },
        set(),
    )
    rid = str(uuid4())
    token, receipt = store.prepare_owner_email(rid, ORIGIN)
    store.close()
    other = LocalPortalStore(directory, secret, lambda: 1001)
    try:
        assert other.prepare_owner_email(rid, ORIGIN) == (token, receipt)
        assert other.latest_owner_email() == {
            "request_id": rid,
            "accepted": False,
            "expired": False,
        }
        with pytest.raises(Conflict):
            other.prepare_owner_email(rid, "http://127.0.0.1:4195")
        other.accept_owner_email(rid, PROVIDER_ID)
        assert other.prepare_owner_email(rid, ORIGIN)[1] == PROVIDER_ID
        assert other.latest_owner_email()["accepted"] is True
    finally:
        other.close()


def test_concurrent_provider_requests_use_identical_idempotency_key(mail_portal):
    _, db, sender, calls, _, _ = mail_portal
    rid = str(uuid4())
    token, _ = db.prepare_owner_email(rid, ORIGIN)

    async def send_twice():
        return await asyncio.gather(
            sender.send(rid, ORIGIN, token), sender.send(rid, ORIGIN, token)
        )

    assert asyncio.run(send_twice()) == [PROVIDER_ID, PROVIDER_ID]
    assert calls[0].headers["idempotency-key"] == calls[1].headers["idempotency-key"]
    assert calls[0].content == calls[1].content


def test_secret_storage_permissions_and_no_overwrite(tmp_path):
    directory = tmp_path / "secrets"
    directory.mkdir(mode=0o700)
    path = directory / "test-key"
    write_key(path, KEY)
    assert read_key(path) == KEY
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_key(path, "re_another_synthetic_credential")
    os.chmod(path, 0o644)
    with pytest.raises(RuntimeError):
        read_key(path)
    os.chmod(path, 0o600)
    link = directory / "linked"
    link.symlink_to(path)
    with pytest.raises(RuntimeError):
        read_key(link)
    with pytest.raises(RuntimeError):
        write_key(Path.cwd() / "tmp/secret-not-allowed", KEY)


def test_template_rejects_nonlocal_links_and_injection():
    for origin in (
        "https://spacemusic.io",
        "https://evil.example",
        ORIGIN + "/path",
        ORIGIN + "?secret=yes",
        "http://user@127.0.0.1:4194",
    ):
        with pytest.raises(ValueError):
            message(origin, "x" * 43)
    with pytest.raises(ValueError):
        message(ORIGIN, '<script>alert("x")</script>')
