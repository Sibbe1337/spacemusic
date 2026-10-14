import json
import secrets
import socket
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Event
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import psycopg2
import pytest
from conftest import draft, owner_cursor, sign_in
from psycopg2.extras import RealDictCursor

from services.catalog_review.providers.adapter import ReadOnlyAdapter, Response
from services.catalog_review.providers.contracts import Config, ProviderError
from services.catalog_review.providers.crypto import TokenVault
from services.catalog_review.providers.erasure import (
    ERASURE_TABLES,
    ProviderErasureParticipant,
)
from services.catalog_review.providers.repository import (
    Repository,
    ReviewSessionAuthority,
)
from services.catalog_review.providers.service import TooLostService
from services.catalog_review.security import ReviewError


@pytest.fixture(autouse=True)
def no_provider_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("No network transport allowed")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def reply(value, status=200, headers=None):
    body = value if isinstance(value, bytes) else json.dumps(value).encode()
    return Response(
        status, {"content-type": "application/json", **(headers or {})}, [body]
    )


def page(ids=(1,), *, number=1, size=1, count=None):
    total = len(ids) if count is None else count
    return {
        "data": [
            {
                "id": identity,
                "title": f"Synthetic {identity}",
                "upc": None,
                "audio_url": "https://example.com/not-fetched",
            }
            for identity in ids
        ],
        "currentPage": number,
        "perPage": size,
        "totalItems": total,
        "totalPages": (total + size - 1) // size,
    }


class FakeProvider:
    offline = True

    def __init__(self):
        self.requests = []
        self.script = {}
        self.on_send = None

    def send(self, request):
        self.requests.append(request)
        if self.on_send:
            self.on_send(request)
        resource = "token" if request.method == "POST" else request.url.split("/v1/")[1]
        if self.script.get(resource):
            result = self.script[resource].pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        if resource == "token":
            return reply(
                {
                    "access_token": "synthetic-access-" + str(len(self.requests)),
                    "refresh_token": "synthetic-refresh-" + str(len(self.requests)),
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "scope": "read:profile read:releases read:sales",
                }
            )
        if resource == "me":
            return reply({"data": {"id": 42, "email": "discard@example.com"}})
        if resource == "releases":
            return reply(page())
        return reply(
            b'{"data":[{"date":"2026-08-31","total":0.1000000000000000001},{"date":"2026-08-31","total":-0.02}]}'
        )


@pytest.fixture
def setup(backend):
    with owner_cursor(backend) as db:
        db.execute(Path("services/catalog_review/providers/schema.sql").read_text())
    configuration = Config(
        enabled=True, client_id="synthetic-client", client_secret="synthetic-secret"
    )
    provider = FakeProvider()
    vault = TokenVault({"test-key-v1": secrets.token_bytes(32)}, "test-key-v1")
    repository = Repository(
        backend.db,
        ReviewSessionAuthority(backend),
        configuration,
        backend.clock,
        workspace_guard=backend._active,
    )
    service = TooLostService(
        repository, vault, ReadOnlyAdapter(configuration, provider)
    )
    workspace, session, _ = sign_in(backend)
    return backend, service, provider, workspace, session


def begin(service, session):
    url = service.start_oauth(session)["authorization_url"]
    return parse_qs(urlsplit(url).query)["state"][0]


def connected(service, session):
    state = begin(service, session)
    result = service.callback(
        session,
        state=state,
        code="synthetic-code",
        callback_uri=service.config.callback,
    )
    service.confirm_account(session, result["connection_id"], result["account_id"])
    return result["connection_id"]


def connection_row(backend, workspace):
    with owner_cursor(backend) as db:
        db.execute(
            "SELECT * FROM toolost_connections WHERE workspace_id=%s", (workspace,)
        )
        return db.fetchone()


def expire_access(backend, workspace):
    with owner_cursor(backend) as db:
        db.execute(
            "UPDATE toolost_connections SET access_expires_at=%s WHERE workspace_id=%s",
            (backend.clock(), workspace),
        )


def run_to_end(service, workspace, run_id):
    for _ in range(10):
        status = service.step_import(workspace, run_id)
        if status["status"] in ("complete", "partial", "cancelled"):
            return status
    raise AssertionError("Import failed to terminate")


def test_oauth_ciphertext_single_use_and_explicit_confirmation(setup):
    backend, service, provider, workspace, session = setup
    state = begin(service, session)
    assert not provider.requests
    with owner_cursor(backend) as db:
        db.execute("SELECT * FROM toolost_oauth_attempts")
        attempt = db.fetchone()
    assert state not in json.dumps(attempt, default=str)
    assert attempt["verifier"]["kid"] == "test-key-v1"
    result = service.callback(
        session,
        state=state,
        code="synthetic-code",
        callback_uri=service.config.callback,
    )
    assert result["status"] == "awaiting_confirmation"
    with pytest.raises(ProviderError, match="connection_unavailable"):
        service.start_import(session, result["connection_id"], uuid4())
    with pytest.raises(ProviderError, match="oauth_state_unavailable"):
        service.callback(
            session,
            state=state,
            code="synthetic-code",
            callback_uri=service.config.callback,
        )
    assert len(provider.requests) == 2
    assert "synthetic-access" not in json.dumps(
        connection_row(backend, workspace), default=str
    )
    with pytest.raises(ProviderError, match="account_confirmation_mismatch"):
        service.confirm_account(session, result["connection_id"], "43")
    service.confirm_account(session, result["connection_id"], "42")
    assert (
        service.confirm_account(session, result["connection_id"], "42")["status"]
        == "active"
    )


def test_oauth_session_workspace_environment_and_expiry_binding(setup):
    backend, service, provider, workspace, session = setup
    state = begin(service, session)
    _, foreign, _ = sign_in(backend, "foreign", "foreign@example.com")
    with pytest.raises(ProviderError):
        service.callback(
            foreign, state=state, code="synthetic", callback_uri=service.config.callback
        )
    other_session = workspace + "." + secrets.token_urlsafe(32)
    with owner_cursor(backend) as db:
        db.execute(
            "SELECT principal_id FROM memberships WHERE workspace_id=%s", (workspace,)
        )
        principal = db.fetchone()["principal_id"]
        db.execute(
            "INSERT INTO sessions VALUES(%s,%s,%s,false,%s)",
            (
                workspace,
                backend._hash("session", other_session),
                principal,
                backend.clock() + timedelta(hours=1),
            ),
        )
    with pytest.raises(ProviderError, match="oauth_binding_mismatch"):
        service.callback(
            other_session,
            state=state,
            code="synthetic",
            callback_uri=service.config.callback,
        )
    configuration = replace(service.config, environment="production")
    other = TooLostService(
        Repository(
            backend.db,
            ReviewSessionAuthority(backend),
            configuration,
            backend.clock,
            workspace_guard=backend._active,
        ),
        service.vault,
        ReadOnlyAdapter(configuration, provider),
    )
    with pytest.raises(ProviderError, match="oauth_binding_mismatch"):
        other.callback(
            session, state=state, code="synthetic", callback_uri=configuration.callback
        )
    backend.clock.advance(600)
    with pytest.raises(ProviderError, match="oauth_state_unavailable"):
        service.callback(
            session, state=state, code="synthetic", callback_uri=service.config.callback
        )
    assert not provider.requests


def test_oauth_denial_consumes_state_without_provider_request(setup):
    backend, service, provider, workspace, session = setup
    state = begin(service, session)
    with pytest.raises(ProviderError, match="oauth_denied"):
        service.callback(
            session,
            state=state,
            error="untrusted provider detail",
            callback_uri=service.config.callback,
        )
    assert connection_row(backend, workspace)["status"] == "reauth_required"
    assert not provider.requests


def test_unknown_exchange_is_not_replayed(setup):
    backend, service, provider, workspace, session = setup
    state = begin(service, session)
    provider.script["token"] = [TimeoutError("synthetic secret must not escape")]
    with pytest.raises(ProviderError, match="provider_unavailable"):
        service.callback(
            session, state=state, code="synthetic", callback_uri=service.config.callback
        )
    with pytest.raises(ProviderError, match="oauth_state_unavailable"):
        service.callback(
            session, state=state, code="synthetic", callback_uri=service.config.callback
        )
    assert len(provider.requests) == 1
    assert connection_row(backend, workspace)["credentials"] is None


def test_disconnect_fences_late_oauth_exchange(setup):
    backend, service, provider, workspace, session = setup
    state = begin(service, session)
    connection_id = str(connection_row(backend, workspace)["connection_id"])
    provider.on_send = lambda _: service.disconnect(session, connection_id)
    with pytest.raises(ProviderError):
        service.callback(
            session, state=state, code="synthetic", callback_uri=service.config.callback
        )
    assert connection_row(backend, workspace)["status"] == "disconnected"
    assert connection_row(backend, workspace)["credentials"] is None
    assert len(provider.requests) == 1


def test_refresh_is_singleflight_and_token_pair_versioned(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    expire_access(backend, workspace)
    entered, release = Event(), Event()

    def block(request):
        if request.method == "POST":
            entered.set()
            assert release.wait(5)

    provider.on_send = block
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(service.refresh, session, identity)
        assert entered.wait(5)
        try:
            with pytest.raises(ProviderError, match="refresh_busy"):
                service.refresh(session, identity)
        finally:
            release.set()
        assert first.result()["token_version"] == 2
    assert (
        len([request for request in provider.requests if request.method == "POST"]) == 2
    )
    row = connection_row(backend, workspace)
    assert row["refresh_lease"] is None
    assert row["credentials"]["kid"] == "test-key-v1"


@pytest.mark.parametrize(
    "outcome", [TimeoutError("unknown ack"), reply({"error": "invalid_grant"}, 400)]
)
def test_refresh_unknown_outcome_or_invalid_grant_needs_reconnect(setup, outcome):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    expire_access(backend, workspace)
    provider.script["token"] = [outcome]
    with pytest.raises(ProviderError):
        service.refresh(session, identity)
    assert connection_row(backend, workspace)["status"] == "reauth_required"
    count = len(provider.requests)
    with pytest.raises(ProviderError, match="reauth_required"):
        service.refresh(session, identity)
    assert len(provider.requests) == count


def test_expired_refresh_lease_cannot_reuse_rotating_token(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    with owner_cursor(backend) as db:
        db.execute(
            "UPDATE toolost_connections SET refresh_lease=%s,refresh_until=%s WHERE workspace_id=%s",
            (str(uuid4()), backend.clock() - timedelta(seconds=1), workspace),
        )
    count = len(provider.requests)
    with pytest.raises(ProviderError, match="reauth_required"):
        service.refresh(session, identity)
    assert len(provider.requests) == count
    assert connection_row(backend, workspace)["credentials"] is None


def test_disconnect_fences_refresh_and_key_rewrap_preserves_version(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    service.vault = TokenVault(
        {**service.vault._keys, "test-key-v2": secrets.token_bytes(32)}, "test-key-v2"
    )
    assert service.rewrap_credentials(session, identity) == {
        "key_version": "test-key-v2"
    }
    assert connection_row(backend, workspace)["token_version"] == 1
    expire_access(backend, workspace)
    provider.on_send = lambda _: service.disconnect(session, identity)
    with pytest.raises(ProviderError):
        service.refresh(session, identity)
    assert connection_row(backend, workspace)["status"] == "disconnected"
    assert connection_row(backend, workspace)["credentials"] is None


def test_import_resumes_exact_checkpoint_and_returns_decimal_versioned_facts(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    provider.script["releases"] = [
        reply(page((1,), count=2)),
        reply(page((2,), number=2, count=2)),
    ]
    request_id = str(uuid4())
    run = service.start_import(session, identity, request_id, [1])
    assert (
        service.start_import(session, identity, request_id, ["1"])["run_id"]
        == run["run_id"]
    )
    with pytest.raises(ProviderError, match="import_request_conflict"):
        service.start_import(session, identity, request_id, [2])
    first = service.step_import(workspace, run["run_id"])
    assert first["pages"] == 1 and first["status"] == "queued"
    rebuilt = TooLostService(
        Repository(
            backend.db,
            ReviewSessionAuthority(backend),
            service.config,
            backend.clock,
            workspace_guard=backend._active,
        ),
        service.vault,
        service.adapter,
    )
    assert run_to_end(rebuilt, workspace, run["run_id"])["status"] == "complete"
    snapshot = rebuilt.snapshot(session, run["run_id"])
    values = [
        record["payload"]["amount"]
        for record in snapshot["facts"]
        if record["payload"]["kind"] == "reported_amount"
    ]
    assert values == ["0.1000000000000000001", "-0.02"]
    assert snapshot["coverage"]["conclusions_allowed"] is False
    assert "audio_url" not in json.dumps(snapshot)
    assert "discard@example.com" not in json.dumps(snapshot)
    assert [
        request.query["page"]
        for request in provider.requests
        if request.url.endswith("/releases")
    ] == [1, 2]
    count = len(provider.requests)
    assert (
        service.start_import(session, identity, request_id, [1])["status"] == "complete"
    )
    assert len(provider.requests) == count


def test_import_versions_do_not_replace_or_sum_old_facts(setup):
    _, service, _, workspace, session = setup
    identity = connected(service, session)
    first = service.start_import(session, identity, uuid4(), [1])
    run_to_end(service, workspace, first["run_id"])
    snapshot = service.snapshot(session, first["run_id"])
    second = service.start_import(session, identity, uuid4(), [1])
    run_to_end(service, workspace, second["run_id"])
    assert second["run_id"] != first["run_id"]
    assert service.snapshot(session, first["run_id"]) == snapshot


@pytest.mark.parametrize(
    "second,error",
    [
        (page((1,), number=2, count=2), "provider_repeated_page"),
        (page((2,), number=2, count=3), "provider_pagination_changed"),
    ],
)
def test_changing_or_repeated_pages_leave_partial_evidence(setup, second, error):
    _, service, provider, workspace, session = setup
    identity = connected(service, session)
    provider.script["releases"] = [reply(page((1,), count=2)), reply(second)]
    run = service.start_import(session, identity, uuid4())
    final = run_to_end(service, workspace, run["run_id"])
    assert (
        final["status"] == "partial" and final["error"] == error and final["pages"] == 1
    )
    with pytest.raises(ProviderError, match="import_not_complete"):
        service.snapshot(session, run["run_id"])


def test_checkpoint_rollback_and_lost_commit_ack_are_reconcilable(setup, monkeypatch):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4())
    original = service._commit_page

    def crash(*args):
        raise RuntimeError("simulated worker crash before transaction")

    monkeypatch.setattr(service, "_commit_page", crash)
    with pytest.raises(RuntimeError):
        service.step_import(workspace, run["run_id"])
    assert service.import_status(session, run["run_id"])["pages"] == 0
    backend.clock.advance(service.config.lease_seconds + 1)

    def lost_ack(*args):
        original(*args)
        raise RuntimeError("simulated lost acknowledgement after durable commit")

    monkeypatch.setattr(service, "_commit_page", lost_ack)
    with pytest.raises(RuntimeError):
        service.step_import(workspace, run["run_id"])
    before = len(provider.requests)
    assert service.step_import(workspace, run["run_id"])["status"] == "complete"
    assert len(provider.requests) == before


def test_concurrent_start_and_step_do_not_duplicate_import(setup):
    _, service, provider, workspace, session = setup
    identity = connected(service, session)
    request_id = uuid4()
    with ThreadPoolExecutor(2) as pool:
        runs = list(
            pool.map(
                lambda _: service.start_import(session, identity, request_id), range(2)
            )
        )
    assert runs[0]["run_id"] == runs[1]["run_id"]
    entered, release = Event(), Event()

    def block(request):
        if request.method == "GET" and request.url.endswith("/releases"):
            entered.set()
            assert release.wait(5)

    provider.on_send = block
    with ThreadPoolExecutor(2) as pool:
        future = pool.submit(service.step_import, workspace, runs[0]["run_id"])
        assert entered.wait(5)
        try:
            with pytest.raises(ProviderError, match="import_busy"):
                service.step_import(workspace, runs[0]["run_id"])
        finally:
            release.set()
        assert future.result()["status"] == "complete"


def test_worker_session_independence_but_current_membership_required(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4())
    backend.logout(session)
    assert service.step_import(workspace, run["run_id"])["status"] == "complete"
    with pytest.raises(ReviewError):
        service.snapshot(session, run["run_id"])
    with owner_cursor(backend) as db:
        db.execute(
            "UPDATE memberships SET active=false WHERE workspace_id=%s", (workspace,)
        )
    count = len(provider.requests)
    with pytest.raises(ProviderError, match="import_authorization_revoked"):
        service.step_import(workspace, run["run_id"])
    assert len(provider.requests) == count


def test_disconnect_or_deletion_blocks_inflight_commit(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4())
    provider.on_send = lambda _: service.disconnect(session, identity)
    assert service.step_import(workspace, run["run_id"])["status"] == "cancelled"
    with owner_cursor(backend) as db:
        db.execute(
            "SELECT count(*) AS n FROM toolost_source_facts WHERE workspace_id=%s",
            (workspace,),
        )
        assert db.fetchone()["n"] == 0
    backend.request_deletion(session)
    count = len(provider.requests)
    with pytest.raises(ProviderError, match="workspace_unavailable"):
        service.step_import(workspace, run["run_id"])
    assert len(provider.requests) == count


def test_global_quota_shared_across_workspaces_and_null_is_unknown(setup):
    backend, service, provider, _, session = setup
    identity = connected(service, session)
    assert identity
    _, other, _ = sign_in(backend, "second", "second@example.com")
    connected(service, other)
    with owner_cursor(backend) as db:
        db.execute("SELECT * FROM toolost_quota")
        row = db.fetchone()
    assert row["month_calls"] == 4
    assert row["provider_remaining"] is None
    service.repo.observe_quota({"x-api-quota-remaining": "0"})
    with pytest.raises(ProviderError, match="provider_quota_exceeded"):
        service.repo.reserve_call()
    assert len(provider.requests) == 4


def test_429_pause_and_bounded_5xx_retries(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    provider.script["releases"] = [
        reply({}, 429, {"Retry-After": "17"}),
        reply({}, 503),
        reply({}, 503),
    ]
    run = service.start_import(session, identity, uuid4())
    assert service.step_import(workspace, run["run_id"])["status"] == "retryable"
    count = len(provider.requests)
    with pytest.raises(ProviderError, match="import_busy"):
        service.step_import(workspace, run["run_id"])
    assert len(provider.requests) == count
    backend.clock.advance(18)
    assert service.step_import(workspace, run["run_id"])["status"] == "retryable"
    backend.clock.advance(6)
    assert service.step_import(workspace, run["run_id"])["status"] == "partial"


def test_401_refresh_only_once_and_import_budget_counts_refresh(setup):
    _, service, provider, workspace, session = setup
    identity = connected(service, session)
    provider.script["releases"] = [reply({}, 401), reply({}, 401)]
    run = service.start_import(session, identity, uuid4())
    status = service.step_import(workspace, run["run_id"])
    assert status["status"] == "partial"
    assert status["calls"] == 3
    assert (
        len([request for request in provider.requests if request.method == "POST"]) == 2
    )


def test_row_level_isolation_immutable_facts_and_no_truncate(setup):
    backend, service, _, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4(), [1])
    run_to_end(service, workspace, run["run_id"])
    other_workspace, other, _ = sign_in(backend, "other", "other@example.com")
    with backend.db.transaction(other_workspace) as db:
        db.execute(
            "SELECT * FROM toolost_source_facts WHERE workspace_id=%s", (workspace,)
        )
        assert db.fetchall() == []
    with pytest.raises(ProviderError, match="import_unavailable"):
        service.snapshot(other, run["run_id"])
    for statement in (
        "UPDATE toolost_source_facts SET amount=0",
        "DELETE FROM toolost_source_facts",
        "TRUNCATE toolost_source_facts",
    ):
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            with backend.db.transaction(workspace) as db:
                db.execute(statement)


def test_document_pilot_unmodified_and_provider_disabled_default(setup):
    backend, service, provider, workspace, session = setup
    configuration = replace(service.config, enabled=False)
    disabled = TooLostService(
        Repository(
            backend.db,
            ReviewSessionAuthority(backend),
            configuration,
            backend.clock,
            workspace_guard=backend._active,
        ),
        service.vault,
        ReadOnlyAdapter(configuration, provider),
    )
    with pytest.raises(ProviderError, match="provider_disabled"):
        disabled.start_oauth(session)
    backend.save_draft(session, {"revision": 0, "draft": draft()})
    backend.submit(
        session, {"revision": 1, "request_id": str(uuid4()), "consent": True}
    )
    assert backend.view(session)["review_status"] == "submitted"
    assert not provider.requests


class Journal:
    def __init__(self):
        self.deleted = set()
        self.suppressed = set()
        self.unavailable = False

    def contains(self, workspace):
        if self.unavailable:
            raise RuntimeError("synthetic journal unavailable")
        return workspace in self.deleted

    def suppresses(self, source):
        if self.unavailable:
            raise RuntimeError("synthetic journal unavailable")
        return source in self.suppressed


def test_external_guard_is_required(setup):
    backend, service, _, _, _ = setup
    with pytest.raises(ValueError, match="external_workspace_guard_required"):
        Repository(
            backend.db,
            ReviewSessionAuthority(backend),
            service.config,
            backend.clock,
            workspace_guard=None,
        )


@pytest.mark.parametrize("unavailable", [False, True])
def test_restored_active_database_cannot_override_external_journal(setup, unavailable):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4())
    backend.deletion_journal = Journal()
    backend.deletion_journal.deleted.add(workspace)
    backend.deletion_journal.unavailable = unavailable
    with owner_cursor(backend) as db:
        db.execute("SELECT status FROM workspaces WHERE workspace_id=%s", (workspace,))
        assert db.fetchone()["status"] == "active"
    count = len(provider.requests)
    with pytest.raises((ProviderError, RuntimeError)):
        service.step_import(workspace, run["run_id"])
    with pytest.raises((ReviewError, RuntimeError)):
        service.refresh(session, identity)
    with pytest.raises((ReviewError, RuntimeError)):
        service.start_oauth(session)
    assert len(provider.requests) == count


@pytest.mark.parametrize("source_only", [False, True])
def test_journal_is_rechecked_immediately_before_network_dispatch(
    setup, monkeypatch, source_only
):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4())
    backend.deletion_journal = Journal()
    with owner_cursor(backend) as db:
        db.execute(
            "SELECT source_digest FROM receipts WHERE workspace_id=%s", (workspace,)
        )
        source = db.fetchone()["source_digest"]
    original = service.repo.reserve_call

    def delete_after_reservation():
        original()
        if source_only:
            backend.deletion_journal.suppressed.add(source)
        else:
            backend.deletion_journal.deleted.add(workspace)

    monkeypatch.setattr(service.repo, "reserve_call", delete_after_reservation)
    count = len(provider.requests)
    with pytest.raises(ProviderError, match="workspace_unavailable"):
        service.step_import(workspace, run["run_id"])
    assert len(provider.requests) == count
    assert backend.deletion_journal.contains(workspace) is (not source_only)
    assert backend.deletion_journal.suppresses(source) is source_only


def test_journal_blocks_late_provider_page_commit(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4())
    backend.deletion_journal = Journal()
    provider.on_send = lambda _: backend.deletion_journal.deleted.add(workspace)
    with pytest.raises(ProviderError, match="workspace_unavailable"):
        service.step_import(workspace, run["run_id"])
    with owner_cursor(backend) as db:
        db.execute("SELECT count(*) AS n FROM toolost_source_facts")
        assert db.fetchone()["n"] == 0


@pytest.mark.parametrize("source_only", [False, True])
def test_oauth_before_send_also_checks_external_journal(setup, monkeypatch, source_only):
    backend, service, provider, workspace, session = setup
    state = begin(service, session)
    backend.deletion_journal = Journal()
    with owner_cursor(backend) as db:
        db.execute(
            "SELECT source_digest FROM receipts WHERE workspace_id=%s", (workspace,)
        )
        source = db.fetchone()["source_digest"]
    original = service.repo.reserve_call

    def block():
        original()
        if source_only:
            backend.deletion_journal.suppressed.add(source)
        else:
            backend.deletion_journal.deleted.add(workspace)

    monkeypatch.setattr(service.repo, "reserve_call", block)
    with pytest.raises(ReviewError):
        service.callback(
            session, state=state, code="synthetic", callback_uri=service.config.callback
        )
    assert not provider.requests
    assert connection_row(backend, workspace)["credentials"] is None
    assert backend.deletion_journal.contains(workspace) is (not source_only)
    assert backend.deletion_journal.suppresses(source) is source_only


def test_erasure_participant_requires_separate_role_and_deletes_in_fk_order(setup):
    backend, service, _, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4(), [1])
    run_to_end(service, workspace, run["run_id"])
    other_workspace, other_session, _ = sign_in(
        backend, "survivor", "survivor@example.com"
    )
    connected(service, other_session)
    participant = ProviderErasureParticipant()
    with pytest.raises(ProviderError, match="dedicated_scoped_erasure_role_required"):
        with backend.db.transaction(workspace) as db:
            participant.erase_in_transaction(db, workspace)
    with owner_cursor(backend) as db:
        db.execute("""DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='review_erasure')
            THEN CREATE ROLE review_erasure LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE; END IF; END $$""")
        db.execute("GRANT USAGE ON SCHEMA public TO review_erasure")
        db.execute("GRANT SELECT,UPDATE ON workspaces TO review_erasure")
        db.execute(
            Path("services/catalog_review/providers/erasure-grants.sql").read_text()
        )
    erasure_dsn = backend.test_owner_dsn.replace(
        "user=review_migration", "user=review_erasure"
    )
    with closing(psycopg2.connect(erasure_dsn)) as connection, connection:
        with connection.cursor(cursor_factory=RealDictCursor) as db:
            db.execute("SELECT set_config('space.workspace_id',%s,true)", (workspace,))
            counts = participant.erase_in_transaction(db, workspace)
            assert counts["toolost_source_facts"] == 3
            assert counts["toolost_import_pages"] == 2
            assert counts["toolost_import_runs"] == 1
            assert all(
                count == 0
                for count in participant.erase_in_transaction(db, workspace).values()
            )
    with owner_cursor(backend) as db:
        for table in ERASURE_TABLES:
            db.execute(
                "SELECT count(*) AS n FROM " + table + " WHERE workspace_id=%s",
                (workspace,),
            )
            assert db.fetchone()["n"] == 0
        db.execute(
            "SELECT count(*) AS n FROM toolost_connections WHERE workspace_id=%s",
            (other_workspace,),
        )
        assert db.fetchone()["n"] == 1
        db.execute("SELECT status FROM workspaces WHERE workspace_id=%s", (workspace,))
        assert (
            db.fetchone()["status"] == "active"
        )  # Core owns core deletion; participant never reactivates.
    with pytest.raises(ProviderError, match="import_unavailable"):
        service.step_import(workspace, run["run_id"])


def test_erasure_workspace_context_must_match(setup):
    backend, _, _, workspace, _ = setup
    with pytest.raises(ProviderError, match="erasure_workspace_mismatch"):
        with backend.db.transaction(str(uuid4())) as db:
            ProviderErasureParticipant().erase_in_transaction(db, workspace)


def reconfigured(backend, service, provider, **changes):
    configuration = replace(service.config, **changes)
    return TooLostService(
        Repository(
            backend.db,
            ReviewSessionAuthority(backend),
            configuration,
            backend.clock,
            workspace_guard=backend._active,
        ),
        service.vault,
        ReadOnlyAdapter(configuration, provider),
    )


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"max_pages": 1}, "import_page_limit"),
        ({"max_records": 1}, "import_record_or_page_limit"),
        ({"max_calls": 1}, "import_call_limit"),
    ],
)
def test_import_limits_are_durable_and_never_loop_unbounded(setup, changes, expected):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    service = reconfigured(backend, service, provider, **changes)
    provider.script["releases"] = [
        reply(page((1,), count=2)),
        reply(page((2,), number=2, count=2)),
    ]
    run = service.start_import(session, identity, uuid4())
    final = run_to_end(service, workspace, run["run_id"])
    assert final["status"] == "partial" and final["error"] == expected
    assert final["pages"] == 1
    if "max_calls" in changes:
        assert final["calls"] == 1


def test_refresh_is_included_in_job_call_limit(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    service = reconfigured(backend, service, provider, max_calls=1)
    expire_access(backend, workspace)
    run = service.start_import(session, identity, uuid4())
    before = len(provider.requests)
    final = service.step_import(workspace, run["run_id"])
    assert final["status"] == "partial" and final["error"] == "import_call_limit"
    assert final["calls"] == 1
    assert [request.method for request in provider.requests[before:]] == ["POST"]


def test_job_deadline_stops_before_provider_request(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4())
    backend.clock.advance(service.config.job_seconds)
    count = len(provider.requests)
    final = service.step_import(workspace, run["run_id"])
    assert final["error"] == "import_deadline" and final["status"] == "partial"
    assert len(provider.requests) == count


def test_expired_worker_cannot_commit_over_new_lease(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4())
    entered, release = Event(), Event()

    def pause_first(request):
        if request.url.endswith("/releases") and not entered.is_set():
            entered.set()
            assert release.wait(5)

    provider.on_send = pause_first
    with ThreadPoolExecutor(2) as pool:
        stale = pool.submit(service.step_import, workspace, run["run_id"])
        assert entered.wait(5)
        try:
            backend.clock.advance(service.config.lease_seconds + 1)
            current = service.step_import(workspace, run["run_id"])
            assert current["status"] == "complete"
        finally:
            release.set()
        assert stale.result()["status"] == "complete"
    assert service.import_status(session, run["run_id"])["pages"] == 1


def test_quota_and_permission_errors_do_not_refresh_or_retry(setup):
    _, service, provider, workspace, session = setup
    identity = connected(service, session)
    provider.script["releases"] = [reply({}, 403)]
    first = service.start_import(session, identity, uuid4())
    assert (
        service.step_import(workspace, first["run_id"])["error"]
        == "provider_scope_denied"
    )
    provider.script["releases"] = [reply({"error": "quota_exceeded"}, 429)]
    second = service.start_import(session, identity, uuid4())
    assert (
        service.step_import(workspace, second["run_id"])["error"]
        == "provider_quota_exceeded"
    )
    third = service.start_import(session, identity, uuid4())
    count = len(provider.requests)
    assert (
        service.step_import(workspace, third["run_id"])["error"]
        == "provider_quota_exceeded"
    )
    assert len(provider.requests) == count
    assert (
        len([request for request in provider.requests if request.method == "POST"]) == 1
    )


def test_new_oauth_client_cannot_consume_old_client_state(setup):
    backend, service, provider, _, session = setup
    state = begin(service, session)
    other = reconfigured(
        backend, service, provider, client_id="different-synthetic-client"
    )
    with pytest.raises(ProviderError, match="oauth_binding_mismatch"):
        other.callback(
            session, state=state, code="synthetic", callback_uri=other.config.callback
        )
    assert not provider.requests


def test_disabled_worker_and_local_disconnect(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4())
    disabled = reconfigured(backend, service, provider, enabled=False)
    count = len(provider.requests)
    with pytest.raises(ProviderError, match="provider_disabled"):
        disabled.step_import(workspace, run["run_id"])
    assert (
        disabled.disconnect(session, identity)["remote_revocation_confirmed"] is False
    )
    assert len(provider.requests) == count
    assert connection_row(backend, workspace)["credentials"] is None


def test_concurrent_callbacks_exchange_the_code_only_once(setup):
    _, service, provider, _, session = setup
    state = begin(service, session)
    entered, release = Event(), Event()

    def block(request):
        if request.method == "POST":
            entered.set()
            assert release.wait(5)

    provider.on_send = block
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(
            service.callback,
            session,
            state=state,
            code="synthetic",
            callback_uri=service.config.callback,
        )
        assert entered.wait(5)
        try:
            with pytest.raises(ProviderError, match="oauth_state_unavailable"):
                service.callback(
                    session,
                    state=state,
                    code="synthetic",
                    callback_uri=service.config.callback,
                )
        finally:
            release.set()
        assert first.result()["status"] == "awaiting_confirmation"
    assert len(provider.requests) == 2


def test_page_facts_and_checkpoint_roll_back_together(setup):
    backend, service, provider, workspace, session = setup
    identity = connected(service, session)
    run = service.start_import(session, identity, uuid4(), [2])
    final = service.step_import(workspace, run["run_id"])
    assert final["status"] == "partial" and final["error"] == "selected_release_missing"
    assert final["pages"] == 0
    with owner_cursor(backend) as db:
        db.execute("SELECT count(*) AS n FROM toolost_source_facts")
        assert db.fetchone()["n"] == 0
        db.execute("SELECT count(*) AS n FROM toolost_import_pages")
        assert db.fetchone()["n"] == 0
    assert len(provider.requests) == 3
