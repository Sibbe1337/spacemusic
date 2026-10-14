import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg2
import pytest
from conftest import owner_cursor, sign_in

from services.catalog_review.database import CommitOutcomeUnknown
from services.catalog_review.mail import TEM_URL, MailDispatcher, TEMTransport
from services.catalog_review.security import ReviewError

PROJECT = "00000000-0000-4000-8000-000000000001"
PROVIDER = "00000000-0000-4000-8000-000000000002"
TOKEN = "synthetic-provider-token-not-a-real-credential"


def provider_record(status="new", **extra):
    return {
        "id": PROVIDER,
        "project_id": PROJECT,
        "mail_from": "review@example.com",
        "mail_rcpt": "alex@example.com",
        "status": status,
        "flags": [],
        **extra,
    }


@pytest.fixture
def mailcase(backend):
    with owner_cursor(backend) as cur:
        cur.execute("SELECT to_regclass('portal_mail_attempts') AS name")
        if cur.fetchone()["name"] is None:
            cur.execute(Path("services/catalog_review/intake-schema.sql").read_text())
    # ingest only: the invitation must not have been consumed by sign_in().
    workspace = backend.ingest(
        {
            "source": "typeform",
            "form_id": "synthetic-form",
            "response_id": "mail-case",
            "email": "alex@example.com",
        }
    )["workspace_id"]
    with owner_cursor(backend) as cur:
        cur.execute(
            "SELECT invitation_id FROM invitations WHERE workspace_id=%s", (workspace,)
        )
        invitation = str(cur.fetchone()["invitation_id"])
    clients = []

    def build(handler, enabled=True):
        transport = TEMTransport(
            token=TOKEN,
            project_id=PROJECT,
            sender="review@example.com",
            portal_origin=backend.settings.origin,
            enabled=enabled,
            http_transport=httpx.MockTransport(handler),
            clock=backend.clock,
        )
        clients.append(transport)
        dispatcher = MailDispatcher(
            backend.db,
            transport,
            clock=backend.clock,
            current_workspace_guard=backend._active,
            url_for=lambda w, i: (
                backend.settings.origin
                + "/workspace/#invitation="
                + backend.invitation_token(w, i)
            ),
        )
        return dispatcher

    yield workspace, invitation, build
    for transport in clients:
        transport.close()


def test_tem_http_contract_no_fabricated_idempotency(mailcase, backend):
    workspace, invitation, build = mailcase
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == TEM_URL and request.method == "POST"
        assert request.headers["X-Auth-Token"] == TOKEN
        assert "Idempotency-Key" not in request.headers
        message = json.loads(request.content)
        assert message["to"] == [{"email": "alex@example.com"}]
        assert message["from"] == {"email": "review@example.com", "name": "SPACE"}
        assert message["project_id"] == PROJECT
        assert message["send_before"] == "2026-09-18T12:15:00+00:00"
        assert "#invitation=" in message["text"]
        assert (
            "html" not in message
            and "attachments" not in message
            and "additional_headers" not in message
        )
        return httpx.Response(200, json={"emails": [provider_record()]})

    dispatcher = build(handler)
    first = dispatcher.dispatch(workspace, invitation)
    assert first.status == "accepted" and first.provider_reference == PROVIDER
    assert dispatcher.dispatch(workspace, invitation) == first
    assert len(calls) == 1
    with owner_cursor(backend) as cur:
        cur.execute("SELECT * FROM portal_mail_attempts")
        stored = repr(cur.fetchall())
        assert (
            "alex@example.com" not in stored
            and "#invitation" not in stored
            and TOKEN not in stored
        )


def test_unknown_acceptance_survives_restart_without_blind_retry(
    mailcase, backend, caplog
):
    workspace, invitation, build = mailcase
    calls = []

    def lost_ack(request):
        calls.append(request)
        raise httpx.ReadTimeout("synthetic private response " + TOKEN, request=request)

    result = build(lost_ack).dispatch(workspace, invitation)
    assert result.status == "uncertain"
    restarted = build(
        lambda request: pytest.fail(
            "must not POST or lookup by email after lost acknowledgement"
        )
    )
    assert restarted.dispatch(workspace, invitation).status == "uncertain"
    assert restarted.refresh(workspace, invitation).status == "uncertain"
    assert len(calls) == 1 and TOKEN not in caplog.text


def test_crash_before_provider_request_never_requeues(mailcase):
    workspace, invitation, build = mailcase
    dispatcher = build(lambda request: pytest.fail("network must not execute"))

    def crash(message):
        raise KeyboardInterrupt()

    dispatcher.transport._send_once = crash
    with pytest.raises(KeyboardInterrupt):
        dispatcher.dispatch(workspace, invitation)
    assert dispatcher.dispatch(workspace, invitation).status == "uncertain"


def test_pre_send_database_commit_unknown_does_not_send(mailcase):
    workspace, invitation, build = mailcase
    dispatcher = build(
        lambda request: pytest.fail("unknown database commit must not send")
    )
    original = dispatcher.db

    class LostAck:
        @contextmanager
        def transaction(self, *args):
            with original.transaction(*args) as cur:
                yield cur
            raise CommitOutcomeUnknown("synthetic lost database commit acknowledgement")

    dispatcher.db = LostAck()
    with pytest.raises(CommitOutcomeUnknown):
        dispatcher.dispatch(workspace, invitation)
    dispatcher.db = original
    assert dispatcher.dispatch(workspace, invitation).status == "uncertain"


@pytest.mark.parametrize("commit_before_failure", [False, True])
def test_post_send_database_failure_does_not_duplicate(mailcase, commit_before_failure):
    workspace, invitation, build = mailcase
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"emails": [provider_record()]})

    dispatcher = build(handler)
    original = dispatcher.db

    class FailSecond:
        def __init__(self):
            self.calls = 0

        @contextmanager
        def transaction(self, *args):
            self.calls += 1
            with original.transaction(*args) as cur:
                yield cur
                if self.calls == 2 and not commit_before_failure:
                    raise RuntimeError("synthetic rollback")
            if self.calls == 2:
                raise CommitOutcomeUnknown("synthetic dropped acknowledgement")

    dispatcher.db = FailSecond()
    with pytest.raises((RuntimeError, CommitOutcomeUnknown)):
        dispatcher.dispatch(workspace, invitation)
    dispatcher.db = original
    assert dispatcher.dispatch(workspace, invitation).status == (
        "accepted" if commit_before_failure else "uncertain"
    )
    assert len(calls) == 1


def test_parallel_dispatch_has_one_provider_post(mailcase):
    workspace, invitation, build = mailcase
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"emails": [provider_record()]})

    dispatcher = build(handler)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(
            pool.map(lambda _: dispatcher.dispatch(workspace, invitation), range(5))
        )
    assert len(calls) == 1
    assert all(result.status in ("accepted", "uncertain") for result in results)


@pytest.mark.parametrize("status", [301, 302, 307, 429, 500, 503])
def test_ambiguous_http_status_never_retries_or_follows_redirect(mailcase, status):
    workspace, invitation, build = mailcase
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == TEM_URL
        return httpx.Response(
            status,
            content=b"private error must not leak",
            headers={"Location": "https://untrusted.invalid/steal"},
        )

    dispatcher = build(handler)
    assert dispatcher.dispatch(workspace, invitation).status == "uncertain"
    assert dispatcher.dispatch(workspace, invitation).status == "uncertain"
    assert len(calls) == 1


@pytest.mark.parametrize("status", [400, 401, 403, 404, 413, 422])
def test_definite_rejection_is_not_a_bounce_or_retry(mailcase, status):
    workspace, invitation, build = mailcase
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"private": TOKEN})

    dispatcher = build(handler)
    result = dispatcher.dispatch(workspace, invitation)
    assert result.status == "failed" and TOKEN not in repr(result)
    assert dispatcher.dispatch(workspace, invitation).status == "failed"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "variant",
    [
        "non_json",
        "invalid_json",
        "oversized",
        "no_email",
        "two_emails",
        "wrong_project",
        "wrong_recipient",
        "bad_id",
    ],
)
def test_invalid_success_response_is_uncertain(mailcase, variant):
    workspace, invitation, build = mailcase

    def handler(request):
        if variant == "non_json":
            return httpx.Response(200, text="private HTML")
        if variant == "invalid_json":
            return httpx.Response(
                200, content=b"bad json", headers={"content-type": "application/json"}
            )
        if variant == "oversized":
            return httpx.Response(
                200, content=b" " * 70000, headers={"content-type": "application/json"}
            )
        records = [provider_record()]
        if variant == "no_email":
            records = []
        elif variant == "two_emails":
            records *= 2
        elif variant == "wrong_project":
            records[0]["project_id"] = str(uuid4())
        elif variant == "wrong_recipient":
            records[0]["mail_rcpt"] = "another@example.com"
        else:
            records[0]["id"] = "not-an-id"
        return httpx.Response(200, json={"emails": records})

    dispatcher = build(handler)
    assert dispatcher.dispatch(workspace, invitation).status == "uncertain"


def test_provider_status_progression_and_stale_poll_does_not_regress(mailcase):
    workspace, invitation, build = mailcase
    polls = iter(
        [
            provider_record("sending"),
            provider_record("sent"),
            provider_record("new"),
            provider_record("failed", flags=["hard_bounce"]),
        ]
    )
    calls = []

    def handler(request):
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json={"emails": [provider_record()]})
        assert str(request.url) == TEM_URL + "/" + PROVIDER
        return httpx.Response(200, json=next(polls))

    dispatcher = build(handler)
    assert dispatcher.dispatch(workspace, invitation).status == "accepted"
    assert dispatcher.refresh(workspace, invitation).status == "accepted"
    assert dispatcher.refresh(workspace, invitation).status == "delivered"
    assert dispatcher.refresh(workspace, invitation).status == "delivered"
    assert dispatcher.refresh(workspace, invitation).status == "bounced"
    assert dispatcher.refresh(workspace, invitation).status == "bounced"
    assert calls == ["POST", "GET", "GET", "GET", "GET"]


def test_lookup_missing_is_not_evidence_of_nondelivery(mailcase):
    workspace, invitation, build = mailcase
    calls = []

    def handler(request):
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json={"emails": [provider_record()]})
        return httpx.Response(404)

    dispatcher = build(handler)
    assert dispatcher.dispatch(workspace, invitation).status == "accepted"
    assert dispatcher.refresh(workspace, invitation).status == "accepted"
    assert dispatcher.dispatch(workspace, invitation).status == "accepted"
    assert calls == ["POST", "GET"]


@pytest.mark.parametrize(
    "status,flags,expected",
    [
        ("new", [], "accepted"),
        ("sending", ["soft_bounce"], "accepted"),
        ("sent", [], "delivered"),
        ("failed", ["hard_bounce"], "bounced"),
        ("failed", ["mailbox_not_found"], "bounced"),
        ("failed", [], "failed"),
        ("canceled", [], "canceled"),
        ("unknown", [], "uncertain"),
    ],
)
def test_tem_status_mapping(mailcase, status, flags, expected):
    workspace, invitation, build = mailcase
    dispatcher = build(
        lambda request: httpx.Response(
            200, json={"emails": [provider_record(status, flags=flags)]}
        )
    )
    result = dispatcher.dispatch(workspace, invitation)
    assert result.status == expected and result.provider_reference == PROVIDER


@pytest.mark.parametrize("unavailable", ["expired", "revoked", "deleted", "consumed"])
def test_unavailable_invitation_canceled_before_post(mailcase, backend, unavailable):
    workspace, invitation, build = mailcase
    if unavailable == "expired":
        backend.clock.advance(900)
    elif unavailable == "consumed":
        backend.exchange_invitation(backend.invitation_token(workspace, invitation))
    else:
        with owner_cursor(backend) as cur:
            if unavailable == "revoked":
                cur.execute(
                    "UPDATE memberships SET active=false WHERE workspace_id=%s",
                    (workspace,),
                )
            else:
                cur.execute(
                    "UPDATE workspaces SET status='deletion_requested' WHERE workspace_id=%s",
                    (workspace,),
                )
    dispatcher = build(
        lambda request: pytest.fail("unavailable invitation must not send")
    )
    if unavailable == "deleted":
        with pytest.raises(ReviewError, match="workspace_unavailable"):
            dispatcher.dispatch(workspace, invitation)
    else:
        assert dispatcher.dispatch(workspace, invitation).status == "canceled"


def test_cross_workspace_invitation_and_ledger_hidden(mailcase, backend):
    workspace, invitation, build = mailcase
    other, _, _ = sign_in(backend, "other-case")
    dispatcher = build(
        lambda request: httpx.Response(200, json={"emails": [provider_record()]})
    )
    dispatcher.dispatch(workspace, invitation)
    with pytest.raises(ReviewError, match="invitation_unavailable"):
        dispatcher.dispatch(other, invitation)
    with pytest.raises(ReviewError, match="mail_attempt_unavailable"):
        dispatcher.refresh(other, invitation)
    with backend.db.transaction(other) as cur:
        cur.execute("SELECT * FROM portal_mail_attempts")
        assert cur.fetchall() == []


def test_sql_guard_blocks_reset_of_uncertain_attempt(mailcase, backend):
    workspace, invitation, build = mailcase
    dispatcher = build(lambda request: httpx.Response(503))
    dispatcher.dispatch(workspace, invitation)
    with pytest.raises(psycopg2.errors.RaiseException, match="invalid_mail_transition"):
        with backend.db.transaction(workspace) as cur:
            cur.execute(
                "UPDATE portal_mail_attempts SET status='queued',attempt_id=NULL WHERE invitation_id=%s",
                (invitation,),
            )
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with backend.db.transaction(workspace) as cur:
            cur.execute("DELETE FROM portal_mail_attempts")


def test_transport_disabled_by_default(mailcase):
    workspace, invitation, build = mailcase
    dispatcher = build(
        lambda request: pytest.fail("disabled adapter must not send"), enabled=False
    )
    with pytest.raises(ReviewError, match="mail_transport_disabled"):
        dispatcher.dispatch(workspace, invitation)


@pytest.mark.parametrize(
    "url",
    [
        "https://spacemusic.io/workspace/#invitation=" + "a" * 80,
        "https://review-staging.spacemusic.io/workspace/#invitation=" + "a" * 80,
        "https://review.test/workspace/?token=private#invitation=" + "a" * 80,
        "https://review.test/workspace/#invitation="
        + "a" * 80
        + "\nBcc:bad@example.com",
    ],
)
def test_invitation_url_restricted_to_exact_environment(mailcase, backend, url):
    _, _, build = mailcase
    dispatcher = build(lambda request: pytest.fail("must not send"))
    with pytest.raises(ReviewError, match="invalid_invitation_mail"):
        dispatcher.transport.prepare(
            recipient="alex@example.com", url=url, expires_at=backend.clock()
        )


def test_private_payload_has_no_printable_repr(mailcase, backend):
    workspace, invitation, build = mailcase
    dispatcher = build(lambda request: pytest.fail("must not send"))
    message = dispatcher.transport.prepare(
        recipient="alex@example.com",
        url=dispatcher._url_for(workspace, invitation),
        expires_at=backend.clock(),
    )
    assert "alex@example.com" not in repr(message) and "invitation=" not in repr(
        message
    )


def test_dispatcher_requires_explicit_current_workspace_guard(mailcase, backend):
    _, _, build = mailcase
    transport = build(lambda request: pytest.fail("must not send")).transport
    with pytest.raises(TypeError, match="current_workspace_guard"):
        MailDispatcher(backend.db, transport, url_for=lambda w, i: "")
    with pytest.raises(ValueError, match="guard required"):
        MailDispatcher(
            backend.db, transport, url_for=lambda w, i: "", current_workspace_guard=None
        )


@pytest.mark.parametrize(
    "phase", ["restored_queued", "immediately_before_post", "source_only"]
)
def test_external_journal_blocks_restored_queue_and_rechecked_before_post(
    mailcase, backend, phase
):
    workspace, invitation, build = mailcase
    checks = []

    class Journal:
        def contains(self, value):
            assert value == workspace
            checks.append(value)
            return phase == "restored_queued" or (
                phase == "immediately_before_post" and len(checks) >= 2
            )

        def suppresses(self, source):
            assert len(source) == 64
            return phase == "source_only"

    backend.deletion_journal = Journal()
    with backend.db.transaction(workspace) as cur:
        MailDispatcher.enqueue_in_transaction(
            cur, workspace, invitation, backend.clock()
        )
    dispatcher = build(
        lambda request: pytest.fail("journal stopped workspace must never send")
    )
    with pytest.raises(ReviewError, match="workspace_unavailable"):
        dispatcher.dispatch(workspace, invitation)
    with owner_cursor(backend) as cur:
        cur.execute("SELECT status FROM portal_mail_attempts")
        assert cur.fetchone()["status"] == (
            "uncertain" if phase == "immediately_before_post" else "queued"
        )
    with pytest.raises(ReviewError, match="workspace_unavailable"):
        dispatcher.refresh(workspace, invitation)


def test_external_journal_failure_at_final_guard_stays_uncertain(mailcase, backend):
    workspace, invitation, build = mailcase
    checks = []

    class Journal:
        def contains(self, value):
            checks.append(value)
            if len(checks) == 2:
                raise RuntimeError("journal unavailable")
            return False

        def suppresses(self, source):
            return False

    backend.deletion_journal = Journal()
    dispatcher = build(lambda request: pytest.fail("guard failure must not POST"))
    with pytest.raises(RuntimeError, match="journal unavailable"):
        dispatcher.dispatch(workspace, invitation)
    assert dispatcher.dispatch(workspace, invitation).status == "uncertain"
    assert dispatcher.refresh(workspace, invitation).status == "uncertain"


@pytest.fixture
def retentioncase(mailcase, backend):
    workspace, _, build = mailcase
    backend.clock.advance(76 * 86400)
    assert backend.queue_retention_notice(workspace, 0) == {
        "queued": True,
        "delivered": False,
    }
    return workspace, build


def activity(backend, workspace):
    with owner_cursor(backend) as cur:
        cur.execute(
            "SELECT last_activity_at,activity_version FROM workspaces WHERE workspace_id=%s",
            (workspace,),
        )
        return dict(cur.fetchone())


def test_retention_real_tem_contract_plain_case_link_and_no_activity_touch(
    retentioncase, backend
):
    workspace, build = retentioncase
    before = activity(backend, workspace)
    deadline = (before["last_activity_at"] + timedelta(days=90)).astimezone(
        timezone.utc
    )
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"emails": [provider_record()]})

    dispatcher = build(handler)
    result = dispatcher.dispatch_retention(workspace, 0)
    assert result.status == "accepted" and result.provider_reference == PROVIDER
    assert dispatcher.dispatch_retention(workspace, 0) == result
    assert len(calls) == 1 and activity(backend, workspace) == before
    request = calls[0]
    assert request.method == "POST" and str(request.url) == TEM_URL
    message = json.loads(request.content)
    assert message["to"] == [{"email": "alex@example.com"}]
    assert message["send_before"] == deadline.isoformat()
    assert workspace in message["text"] and deadline.isoformat() in message["text"]
    assert "https://review.test/workspace/" in message["text"]
    assert "#invitation=" not in message["text"] and "?" not in message["text"]
    assert "I want to continue this review" in message["text"]
    assert "Receiving or opening this email does not extend" in message["text"]
    assert "Idempotency-Key" not in request.headers
    with owner_cursor(backend) as cur:
        cur.execute("SELECT * FROM retention_notices")
        row = cur.fetchone()
        assert (
            row["attempt_id"] is not None and str(row["provider_reference"]) == PROVIDER
        )
        assert row["deadline"] == deadline
        assert "alex@example.com" not in repr(row) and "invitation=" not in repr(row)


def test_retention_lost_provider_ack_never_reposts_or_searches_by_email(retentioncase):
    workspace, build = retentioncase
    calls = []

    def lost_ack(request):
        calls.append(request)
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    assert build(lost_ack).dispatch_retention(workspace, 0).status == "uncertain"
    restarted = build(
        lambda request: pytest.fail("uncertain has no provider ID; never POST or guess")
    )
    assert restarted.dispatch_retention(workspace, 0).status == "uncertain"
    assert restarted.refresh_retention(workspace, 0).status == "uncertain"
    assert len(calls) == 1


def test_retention_pre_send_commit_unknown_does_not_send(retentioncase):
    workspace, build = retentioncase
    dispatcher = build(lambda request: pytest.fail("must not send"))
    original = dispatcher.db

    class LostAck:
        @contextmanager
        def transaction(self, *args):
            with original.transaction(*args) as cur:
                yield cur
            raise CommitOutcomeUnknown("synthetic unknown commit")

    dispatcher.db = LostAck()
    with pytest.raises(CommitOutcomeUnknown):
        dispatcher.dispatch_retention(workspace, 0)
    dispatcher.db = original
    assert dispatcher.dispatch_retention(workspace, 0).status == "uncertain"


@pytest.mark.parametrize("commit_before_failure", [False, True])
def test_retention_post_send_commit_failure_never_reposts(
    retentioncase, commit_before_failure
):
    workspace, build = retentioncase
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"emails": [provider_record()]})

    dispatcher = build(handler)
    original = dispatcher.db

    class FailSecond:
        def __init__(self):
            self.calls = 0

        @contextmanager
        def transaction(self, *args):
            self.calls += 1
            with original.transaction(*args) as cur:
                yield cur
                if self.calls == 2 and not commit_before_failure:
                    raise RuntimeError("synthetic rollback")
            if self.calls == 2:
                raise CommitOutcomeUnknown("synthetic unknown commit")

    dispatcher.db = FailSecond()
    with pytest.raises((RuntimeError, CommitOutcomeUnknown)):
        dispatcher.dispatch_retention(workspace, 0)
    dispatcher.db = original
    assert dispatcher.dispatch_retention(workspace, 0).status == (
        "accepted" if commit_before_failure else "uncertain"
    )
    assert len(calls) == 1


def test_retention_parallel_workers_send_once(retentioncase):
    workspace, build = retentioncase
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"emails": [provider_record()]})

    dispatcher = build(handler)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(
            pool.map(lambda _: dispatcher.dispatch_retention(workspace, 0), range(5))
        )
    assert {r.status for r in results} <= {"uncertain", "accepted"}
    assert len(calls) == 1


@pytest.mark.parametrize("phase", ["restored_queued", "before_post", "source_only"])
def test_retention_journal_guard_rechecked_immediately_before_post(
    retentioncase, backend, phase
):
    workspace, build = retentioncase
    checks = []

    class Journal:
        def contains(self, value):
            assert value == workspace
            checks.append(value)
            return phase == "restored_queued" or (
                phase == "before_post" and len(checks) >= 2
            )

        def suppresses(self, source):
            assert len(source) == 64
            return phase == "source_only"

    backend.deletion_journal = Journal()
    dispatcher = build(lambda request: pytest.fail("blocked by deletion journal"))
    with pytest.raises(ReviewError, match="workspace_unavailable"):
        dispatcher.dispatch_retention(workspace, 0)
    with owner_cursor(backend) as cur:
        cur.execute("SELECT status FROM retention_notices")
        assert cur.fetchone()["status"] == (
            "uncertain" if phase == "before_post" else "queued"
        )


@pytest.mark.parametrize("change", ["activity", "deadline", "owner", "cancellation"])
def test_retention_rechecks_current_version_deadline_owner_and_cancel_before_post(
    retentioncase, backend, change
):
    workspace, build = retentioncase
    dispatcher = build(lambda request: pytest.fail("stale reminder must not send"))
    original = dispatcher.db

    class ChangeAfterCommit:
        def __init__(self):
            self.calls = 0

        @contextmanager
        def transaction(self, *args):
            self.calls += 1
            with original.transaction(*args) as cur:
                yield cur
            if self.calls == 1:
                if change == "deadline":
                    backend.clock.advance(14 * 86400)
                else:
                    with original.transaction(workspace) as cur:
                        backend._active(cur, workspace)
                        if change == "activity":
                            backend._touch(cur, workspace)
                        elif change == "owner":
                            cur.execute(
                                "UPDATE memberships SET active=false WHERE role='owner'"
                            )
                        else:
                            cur.execute(
                                "UPDATE retention_notices SET status='cancelled'"
                            )

    dispatcher.db = ChangeAfterCommit()
    assert dispatcher.dispatch_retention(workspace, 0).status == "canceled"
    dispatcher.db = original
    assert dispatcher.dispatch_retention(workspace, 0).status == "canceled"


@pytest.mark.parametrize(
    "provider_status,flags,expected",
    [
        ("sent", [], "delivered"),
        ("failed", ["hard_bounce"], "bounced"),
        ("failed", [], "failed"),
    ],
)
def test_retention_provider_reconciliation_without_case_activity(
    retentioncase, backend, provider_status, flags, expected
):
    workspace, build = retentioncase
    before = activity(backend, workspace)
    calls = []

    def handler(request):
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json={"emails": [provider_record()]})
        assert str(request.url) == TEM_URL + "/" + PROVIDER
        return httpx.Response(200, json=provider_record(provider_status, flags=flags))

    dispatcher = build(handler)
    assert dispatcher.dispatch_retention(workspace, 0).status == "accepted"
    assert dispatcher.refresh_retention(workspace, 0).status == expected
    assert activity(backend, workspace) == before
    assert calls == ["POST", "GET"]


@pytest.mark.parametrize(
    "status,expected", [(400, "failed"), (429, "uncertain"), (503, "uncertain")]
)
def test_retention_failure_is_operator_attention_not_an_extension(
    retentioncase, backend, status, expected
):
    workspace, build = retentioncase
    before = activity(backend, workspace)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status)

    dispatcher = build(handler)
    assert dispatcher.dispatch_retention(workspace, 0).status == expected
    assert dispatcher.dispatch_retention(workspace, 0).status == expected
    assert len(calls) == 1 and activity(backend, workspace) == before
    backend.clock.advance(14 * 86400)
    assert backend.retention_state(workspace)["deletion_due"]


def test_retention_immutable_notice_no_unknown_reset_and_rls(retentioncase, backend):
    workspace, build = retentioncase
    build(lambda request: httpx.Response(503)).dispatch_retention(workspace, 0)
    for statement in (
        "UPDATE retention_notices SET status='queued'",
        "UPDATE retention_notices SET deadline=deadline+interval '1 day'",
        "UPDATE retention_notices SET activity_version=activity_version+1",
    ):
        with pytest.raises(
            psycopg2.errors.RaiseException, match="invalid_retention_mail_transition"
        ):
            with backend.db.transaction(workspace) as cur:
                cur.execute(statement)
    other, _, _ = sign_in(backend, "other-retention-case")
    with backend.db.transaction(other) as cur:
        cur.execute("SELECT * FROM retention_notices")
        assert cur.fetchall() == []
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with backend.db.transaction(workspace) as cur:
            cur.execute("DELETE FROM retention_notices")


def test_retention_requires_prequeued_due_notice_and_valid_version(mailcase, backend):
    workspace, _, build = mailcase
    dispatcher = build(lambda request: pytest.fail("not queued; no send"))
    assert backend.queue_retention_notice(workspace, 0) == {"queued": False}
    with pytest.raises(ReviewError, match="retention_notice_unavailable"):
        dispatcher.dispatch_retention(workspace, 0)
    with pytest.raises(ReviewError, match="invalid_activity_version"):
        dispatcher.dispatch_retention(workspace, True)
