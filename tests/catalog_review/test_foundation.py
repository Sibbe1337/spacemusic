import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import uuid4

import psycopg2
import pytest
from conftest import draft, owner_cursor, receipt, sign_in
from pydantic import ValidationError

from services.catalog_review.contracts import Draft, Intake, Rights, SaveDraft, Submit
from services.catalog_review.database import CommitOutcomeUnknown, Database
from services.catalog_review.security import ReviewError, Settings
from services.catalog_review.service import ReviewService
from services.catalog_review.workers import deliver_invitation, scan_document


def test_ingest_replay_and_different_submission_same_email(backend):
    first = backend.ingest(receipt())
    assert first["created"] is True
    assert backend.ingest(receipt()) == {**first, "created": False}
    second = backend.ingest(receipt("response-2"))
    assert second["workspace_id"] != first["workspace_id"]
    with owner_cursor(backend) as cur:
        for table in ("receipts", "workspaces", "memberships", "invitations", "outbox"):
            cur.execute("SELECT count(*) AS n FROM " + table)
            assert cur.fetchone()["n"] == 2


def test_changed_payload_replay_rejected(backend):
    backend.ingest(receipt())
    with pytest.raises(ReviewError, match="intake_reference_conflict"):
        backend.ingest(receipt(email="different@example.com"))


def test_parallel_intake_is_atomic(backend):
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: backend.ingest(receipt()), range(5)))
    assert sum(r["created"] for r in results) == 1
    assert len({r["workspace_id"] for r in results}) == 1


def test_audit_failure_rolls_back_application_and_invitation(backend, monkeypatch):
    def fail(*args):
        raise RuntimeError("synthetic transaction failure")

    monkeypatch.setattr(backend, "_audit", fail)
    with pytest.raises(RuntimeError):
        backend.ingest(receipt())
    with owner_cursor(backend) as cur:
        for table in ("receipts", "workspaces", "memberships", "invitations", "outbox"):
            cur.execute("SELECT count(*) AS n FROM " + table)
            assert cur.fetchone()["n"] == 0


def test_invitation_is_single_use_under_race(backend):
    workspace = backend.ingest(receipt())["workspace_id"]
    job = backend.claim_invitation(workspace)
    token = job["url"].split("#invitation=")[1]

    def exchange(_):
        try:
            return backend.exchange_invitation(token)
        except ReviewError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(exchange, range(4)))
    assert sum(r is not None for r in results) == 1


def test_no_raw_auth_tokens_persisted(backend):
    workspace, session, invitation = sign_in(backend)
    with owner_cursor(backend) as cur:
        for table in ("invitations", "sessions", "outbox", "audit"):
            cur.execute("SELECT * FROM " + table)
            stored = json.dumps(cur.fetchall(), default=str)
            assert session not in stored and invitation not in stored
    assert "example.com" not in repr(backend.settings)
    assert backend.settings.signing_key.hex() not in repr(backend.settings)


def test_expired_invitation_and_session(backend):
    workspace, session, _ = sign_in(backend)
    other = backend.ingest(receipt("other"))["workspace_id"]
    invitation = backend.claim_invitation(other)["url"].split("#invitation=")[1]
    backend.clock.advance(900)
    with pytest.raises(ReviewError):
        backend.exchange_invitation(invitation)
    backend.clock.advance(2700)
    with pytest.raises(ReviewError):
        backend.view(session)


def test_workspace_swap_and_membership_revocation(backend):
    first, token, _ = sign_in(backend)
    second, other, _ = sign_in(backend, "other")
    with pytest.raises(ReviewError):
        backend.view(second + "." + token.split(".")[1])
    assert backend.view(token)["workspace_id"] == first
    assert backend.view(other)["workspace_id"] == second
    with owner_cursor(backend) as cur:
        cur.execute(
            "UPDATE memberships SET active=false WHERE workspace_id=%s", (first,)
        )
    with pytest.raises(ReviewError):
        backend.view(token)


def test_database_rls_without_scope_and_cross_workspace_write(backend):
    first, _, _ = sign_in(backend)
    second, _, _ = sign_in(backend, "other")
    with backend.db.transaction() as cur:
        for table in (
            "workspaces",
            "memberships",
            "sessions",
            "invitations",
            "outbox",
            "documents",
            "submissions",
            "audit",
        ):
            cur.execute("SELECT * FROM " + table)
            assert cur.fetchall() == []
    with backend.db.transaction(first) as cur:
        cur.execute("SELECT workspace_id FROM workspaces")
        assert [str(r["workspace_id"]) for r in cur.fetchall()] == [first]
        cur.execute(
            "UPDATE workspaces SET revision=99 WHERE workspace_id=%s", (second,)
        )
        assert cur.rowcount == 0
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with backend.db.transaction(first) as cur:
            cur.execute(
                "INSERT INTO audit VALUES(%s,%s,'submitted',now())",
                (second, str(uuid4())),
            )
    with backend.db.transaction() as cur:
        cur.execute("SELECT * FROM workspaces")
        assert cur.fetchall() == []


def test_runtime_role_not_superuser_or_owner(backend):
    with pytest.raises(RuntimeError, match="bypass"):
        Database(backend.test_owner_dsn)
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with backend.db.transaction() as cur:
            cur.execute("TRUNCATE workspaces CASCADE")


@pytest.mark.parametrize(
    "misconfiguration",
    [
        "ALTER TABLE documents DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY",
        "GRANT UPDATE ON submissions TO review_runtime",
        "GRANT DELETE ON audit TO review_runtime",
        "GRANT TRUNCATE ON workspaces TO review_runtime",
        "GRANT TRUNCATE ON receipts TO review_runtime",
        "GRANT TRUNCATE ON auth_limits TO review_runtime",
        "GRANT UPDATE(snapshot) ON submissions TO review_runtime",
        "GRANT UPDATE(action) ON audit TO review_runtime",
    ],
)
def test_unsafe_database_configuration_blocks_startup(backend, misconfiguration):
    with owner_cursor(backend) as cur:
        cur.execute(misconfiguration)
    with pytest.raises(RuntimeError):
        Database(backend.test_runtime_dsn)


def test_reviewers_need_mfa_and_cannot_change_owner_draft(backend):
    workspace, token, _ = sign_in(backend)
    # A fixture injects reviewer identity directly; no HTTP test-login route exists.
    with owner_cursor(backend) as cur:
        cur.execute(
            "UPDATE memberships SET role='reviewer' WHERE workspace_id=%s", (workspace,)
        )
    with pytest.raises(ReviewError):
        backend.view(token)
    with owner_cursor(backend) as cur:
        cur.execute("UPDATE sessions SET mfa=true WHERE workspace_id=%s", (workspace,))
    assert backend.view(token)["role"] == "reviewer"
    with pytest.raises(ReviewError, match="owner_required"):
        backend.save_draft(token, {"revision": 0, "draft": draft()})


@pytest.mark.parametrize("share", [0, -1, 101, "NaN", "Infinity", "0.001", True])
def test_invalid_known_shares(share):
    with pytest.raises(ValidationError):
        Rights(release_reference="r", ownership="known", share_percent=share)


@pytest.mark.parametrize("share", ["0.01", "50", "100"])
def test_valid_known_share(share):
    assert (
        Rights(
            release_reference="r", ownership="known", share_percent=share
        ).share_percent
        is not None
    )


def test_unknown_is_not_zero_and_future_excluded():
    assert Rights(release_reference="r", ownership="unknown").share_percent is None
    for value in [
        {"ownership": "known"},
        {"ownership": "unknown", "share_percent": 10},
    ]:
        with pytest.raises(ValidationError):
            Rights(release_reference="r", **value)
    with pytest.raises(ValidationError):
        Draft(**{**draft(), "future_music_excluded": False})


@pytest.mark.parametrize("value", [1, "true", False, None])
def test_consent_is_explicit_boolean(value):
    with pytest.raises(ValidationError):
        Submit(request_id=uuid4(), revision=0, consent=value)
    with pytest.raises(ValidationError):
        Draft(**{**draft(), "future_music_excluded": value})


@pytest.mark.parametrize("revision", [-1, True, "1", 0.5])
def test_strict_revision(revision):
    with pytest.raises(ValidationError):
        SaveDraft(revision=revision, draft=draft())


def test_no_real_recipients_or_unknown_metadata():
    for data in [
        receipt(email="test@real.invalid"),
        {**receipt(), "revenue": 1000},
        {**receipt(), "landing_path": "/?email=private"},
    ]:
        with pytest.raises(ValidationError):
            Intake.model_validate(data)


def test_optimistic_revision_and_concurrent_save(backend):
    _, token, _ = sign_in(backend)

    def save(_):
        try:
            return backend.save_draft(token, {"revision": 0, "draft": draft()})
        except ReviewError:
            return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(save, range(3)))
    assert sum(r is not None for r in results) == 1
    assert backend.view(token)["revision"] == 1


def test_submission_locked_idempotent_and_not_verified(backend):
    workspace, token, _ = sign_in(backend)
    backend.save_draft(token, {"revision": 0, "draft": draft()})
    request = {"revision": 1, "request_id": str(uuid4()), "consent": True}
    result = backend.submit(token, request)
    assert backend.submit(token, request) == {**result, "created": False}
    with pytest.raises(ReviewError, match="submission_locked"):
        backend.save_draft(token, {"revision": 1, "draft": draft()})
    snapshot = backend.view(token)["submission"]["snapshot"]
    assert snapshot["missing_evidence"] is True
    assert snapshot["rights_verified"] is False
    assert snapshot["draft"]["rights"][0]["share_percent"] is None
    for statement in (
        "UPDATE submissions SET snapshot='{}'",
        "DELETE FROM submissions",
        "DELETE FROM audit",
    ):
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            with backend.db.transaction(workspace) as cur:
                cur.execute(statement)


def test_empty_draft_cannot_submit(backend):
    _, token, _ = sign_in(backend)
    with pytest.raises(ReviewError, match="draft_incomplete"):
        backend.submit(
            token, {"revision": 0, "request_id": str(uuid4()), "consent": True}
        )


def test_document_quarantine_cross_tenant_and_submission_gate(backend):
    workspace, token, _ = sign_in(backend)
    _, other, _ = sign_in(backend, "other")
    content = b"%PDF-1.7\nsynthetic fixture, not an actual parsed PDF"
    doc = backend.quarantine(token, "statement.pdf", content, backend.test_blobs)[
        "document_id"
    ]
    with pytest.raises(ReviewError):
        backend.download(token, doc, backend.test_blobs)
    with pytest.raises(ReviewError):
        backend.save_draft(other, {"revision": 0, "draft": draft([doc])})
    backend.save_draft(token, {"revision": 0, "draft": draft([doc])})
    with pytest.raises(ReviewError, match="documents_not_ready"):
        backend.submit(
            token, {"revision": 1, "request_id": str(uuid4()), "consent": True}
        )

    class FakeScanner:
        def inspect(self, **kwargs):
            return True

    assert (
        scan_document(backend, workspace, doc, backend.test_blobs, FakeScanner())
        == "accepted_for_review"
    )
    assert backend.download(token, doc, backend.test_blobs) == (
        "statement.pdf",
        content,
    )
    with pytest.raises(ReviewError):
        backend.download(other, doc, backend.test_blobs)
    backend.submit(token, {"revision": 1, "request_id": str(uuid4()), "consent": True})
    assert backend.view(token)["submission"]["snapshot"]["rights_verified"] is False
    with pytest.raises(ReviewError):
        backend.quarantine(token, "another.csv", b"test", backend.test_blobs)


def test_scan_leases_hash_and_out_of_order_results(backend):
    workspace, token, _ = sign_in(backend)
    doc = backend.quarantine(
        token, "statement.csv", b"month,amount\n2026-01,12", backend.test_blobs
    )["document_id"]
    old = backend.claim_scan(workspace, doc)
    assert backend.claim_scan(workspace, doc) is None
    backend.clock.advance(120)
    new = backend.claim_scan(workspace, doc)
    for job, checksum in [(old, old["sha256"]), (new, "0" * 64)]:
        with pytest.raises(ReviewError, match="scan_result_stale"):
            backend.complete_scan(job, clean=True, scanned_sha256=checksum)
    backend.complete_scan(new, clean=True, scanned_sha256=new["sha256"])
    backend.test_blobs.objects[new["object_key"]] = b"modified"
    with pytest.raises(ReviewError, match="document_integrity_failed"):
        backend.download(token, doc, backend.test_blobs)


def test_scanner_outage_does_not_accept_and_stops_after_three_attempts(backend):
    workspace, token, _ = sign_in(backend)
    doc = backend.quarantine(token, "statement.csv", b"fixture", backend.test_blobs)[
        "document_id"
    ]

    class Unavailable:
        def inspect(self, **kwargs):
            raise RuntimeError("unavailable")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            scan_document(backend, workspace, doc, backend.test_blobs, Unavailable())
        backend.clock.advance(120)
    assert backend.claim_scan(workspace, doc) is None
    assert backend.view(token)["documents"][0]["status"] == "quarantined"


@pytest.mark.parametrize(
    "name,content",
    [
        ("../x.pdf", b"%PDF-"),
        ("x.exe", b"MZ"),
        ("report.pdf", b"not pdf"),
        ("report.xlsx", b"not zip"),
        ("report.csv", b""),
    ],
)
def test_bad_uploads(backend, name, content):
    _, token, _ = sign_in(backend)
    with pytest.raises((ValidationError, ReviewError)):
        backend.quarantine(token, name, content, backend.test_blobs)
    assert backend.test_blobs.objects == {}


def test_failed_database_commit_removes_quarantine_object(backend, monkeypatch):
    _, token, _ = sign_in(backend)

    def fail(*args):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(backend, "_audit", fail)
    with pytest.raises(RuntimeError):
        backend.quarantine(token, "statement.csv", b"fixture", backend.test_blobs)
    assert not backend.test_blobs.objects


def test_lost_commit_ack_preserves_committed_document(backend, monkeypatch):
    _, token, _ = sign_in(backend)
    original = backend.db.transaction

    @contextmanager
    def lost_ack(workspace=None):
        with original(workspace) as cur:
            yield cur
        raise CommitOutcomeUnknown("simulated lost acknowledgement after real commit")

    monkeypatch.setattr(backend.db, "transaction", lost_ack)
    with pytest.raises(CommitOutcomeUnknown):
        backend.quarantine(token, "statement.csv", b"fixture", backend.test_blobs)
    assert len(backend.test_blobs.objects) == 1
    with owner_cursor(backend) as cur:
        cur.execute("SELECT object_key FROM documents")
        assert cur.fetchone()["object_key"] in backend.test_blobs.objects


def test_outbox_crash_recovery_same_link_and_idempotency_key(backend):
    workspace = backend.ingest(receipt())["workspace_id"]
    old = backend.claim_invitation(workspace)
    assert backend.claim_invitation(workspace) is None
    backend.clock.advance(60)
    job = backend.claim_invitation(workspace)
    assert job["url"] == old["url"]
    assert job["idempotency_key"] == old["idempotency_key"]
    assert job["lease_id"] != old["lease_id"]
    with pytest.raises(ReviewError, match="invitation_lease_stale"):
        backend.finish_invitation(old, accepted=True, provider_reference="synthetic")
    backend.finish_invitation(job, accepted=True, provider_reference="synthetic")
    assert backend.claim_invitation(workspace) is None


def test_outbox_transport_failure_is_bounded_and_persistent(backend):
    workspace = backend.ingest(receipt())["workspace_id"]

    class FailedTransport:
        def send(self, **kwargs):
            raise TimeoutError("unknown remote outcome")

    for _ in range(5):
        assert (
            deliver_invitation(backend, workspace, FailedTransport())
            == "retry_scheduled"
        )
        # A new service instance simulates process restart; state remains in PG.
        backend = ReviewService(backend.db, backend.settings, backend.clock)
        backend.clock.advance(60)
    assert deliver_invitation(backend, workspace, FailedTransport()) == "no_job"


def test_accepted_is_not_delivered_and_consumed_invite_not_sent(backend):
    workspace = backend.ingest(receipt())["workspace_id"]

    class Transport:
        def send(self, **kwargs):
            assert kwargs["recipient"] == "alex@example.com"
            assert "#invitation=" in kwargs["url"]
            return "synthetic-provider-id"

    assert deliver_invitation(backend, workspace, Transport()) == "accepted"
    other, _, _ = sign_in(backend, "other")
    assert deliver_invitation(backend, other, Transport()) == "no_job"


def test_deletion_stops_access_jobs_and_receipt_replay_not_erasure(backend):
    workspace, token, _ = sign_in(backend)
    doc = backend.quarantine(token, "statement.csv", b"fixture", backend.test_blobs)[
        "document_id"
    ]
    job = backend.claim_scan(workspace, doc)
    assert backend.request_deletion(token) == {
        "status": "deletion_requested",
        "erasure_completed": False,
    }
    for call in [
        lambda: backend.view(token),
        lambda: backend.claim_invitation(workspace),
        lambda: backend.complete_scan(job, clean=True, scanned_sha256=job["sha256"]),
    ]:
        with pytest.raises(ReviewError):
            call()
    assert backend.ingest(receipt()) == {"workspace_id": workspace, "created": False}
    assert backend.test_blobs.objects  # No false claim of completed erasure.


def test_production_and_unapproved_origin_are_blocked(backend):
    for value in ["production", "sandbox", "staging"]:
        with pytest.raises(RuntimeError):
            Settings("https://review.test", b"a" * 32, b"b" * 32, value).validate()
    with pytest.raises(RuntimeError):
        Settings("https://spacemusic.io", b"a" * 32, b"b" * 32).validate()
    with pytest.raises(RuntimeError):
        Settings("https://review.test", b"a" * 32, b"a" * 32).validate()
