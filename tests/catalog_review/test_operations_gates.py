import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from test_operations_config import configuration

from services.catalog_review.operations.asgi import GuardedApplication
from services.catalog_review.operations.gates import (
    CHECKS,
    EVIDENCE,
    Evidence,
    LaunchBlocked,
    LaunchGate,
    LaunchManifest,
    RestoreState,
    RuntimeState,
)

NOW = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)


def ready_states(config=None):
    config = config or configuration()
    manifest = LaunchManifest(
        config.environment,
        config.generation,
        config.fingerprint,
        config.release_sha256,
        "Synthetic legal evidence in offline unit test",
        "TEST-NOT-A-REAL-ENTITY",
        "Test operator",
        1700,
        True,
        tuple(
            (
                name,
                Evidence(
                    "b" * 64,
                    "Test reviewer",
                    NOW - timedelta(days=1),
                    NOW + timedelta(days=1),
                ),
            )
            for name in sorted(EVIDENCE)
        ),
    )
    runtime = RuntimeState(
        config.generation,
        config.fingerprint,
        NOW,
        tuple((name, True) for name in sorted(CHECKS)),
    )
    restore = RestoreState(
        config.generation, config.generation, 42, 42, NOW, True, True
    )
    return manifest, runtime, restore


def test_no_manifest_or_integrations_can_open_invitations():
    gate = LaunchGate(configuration())
    decision = gate.evaluate(now=NOW)
    assert not decision.ready and not decision.invitations_allowed
    with pytest.raises(LaunchBlocked):
        gate.require_invitations(now=NOW)


def test_complete_current_evidence_allows_only_production():
    for environment in ("production", "staging"):
        config = configuration(environment)
        manifest, runtime, restore = ready_states(config)
        decision = LaunchGate(config, manifest).evaluate(
            now=NOW, runtime=runtime, restore=restore
        )
        assert decision.ready
        assert decision.invitations_allowed is (environment == "production")


@pytest.mark.parametrize("name", sorted(EVIDENCE))
def test_every_production_evidence_record_is_required(name):
    manifest, runtime, restore = ready_states()
    manifest = replace(
        manifest, evidence=tuple(item for item in manifest.evidence if item[0] != name)
    )
    decision = LaunchGate(configuration(), manifest).evaluate(
        now=NOW, runtime=runtime, restore=restore
    )
    assert "evidence_" + name in decision.blockers
    assert not decision.invitations_allowed


@pytest.mark.parametrize("name", sorted(CHECKS))
@pytest.mark.parametrize("bad", [False, "true", 1, None])
def test_real_integration_checks_require_strict_true(name, bad):
    manifest, runtime, restore = ready_states()
    runtime = replace(
        runtime,
        checks=tuple((key, bad if key == name else val) for key, val in runtime.checks),
    )
    assert (
        not LaunchGate(configuration(), manifest)
        .evaluate(now=NOW, runtime=runtime, restore=restore)
        .ready
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation", "8f402b34-49b3-400c-a800-17c15ff96161"),
        ("config_sha256", "c" * 64),
        ("release_sha256", "d" * 64),
        ("legal_name", ""),
        ("organization_number", ""),
        ("operator", ""),
        ("approved_monthly_sek", 2001),
        ("approved_monthly_sek", 0),
        ("invitations_approved", "true"),
        ("invitations_approved", False),
    ],
)
def test_manifest_fail_closed(field, value):
    manifest, runtime, restore = ready_states()
    manifest = replace(manifest, **{field: value})
    assert (
        not LaunchGate(configuration(), manifest)
        .evaluate(now=NOW, runtime=runtime, restore=restore)
        .ready
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"generation": "8f402b34-49b3-400c-a800-17c15ff96161"},
        {"session_generation": "8f402b34-49b3-400c-a800-17c15ff96161"},
        {"journal_head": 43},
        {"replayed_through": 43},
        {"journal_head": True},
        {"objects_verified": False},
        {"verified_at": NOW - timedelta(seconds=31)},
        {"source_tombstones_reconciled": False},
        {"source_tombstones_reconciled": 1},
        {"verified_at": NOW + timedelta(seconds=1)},
    ],
)
def test_restore_must_match_external_generation_and_latest_journal(changes):
    manifest, runtime, restore = ready_states()
    assert (
        not LaunchGate(configuration(), manifest)
        .evaluate(now=NOW, runtime=runtime, restore=replace(restore, **changes))
        .ready
    )


def test_runtime_and_evidence_expiration_never_cache_allow():
    manifest, runtime, restore = ready_states()
    gate = LaunchGate(configuration(), manifest)
    assert gate.evaluate(now=NOW, runtime=runtime, restore=restore).ready
    assert not gate.evaluate(
        now=NOW + timedelta(seconds=31), runtime=runtime, restore=restore
    ).ready
    expired = replace(manifest.evidence[0][1], expires_at=NOW)
    gate.manifest = replace(
        manifest, evidence=((manifest.evidence[0][0], expired),) + manifest.evidence[1:]
    )
    assert not gate.evaluate(now=NOW, runtime=runtime, restore=restore).ready
    assert not gate.evaluate(
        now=NOW.replace(tzinfo=None), runtime=runtime, restore=restore
    ).ready


def request(
    app,
    path="/api/portal/session",
    method="POST",
    host=b"review.spacemusic.io",
    origin=b"https://review.spacemusic.io",
    scheme="https",
):
    sent = []

    async def receive():
        raise AssertionError("Blocked request body must not be read")

    async def send(message):
        sent.append(message)

    asyncio.run(
        app(
            {
                "type": "http",
                "scheme": scheme,
                "path": path,
                "method": method,
                "headers": [(b"host", host), (b"origin", origin)],
            },
            receive,
            send,
        )
    )
    return sent[0]["status"], sent[-1].get("body", b"")


def test_default_asgi_never_ready_even_with_complete_manifest():
    manifest, runtime, restore = ready_states()
    app = GuardedApplication(
        configuration(),
        LaunchGate(configuration(), manifest),
        status_provider=lambda: (runtime, restore),
        clock=lambda: NOW,
    )
    assert request(app, "/health/live", "GET")[0] == 200
    assert request(app, "/health/ready", "GET") == (503, b'{"status":"blocked"}')
    assert request(app)[0] == 503
    assert request(app, "/health/live", "GET", scheme="http")[0] == 400


def test_asgi_integrated_requests_still_require_exact_origin_and_current_health():
    manifest, runtime, restore = ready_states()

    async def real_app(scope, receive, send):
        await GuardedApplication._respond(send, 200, "integrated")

    app = GuardedApplication(
        configuration(),
        LaunchGate(configuration(), manifest),
        application=real_app,
        status_provider=lambda: (runtime, restore),
        clock=lambda: NOW,
    )
    assert request(app)[0] == 200
    assert request(app, origin=b"https://spacemusic.io")[0] == 403
    assert request(app, host=b"review-staging.spacemusic.io")[0] == 400
    app.clock = lambda: NOW + timedelta(seconds=31)
    assert request(app)[0] == 503


def test_status_collector_failure_is_redacted():
    def failed():
        raise RuntimeError("secret-probe-error")

    app = GuardedApplication(
        configuration(),
        LaunchGate(configuration()),
        application=object(),
        status_provider=failed,
    )
    status, body = request(app)
    assert status == 503 and b"secret" not in body
