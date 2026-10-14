import hashlib
import json
import secrets
import socket
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest

from services.catalog_review.providers.adapter import ReadOnlyAdapter, Response
from services.catalog_review.providers.contracts import (
    Config,
    ProviderError,
    decimal_string,
)
from services.catalog_review.providers.crypto import TokenVault, b64, pkce
from services.catalog_review.providers.normalization import normalize_page


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("External network is forbidden in provider tests")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


class Transport:
    offline = True

    def __init__(self, response):
        self.response = response
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        return self.response


def config(**kwargs):
    return Config(
        enabled=True,
        client_id="synthetic-client",
        client_secret="synthetic-secret",
        **kwargs,
    )


def hooks():
    return {
        "before_send": lambda: None,
        "observe": lambda _: None,
        "now": datetime(2026, 9, 18, 12, tzinfo=timezone.utc),
    }


def response(body, status=200, headers=None):
    encoded = body if isinstance(body, bytes) else json.dumps(body).encode()
    return Response(
        status, {"Content-Type": "application/json", **(headers or {})}, [encoded]
    )


@pytest.mark.parametrize("size", range(1, 35))
def test_aead_round_trip_every_padding_length_and_random_nonce(size):
    vault = TokenVault({"key-1": secrets.token_bytes(32)}, "key-1")
    value, binding = (
        {"token": "x" * size},
        {"workspace": "one", "environment": "sandbox"},
    )
    first, second = vault.seal(value, binding), vault.seal(value, binding)
    assert first != second
    assert vault.open(first, binding) == value
    assert "x" * size not in first.values()


def test_aead_context_tampering_and_versioned_rotation():
    old, new = secrets.token_bytes(32), secrets.token_bytes(32)
    binding = {
        "workspace": "one",
        "connection": "a",
        "generation": 1,
        "environment": "sandbox",
    }
    first = TokenVault({"old": old}, "old").seal(
        {"access_token": "synthetic-access"}, binding
    )
    rotated = TokenVault({"old": old, "new": new}, "new").rewrap(first, binding)
    assert rotated["kid"] == "new"
    assert (
        TokenVault({"new": new}, "new").open(rotated, binding)["access_token"]
        == "synthetic-access"
    )
    for field, value in [
        ("workspace", "other"),
        ("connection", "b"),
        ("generation", 2),
        ("environment", "production"),
    ]:
        with pytest.raises(ProviderError, match="credential_unavailable"):
            TokenVault({"old": old}, "old").open(first, {**binding, field: value})
    for bad in (
        {**first, "v": 2},
        {**first, "kid": "absent"},
        {**first, "ciphertext": "AAAA"},
    ):
        with pytest.raises(ProviderError, match="credential_unavailable"):
            TokenVault({"old": old}, "old").open(bad, binding)


def test_pkce_s256_and_exact_callback_and_scopes():
    verifier, challenge = pkce()
    assert 43 <= len(verifier) <= 128
    assert challenge == b64(hashlib.sha256(verifier.encode()).digest())
    adapter = ReadOnlyAdapter(config(), Transport(response({})))
    parsed = urlsplit(adapter.authorization_url("state", challenge))
    query = parse_qs(parsed.query)
    assert parsed.netloc == "sandbox.toolost.com"
    assert query["redirect_uri"] == [
        "https://review-staging.spacemusic.io/api/integrations/toolost/callback"
    ]
    assert query["scope"] == ["read:profile read:releases read:sales"]
    assert query["code_challenge_method"] == ["S256"]
    assert "client_secret" not in query


@pytest.mark.parametrize(
    "url",
    [
        "https://spacemusic.io/api/integrations/toolost/callback",
        "https://review.spacemusic.io/api/integrations/toolost/callback",
        "https://review-staging.spacemusic.io/api/integrations/toolost/callback/",
        "https://review-staging.spacemusic.io/api/integrations/toolost/callback?next=https://example.com",
    ],
)
def test_callback_does_not_accept_bridge_or_other_environment(url):
    with pytest.raises(ProviderError, match="callback_mismatch"):
        config().validate_callback(url)


def test_disabled_default_and_no_live_transport():
    transport = Transport(response({}))
    adapter = ReadOnlyAdapter(Config(), transport)
    with pytest.raises(ProviderError, match="provider_disabled"):
        adapter.get("me", "synthetic", **hooks())
    assert transport.requests == []
    with pytest.raises(ProviderError, match="live_transport_not_implemented"):
        ReadOnlyAdapter(config(), object())
    assert "synthetic-secret" not in repr(config())


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
def test_feature_flag_requires_explicit_boolean(value):
    with pytest.raises(ValueError, match="invalid_provider_feature_flag"):
        Config(enabled=value)


@pytest.mark.parametrize(
    "resource",
    [
        "../me",
        "https://example.com",
        "releases/1?x=1",
        "releases/0",
        "analytics",
        "sales/tracks",
        "releases/1/distribute",
    ],
)
def test_only_minimal_allowlisted_resources(resource):
    transport = Transport(response({}))
    with pytest.raises(ProviderError, match="provider_resource_forbidden"):
        ReadOnlyAdapter(config(), transport).get(resource, "synthetic", **hooks())
    assert transport.requests == []


@pytest.mark.parametrize(
    "resource,key",
    [
        ("releases", "perPage"),
        ("sales/overview", "per_page"),
        ("sales/releases", "per_page"),
    ],
)
def test_pagination_case_is_resource_specific(resource, key):
    transport = Transport(response({"data": []}))
    ReadOnlyAdapter(config(), transport).get(resource, "synthetic", page=2, **hooks())
    assert transport.requests[0].query == {"page": 2, key: 100}
    assert transport.requests[0].method == "GET"
    assert "synthetic" not in repr(transport.requests[0])


@pytest.mark.parametrize(
    "body",
    [
        b'{"data":NaN}',
        b'{"data":[],"data":[]}',
        b"[]",
        b'{"data":Infinity}',
        b"not json",
    ],
)
def test_json_contract_rejects_nonfinite_duplicate_and_nonobject(body):
    with pytest.raises(ProviderError, match="provider_schema_invalid"):
        ReadOnlyAdapter(config(), Transport(response(body))).get(
            "me", "synthetic", **hooks()
        )


def test_decimal_lexical_precision_and_no_sample_semantics():
    body = b'{"data":[{"date":"2026-08-31","total":-123456789.123456789123456789,"currency":"USD","gross":true}]}'
    parsed = ReadOnlyAdapter(config(), Transport(response(body))).get(
        "sales/releases/1/overview", "synthetic", **hooks()
    )
    facts, _, _ = normalize_page(
        "sales/releases/1/overview", parsed, 1, max_records=100
    )
    payload = facts[0]["payload"]
    assert payload["amount"] == "-123456789.123456789123456789"
    assert payload["currency"] is None
    assert payload["period_kind"] == "unknown"
    assert payload["gross_net_basis"] is None
    assert payload["conclusions_allowed"] is False
    assert "valuation" not in payload


@pytest.mark.parametrize(
    "value",
    [
        True,
        0.1,
        "1.20",
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("1e100"),
        Decimal("1e-100"),
    ],
)
def test_no_float_string_nonfinite_or_unbounded_decimal(value):
    with pytest.raises(ProviderError):
        decimal_string(value)


def test_missing_amount_is_unknown_not_zero():
    facts, _, _ = normalize_page(
        "sales/releases/1/overview", {"data": [{}]}, 1, max_records=10
    )
    assert facts[0]["payload"]["amount"] is None
    assert facts[0]["payload"]["reported_date"] is None


def test_streamed_response_cap_and_elapsed_deadline():
    transport = Transport(
        Response(200, {"content-type": "application/json"}, [b"{}", b" "])
    )
    with pytest.raises(ProviderError, match="too_large"):
        ReadOnlyAdapter(replace(config(), max_response_bytes=2), transport).get(
            "me", "synthetic", **hooks()
        )
    ticks = iter([0, 31])
    with pytest.raises(ProviderError, match="provider_timeout"):
        ReadOnlyAdapter(
            config(), Transport(response({})), monotonic=lambda: next(ticks)
        ).get("me", "synthetic", **hooks())


@pytest.mark.parametrize(
    "status,body,code",
    [
        (401, {}, "provider_unauthorized"),
        (403, {}, "provider_scope_denied"),
        (404, {}, "provider_resource_missing"),
        (500, {}, "provider_unavailable"),
        (429, {"error": "quota_exceeded"}, "provider_quota_exceeded"),
        (400, {"error": "invalid_grant"}, "reauth_required"),
        (422, {"secret": "must-not-echo"}, "provider_request_rejected"),
    ],
)
def test_sanitized_errors(status, body, code):
    with pytest.raises(ProviderError) as caught:
        ReadOnlyAdapter(config(), Transport(response(body, status))).get(
            "me", "synthetic", **hooks()
        )
    assert str(caught.value) == code


@pytest.mark.parametrize(
    "retry,expected", [("17", 17), ("Fri, 18 Sep 2026 12:00:30 GMT", 30), ("bad", 60)]
)
def test_retry_after_seconds_or_http_date(retry, expected):
    with pytest.raises(ProviderError) as caught:
        ReadOnlyAdapter(
            config(), Transport(response({}, 429, {"Retry-After": retry}))
        ).get("me", "synthetic", **hooks())
    assert caught.value.retry_after == expected


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": "read:catalog"},
        {"scope": None},
        {"refresh_token": None},
        {"expires_in": True},
        {"token_type": 12},
    ],
)
def test_token_contract_is_explicit(changes):
    tokens = {
        "access_token": "synthetic-access",
        "refresh_token": "synthetic-refresh",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "read:profile read:releases read:sales",
        **changes,
    }
    with pytest.raises(ProviderError):
        ReadOnlyAdapter(config(), Transport(response(tokens))).tokens(
            code="synthetic-code", verifier="synthetic-verifier", **hooks()
        )
