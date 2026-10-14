import asyncio
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from test_operations_config import configuration
from test_operations_gates import NOW, ready_states, request

from services.catalog_review.operations.config import ConfigurationError
from services.catalog_review.operations.gates import LaunchBlocked
from services.catalog_review.operations.runtime import (
    REQUIRED_ADAPTERS,
    AdapterBinding,
    GuardedMailDispatcher,
    ProbeResult,
    build_runtime,
)


def bindings(config):
    result = {}
    for name, methods in REQUIRED_ADAPTERS.items():
        value = (
            SimpleNamespace(
                **{method: (lambda *a, **k: "called") for method in methods}
            )
            if methods
            else lambda: None
        )
        result[name] = AdapterBinding(
            value,
            "synthetic" if config.synthetic_staging else "live",
            lambda: ProbeResult(True, NOW, config.generation, config.fingerprint),
        )
    return result


async def inner(scope, receive, send):
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b""})


def build(config=None, supplied=None, manifest=True, **kwargs):
    config = config or configuration()
    evidence, _, restore = ready_states(config)
    return build_runtime(
        config,
        adapters=bindings(config) if supplied is None else supplied,
        app_builder=lambda **_: inner,
        restore_provider=lambda: restore,
        manifest=evidence if manifest else None,
        clock=lambda: NOW,
        **kwargs,
    )


@pytest.mark.parametrize("missing", sorted(REQUIRED_ADAPTERS))
def test_every_missing_adapter_blocks_and_does_not_call_builder(missing):
    config = configuration()
    supplied = bindings(config)
    supplied.pop(missing)

    def forbidden(**_):
        raise AssertionError("Incomplete app must not be built")

    app = build_runtime(
        config, adapters=supplied, app_builder=forbidden, restore_provider=lambda: None
    )
    assert "adapter_" + missing in app.startup_blockers
    assert request(app)[0] == 503


def test_production_rejects_synthetic_binding_and_plain_boolean_probe():
    config = configuration()
    supplied = bindings(config)
    supplied["identity"] = replace(supplied["identity"], mode="synthetic")
    assert request(build(supplied=supplied))[0] == 503
    supplied = bindings(config)
    supplied["identity"] = replace(supplied["identity"], probe=lambda: True)
    assert request(build(supplied=supplied))[0] == 503


def test_manifest_never_overrides_failed_stale_or_wrong_generation_probe():
    config = configuration()
    for observation in (
        ProbeResult(False, NOW, config.generation, config.fingerprint),
        ProbeResult(
            True, NOW - timedelta(seconds=31), config.generation, config.fingerprint
        ),
        ProbeResult(True, NOW, "old-generation", config.fingerprint),
        ProbeResult(True, NOW, config.generation, "wrong-config"),
    ):
        supplied = bindings(config)
        supplied["storage"] = replace(supplied["storage"], probe=lambda: observation)
        assert request(build(supplied=supplied))[0] == 503


def test_mail_dispatch_is_guarded_outside_http_as_well():
    app = build(manifest=False)
    with pytest.raises(LaunchBlocked):
        app.adapters["mail"].dispatch("workspace", "invitation")
    with pytest.raises(LaunchBlocked):
        app.adapters["mail"].dispatch_retention("workspace", 1)
    allowed = build()
    assert allowed.adapters["mail"].dispatch("workspace", "invitation") == "called"
    assert allowed.adapters["mail"].dispatch_retention("workspace", 1) == "called"
    with pytest.raises(TypeError):
        allowed.adapters["mail"] = object()


@pytest.mark.parametrize("method", ["dispatch_retention", "refresh_retention"])
def test_retention_forwards_recheck_gate_before_calling_dispatcher(method):
    events = []
    allowed = True
    result = object()

    def require_ready():
        events.append("gate")
        if not allowed:
            raise LaunchBlocked("production_invitations_blocked")

    def forward(*args, **kwargs):
        events.append((method, args, kwargs))
        return result

    guarded = GuardedMailDispatcher(SimpleNamespace(**{method: forward}), require_ready)
    assert getattr(guarded, method)("workspace", activity_version=7) is result
    allowed = False
    with pytest.raises(LaunchBlocked):
        getattr(guarded, method)("workspace", activity_version=7)
    assert events == ["gate", (method, ("workspace",), {"activity_version": 7}), "gate"]


@pytest.mark.parametrize("method", ["dispatch_retention", "refresh_retention"])
def test_missing_retention_mail_method_blocks_runtime_construction(method):
    config = configuration()
    supplied = bindings(config)
    methods = ("dispatch", "refresh", "dispatch_retention", "refresh_retention")
    supplied["mail"] = replace(
        supplied["mail"],
        value=SimpleNamespace(
            **{name: (lambda *a, **k: None) for name in methods if name != method}
        ),
    )
    app = build(supplied=supplied)
    assert "adapter_mail" in app.startup_blockers
    assert request(app)[0] == 503


def test_synthetic_staging_supports_end_to_end_without_production_evidence():
    config = replace(configuration("staging"), synthetic_staging=True)
    app = build(config=config, manifest=False)
    assert (
        request(
            app,
            host=b"review-staging.spacemusic.io",
            origin=b"https://review-staging.spacemusic.io",
        )[0]
        == 204
    )
    assert app.adapters["mail"].dispatch("synthetic", "only") == "called"
    app.require_invitations()
    with pytest.raises(ConfigurationError):
        replace(configuration(), synthetic_staging=True).validate()
    supplied = bindings(config)
    supplied["mail"] = replace(supplied["mail"], mode="live")
    assert (
        request(
            build(config=config, supplied=supplied, manifest=False),
            host=b"review-staging.spacemusic.io",
        )[0]
        == 503
    )


def webhook_request(
    app, *, path="/api/intake/typeform", method="POST", headers=(), query=b""
):
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"{}"}

    async def send(message):
        messages.append(message)

    asyncio.run(
        app(
            {
                "type": "http",
                "scheme": "https",
                "path": path,
                "method": method,
                "query_string": query,
                "headers": [(b"host", b"review.spacemusic.io"), *headers],
            },
            receive,
            send,
        )
    )
    return messages[0]["status"]


def test_webhook_exception_requires_actual_binding_and_exact_server_request():
    config = configuration()
    supplied = bindings(config)
    supplied["typeform_intake"] = AdapterBinding(
        SimpleNamespace(receive_typeform=lambda body, signature: None),
        "live",
        lambda: ProbeResult(True, NOW, config.generation, config.fingerprint),
    )
    app = build(supplied=supplied)
    assert webhook_request(build()) == 403
    assert webhook_request(app) == 204
    assert webhook_request(app, path="/api/intake/typeform/") == 403
    assert webhook_request(app, path="/api/portal/session") == 403
    assert webhook_request(app, method="PUT") == 403
    assert webhook_request(app, query=b"extra=true") == 403
    for header in (b"sec-fetch-site", b"Sec-Fetch-Mode", b"sec-fetch-dest", b"origin"):
        assert webhook_request(app, headers=[(header, b"")]) == 403
    assert webhook_request(app, headers=[(b"origin", b"https://evil.test")]) == 403
    assert webhook_request(app, headers=[(b"origin", b"https://spacemusic.io")]) == 403
    supplied["typeform_intake"] = replace(
        supplied["typeform_intake"], probe=lambda: False
    )
    assert webhook_request(build(supplied=supplied)) == 403


def test_callback_get_is_delegated_to_inner_state_nonce_validation():
    assert (
        webhook_request(
            build(),
            path="/api/staff/oidc/callback",
            method="GET",
            query=b"state=opaque&code=opaque",
        )
        == 204
    )
