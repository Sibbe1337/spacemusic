"""Google transport tests: synthetic mount and MockTransport only, no accounts."""

import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace
from urllib.parse import parse_qs
from uuid import uuid4

import httpx
import pytest

from services.catalog_review.staff import GoogleOIDCTransport, StaffError, StaffSettings
from services.catalog_review.staff.transport import JWKS_ENDPOINT, TOKEN_ENDPOINT


@pytest.fixture
def transport_setup(tmp_path):
    path = tmp_path / "independent-google-client-secret"
    path.write_text("synthetic-independent-client-secret\n")
    path.chmod(0o600)
    now = [datetime(2026, 9, 18, 12, tzinfo=timezone.utc)]
    settings = StaffSettings(
        "synthetic-client.apps.googleusercontent.com",
        "https://review.test",
        "review.test",
        str(uuid4()),
        secrets.token_bytes(32),
    )
    clients = []

    def make(handler, **kwargs):
        instance = GoogleOIDCTransport(
            settings,
            client_secret_path=path,
            http_transport=httpx.MockTransport(handler),
            clock=lambda: now[0],
            **{"enabled": True, **kwargs},
        )
        clients.append(instance)
        return instance

    yield SimpleNamespace(path=path, now=now, settings=settings, make=make)
    for client in clients:
        client.close()


def exchange(transport):
    return transport.exchange_code(
        code="synthetic-one-use-code",
        code_verifier="v" * 43,
        redirect_uri=transport.settings.redirect_uri,
    )


def keys_response(**headers):
    # Key cryptography is verified separately using real RSA fixtures.
    return httpx.Response(200, json={"keys": [{"kid": "synthetic"}]}, headers=headers)


def test_google_transport_default_closed_without_network_or_mount(transport_setup):
    calls = []
    transport = transport_setup.make(
        lambda request: calls.append(request), enabled=False
    )
    transport_setup.path.unlink()
    for operation in (lambda: exchange(transport), transport.jwks_snapshot):
        with pytest.raises(StaffError, match="staff_identity_unavailable"):
            operation()
    assert not calls
    with pytest.raises(ValueError, match="mounted"):
        GoogleOIDCTransport(transport_setup.settings, enabled=True)
    with pytest.raises(ValueError, match="boolean"):
        transport_setup.make(lambda request: None, enabled="false")


def test_google_transport_pinned_exchange_and_no_ambient_proxy(
    transport_setup, monkeypatch
):
    monkeypatch.setenv("HTTPS_PROXY", "http://must-not-be-used.invalid:9")
    monkeypatch.setenv("SSL_CERT_FILE", "/nonexistent/must-not-be-used")
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == TOKEN_ENDPOINT and request.method == "POST"
        assert request.headers["accept-encoding"] == "identity"
        assert request.extensions["timeout"] == {
            "connect": 3,
            "read": 3,
            "write": 3,
            "pool": 1,
        }
        assert parse_qs(request.content.decode()) == {
            "client_id": [transport_setup.settings.client_id],
            "client_secret": ["synthetic-independent-client-secret"],
            "code": ["synthetic-one-use-code"],
            "code_verifier": ["v" * 43],
            "redirect_uri": [transport_setup.settings.redirect_uri],
            "grant_type": ["authorization_code"],
        }
        return httpx.Response(
            200,
            json={
                "id_token": "signed-token",
                "access_token": "discard",
                "refresh_token": "discard",
            },
        )

    transport = transport_setup.make(handler)
    assert not transport._client.trust_env
    assert not transport._client.follow_redirects
    assert transport._client._mounts == {}
    assert exchange(transport) == "signed-token" and len(calls) == 1
    assert "synthetic-independent-client-secret" not in repr(transport)


@pytest.mark.parametrize(
    "failure", ["timeout", "connect", 302, 307, 400, 429, 500, 503]
)
def test_google_token_post_never_retries_or_redirects(transport_setup, failure):
    calls = []

    def handler(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("provider-sensitive-body", request=request)
        if failure == "connect":
            raise httpx.ConnectError("provider-sensitive-body", request=request)
        return httpx.Response(
            failure, headers={"location": "https://must-not-follow.invalid/"}
        )

    transport = transport_setup.make(handler)
    with pytest.raises(StaffError) as error:
        exchange(transport)
    assert str(error.value) == "staff_identity_unavailable"
    assert error.value.__cause__ is None
    assert len(calls) == 1


@pytest.mark.parametrize(
    "mode", ["permissions", "symlink", "oversize", "short", "fifo"]
)
def test_google_secret_mount_failures_never_send_request(transport_setup, mode):
    import os

    path = transport_setup.path
    if mode == "permissions":
        path.chmod(0o644)
    elif mode == "symlink":
        path.unlink()
        path.symlink_to(path.parent / "missing")
    elif mode == "fifo":
        path.unlink()
        os.mkfifo(path, 0o600)
    else:
        path.write_text("x" * (2050 if mode == "oversize" else 3))
    calls = []
    transport = transport_setup.make(lambda request: calls.append(request))
    with pytest.raises(StaffError):
        exchange(transport)
    assert not calls


def test_google_transport_rejects_callback_override_and_bad_pkce(transport_setup):
    calls = []
    transport = transport_setup.make(lambda request: calls.append(request))
    for redirect, verifier in (
        ("https://spacemusic.io/api/staff/oidc/callback", "v" * 43),
        (transport.settings.redirect_uri, "short"),
    ):
        with pytest.raises(StaffError):
            transport.exchange_code(
                code="code", code_verifier=verifier, redirect_uri=redirect
            )
    assert not calls


@pytest.mark.parametrize("failure", ["timeout", "connect", 429, 500, 502, 503, 504])
def test_google_jwks_get_has_at_most_two_attempts(transport_setup, failure):
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == JWKS_ENDPOINT and request.method == "GET"
        assert not request.content
        if failure == "timeout":
            raise httpx.ReadTimeout("unavailable", request=request)
        if failure == "connect":
            raise httpx.ConnectError("unavailable", request=request)
        return httpx.Response(failure)

    transport = transport_setup.make(handler)
    with pytest.raises(StaffError):
        transport.jwks_snapshot()
    assert len(calls) == 2


def test_google_jwks_get_retry_can_recover_and_cache(transport_setup):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) == 1 else keys_response()

    transport = transport_setup.make(handler)
    first = transport.jwks_snapshot()
    assert transport.jwks_snapshot() == first and len(calls) == 2
    first.keys[0]["kid"] = "mutated-by-caller"
    assert transport.jwks_snapshot().keys[0]["kid"] == "synthetic"


@pytest.mark.parametrize("status", [301, 302, 307, 308, 400, 401, 403, 404])
def test_google_jwks_redirect_and_permanent_error_not_retried(transport_setup, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, headers={"location": "https://untrusted.invalid/"}
        )

    with pytest.raises(StaffError):
        transport_setup.make(handler).jwks_snapshot()
    assert len(calls) == 1


def test_google_cache_hard_cap_expiry_and_no_stale_on_error(transport_setup):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) > 1:
            return httpx.Response(503)
        return keys_response(**{"cache-control": "public, max-age=999999"})

    transport = transport_setup.make(handler)
    snapshot = transport.jwks_snapshot()
    assert (
        timedelta(0) < snapshot.expires_at - snapshot.fetched_at <= timedelta(hours=24)
    )
    transport_setup.now[0] += timedelta(hours=23)
    assert transport.jwks_snapshot() == snapshot and len(calls) == 1
    transport_setup.now[0] += timedelta(hours=1)
    with pytest.raises(StaffError):
        transport.jwks_snapshot()
    assert len(calls) == 3


def test_google_cache_honors_age_and_header_max_age(transport_setup):
    transport = transport_setup.make(
        lambda request: keys_response(
            **{"cache-control": "public,max-age=120", "age": "90"}
        )
    )
    snapshot = transport.jwks_snapshot()
    assert (
        timedelta(seconds=29)
        < snapshot.expires_at - snapshot.fetched_at
        <= timedelta(seconds=30)
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"cache-control": "no-store"},
        {"cache-control": "no-cache,max-age=300"},
        {"cache-control": "max-age=0"},
        {"cache-control": "max-age=20", "age": "20"},
        {"cache-control": "max-age=-1"},
        {"cache-control": "max-age=30,max-age=90"},
        {"cache-control": "max-age=60", "date": "Thu, 17 Sep 2026 12:00:00 GMT"},
    ],
)
def test_google_uncacheable_or_ambiguous_keys_fail_closed(transport_setup, headers):
    calls = []

    def handler(request):
        calls.append(request)
        return keys_response(**headers)

    with pytest.raises(StaffError):
        transport_setup.make(handler).jwks_snapshot()
    assert len(calls) == 1


@pytest.mark.parametrize(
    "content,headers",
    [
        (b'{"id_token":"a","id_token":"b"}', {}),
        (b"x" * 65537, {}),
        (b"{}", {"content-length": "65537"}),
        (b"{}", {"content-type": "text/html"}),
        (b"{}", {"content-encoding": "gzip"}),
        (json.dumps({"id_token": "x" * 16385}).encode(), {}),
        (b'{"id_token":"token","error":"invalid_grant"}', {}),
        (b'{"access_token":"not-an-id-token"}', {}),
    ],
)
def test_google_token_response_bounds_and_malformed_json(
    transport_setup, content, headers
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            stream=httpx.ByteStream(content),
            headers={"content-type": "application/json", **headers},
        )

    with pytest.raises(StaffError):
        exchange(transport_setup.make(handler))
    assert len(calls) == 1


def test_google_stream_total_budget_checked_between_chunks(
    transport_setup, monkeypatch
):
    elapsed = [0]
    monkeypatch.setattr(
        "services.catalog_review.staff.transport.time.monotonic", lambda: elapsed[0]
    )

    class SlowStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"id_token":'
            elapsed[0] = 13
            yield b'"never-accepted"}'

    transport = transport_setup.make(
        lambda request: httpx.Response(
            200, stream=SlowStream(), headers={"content-type": "application/json"}
        )
    )
    with pytest.raises(StaffError):
        exchange(transport)


def test_google_cache_monotonic_expiry_despite_stationary_wall_clock(
    transport_setup, monkeypatch
):
    elapsed, calls = [0], []
    monkeypatch.setattr(
        "services.catalog_review.staff.transport.time.monotonic", lambda: elapsed[0]
    )

    def handler(request):
        calls.append(request)
        return keys_response(**{"cache-control": "max-age=60"})

    transport = transport_setup.make(handler)
    transport.jwks_snapshot()
    elapsed[0] = 59
    transport.jwks_snapshot()
    assert len(calls) == 1
    elapsed[0] = 60
    transport.jwks_snapshot()
    assert len(calls) == 2


def test_google_cache_refresh_lock_bounded_and_first_request_finishes(transport_setup):
    entered, release = Event(), Event()
    calls = []

    def handler(request):
        calls.append(request)
        entered.set()
        assert release.wait(5)
        return keys_response()

    transport = transport_setup.make(handler)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(transport.jwks_snapshot)
        try:
            assert entered.wait(2)
            with pytest.raises(StaffError, match="unavailable"):
                pool.submit(transport.jwks_snapshot).result(timeout=2)
        finally:
            release.set()
        assert first.result(timeout=2).keys[0]["kid"] == "synthetic"
    assert transport.jwks_snapshot().keys[0]["kid"] == "synthetic" and len(calls) == 1


@pytest.mark.parametrize("keys", [None, [], {}, ["not-a-key"], [{"kid": "key"}] * 11])
def test_google_jwks_shape_and_count_bounded_without_retry(transport_setup, keys):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"keys": keys})

    with pytest.raises(StaffError):
        transport_setup.make(handler).jwks_snapshot()
    assert len(calls) == 1
