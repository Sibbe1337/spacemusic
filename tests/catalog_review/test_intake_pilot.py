import base64
import hashlib
import hmac
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import psycopg2
import pytest
from conftest import owner_cursor
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_lifecycle import journal as replicated_journal

from services.catalog_review.database import CommitOutcomeUnknown
from services.catalog_review.erasure import ErasureDatabase, erase_workspace
from services.catalog_review.intake import (
    MAX_BODY,
    IntakeErasureParticipant,
    IntakeService,
    TypeformMapping,
    normalize_email,
)
from services.catalog_review.intake_http import create_intake_router
from services.catalog_review.mail import MailDispatcher
from services.catalog_review.security import ReviewError

SOURCE_KEY = b"source-index-test-only-00000000000"
WEBHOOK_KEY = b"webhook-test-only-000000000000000"
OPERATOR = str(uuid4())


class SyntheticVault:
    """Opaque in-memory test vault, NOT production encryption or a KMS."""

    def __init__(self):
        self.values = {}

    def seal(self, value, *, aad):
        handle = secrets.token_bytes(32)
        self.values[handle] = (aad, value)
        return handle

    def open(self, value, *, aad):
        expected, plaintext = self.values[value]
        if aad != expected:
            raise ValueError("wrong context")
        return plaintext


def authorize(cur, principal, action):
    if principal != "synthetic-live-operator":
        raise ReviewError("operator_required", 403)
    assert action.startswith("intake.")
    return OPERATOR


@pytest.fixture
def inbox(backend):
    with owner_cursor(backend) as cur:
        cur.execute("SELECT to_regclass('intake_inbox') AS name")
        if cur.fetchone()["name"] is None:
            cur.execute(Path("services/catalog_review/intake-schema.sql").read_text())
    return IntakeService(
        backend.db,
        source_key=SOURCE_KEY,
        webhook_secret=WEBHOOK_KEY,
        cipher=SyntheticVault(),
        authorize_staff=authorize,
        source_suppressed=lambda source: False,
        ingest_in_transaction=backend.ingest_in_transaction,
        clock=backend.clock,
        mapping=TypeformMapping(
            inquiry_field_id="inquiry",
            inquiry_choices={
                "owner-choice": "owner",
                "rep-choice": "representative",
                "partner-choice": "partnership",
            },
        ),
    )


def payload(reference="response-one", email="owner@example.com", kind="owner-choice"):
    return {
        "event_type": "form_response",
        "form_response": {
            "form_id": "xzx5SBJb",
            "token": reference,
            "submitted_at": "2026-09-18T12:00:00Z",
            "response_type": "completed",
            "hidden": {"landing_path": "/apply/"},
            "answers": [
                {"field": {"id": "oY3yxQa3CAD3"}, "type": "email", "email": email},
                {
                    "field": {"id": "inquiry"},
                    "type": "choice",
                    "choice": {"id": kind, "label": "Untrusted display label"},
                },
            ],
        },
    }


def signed(inbox, value=None):
    raw = json.dumps(value or payload()).encode()
    signature = (
        "sha256="
        + base64.b64encode(hmac.new(WEBHOOK_KEY, raw, hashlib.sha256).digest()).decode()
    )
    return inbox.receive_typeform(raw, signature)


def approve(inbox, entry, request=None, principal="synthetic-live-operator"):
    return inbox.approve(
        principal,
        intake_id=entry["intake_id"],
        request_id=request or str(uuid4()),
        owner_authority_confirmed=True,
    )


def counts(backend):
    with owner_cursor(backend) as cur:
        result = {}
        for table in (
            "intake_admissions",
            "receipts",
            "workspaces",
            "memberships",
            "invitations",
            "outbox",
            "audit",
        ):
            cur.execute("SELECT count(*) AS n FROM " + table)
            result[table] = cur.fetchone()["n"]
        return result


def test_raw_signature_verified_before_parsing(inbox):
    for raw, signature in (
        (b"not json", "wrong"),
        (b"{}", "sha256=" + "a" * 44),
        (b"{}", None),
    ):
        with pytest.raises(ReviewError, match="invalid_intake_signature"):
            inbox.receive_typeform(raw, signature)
    raw = json.dumps(payload()).encode()
    signature = (
        "sha256="
        + base64.b64encode(hmac.new(WEBHOOK_KEY, raw, hashlib.sha256).digest()).decode()
    )
    with pytest.raises(ReviewError, match="signature"):
        inbox.receive_typeform(raw + b" ", signature)
    assert inbox.receive_typeform(raw, signature)["created"]


@pytest.mark.parametrize("raw", [b"", b"x" * (MAX_BODY + 1)])
def test_body_bounded(inbox, raw):
    with pytest.raises(ReviewError, match="body_limit"):
        inbox.receive_typeform(raw, "")


def test_duplicate_json_keys_rejected(inbox):
    raw = b'{"event_type":"ignore","event_type":"form_response"}'
    signature = (
        "sha256="
        + base64.b64encode(hmac.new(WEBHOOK_KEY, raw, hashlib.sha256).digest()).decode()
    )
    with pytest.raises(ReviewError, match="invalid_intake_payload"):
        inbox.receive_typeform(raw, signature)


@pytest.mark.parametrize(
    "change", ["form", "email_field", "duplicate_email", "kind", "time", "reference"]
)
def test_mapping_failures_do_not_admit(inbox, backend, change):
    value = payload()
    form = value["form_response"]
    if change == "form":
        form["form_id"] = "other"
    elif change == "email_field":
        form["answers"][0]["field"]["id"] = "editor-uuid-not-webhook-id"
    elif change == "duplicate_email":
        form["answers"].append(form["answers"][0])
    elif change == "kind":
        form["answers"][1]["choice"]["id"] = "unmapped-choice"
    elif change == "time":
        form["submitted_at"] = "2026-09-18T12:10:00Z"
    else:
        form["token"] = "not/a/reference"
    with pytest.raises(ReviewError):
        signed(inbox, value)
    assert not any(counts(backend).values())


def test_partial_and_other_event_ignored(inbox, backend):
    value = payload()
    value["form_response"]["response_type"] = "partial"
    assert signed(inbox, value) == {"status": "ignored"}
    value["event_type"] = "other"
    assert signed(inbox, value) == {"status": "ignored"}
    assert not any(counts(backend).values())


def test_source_dedup_not_email_and_changed_fingerprint_conflicts(inbox, backend):
    first = signed(inbox)
    assert signed(inbox) == {**first, "created": False}
    second = signed(inbox, payload("response-two"))
    assert second["intake_id"] != first["intake_id"]
    with pytest.raises(ReviewError, match="intake_reference_conflict"):
        signed(inbox, payload(email="changed@example.com"))
    assert not any(counts(backend).values())


def test_dedup_ignores_unmapped_answers_but_tracks_kind(inbox):
    entry = signed(inbox)
    value = payload()
    value["form_response"]["answers"].append(
        {"type": "text", "text": "NOT RETAINED", "field": {"id": "irrelevant"}}
    )
    value["form_response"]["answers"][1]["choice"]["label"] = "different display label"
    assert signed(inbox, value)["intake_id"] == entry["intake_id"]
    with pytest.raises(ReviewError, match="intake_reference_conflict"):
        signed(inbox, payload(kind="partner-choice"))


def test_concurrent_receipts_have_one_durable_entry(inbox):
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: signed(inbox), range(5)))
    assert sum(item["created"] for item in results) == 1
    assert len({item["intake_id"] for item in results}) == 1


def test_manual_formspree_requires_staff_and_stable_internal_receipt(inbox, backend):
    receipt_id = str(uuid4())
    args = dict(
        receipt_id=receipt_id,
        email="owner@example.com",
        submitted_at="2026-09-18T12:00:00Z",
    )
    with pytest.raises(ReviewError, match="operator_required"):
        inbox.record_formspree_receipt({"role": "operator", "mfa": True}, **args)
    first = inbox.record_formspree_receipt("synthetic-live-operator", **args)
    assert inbox.record_formspree_receipt("synthetic-live-operator", **args) == {
        **first,
        "created": False,
    }
    other = signed(inbox, payload(receipt_id))
    assert other["intake_id"] != first["intake_id"]
    with owner_cursor(backend) as cur:
        cur.execute(
            "SELECT source,form_id,recorded_by FROM intake_inbox WHERE intake_id=%s",
            (first["intake_id"],),
        )
        assert dict(cur.fetchone()) == {
            "source": "short_form",
            "form_id": "mpwdnokz",
            "recorded_by": OPERATOR,
        }


def test_generic_email_validated_but_current_synthetic_core_still_blocks_real_admission(
    inbox, backend
):
    entry = signed(inbox, payload(email="Owner+tag@EXAMPLE.ORG"))
    assert normalize_email("Owner+tag@EXAMPLE.ORG") == "Owner+tag@example.org"
    with pytest.raises(Exception):
        approve(inbox, entry)
    assert not any(counts(backend).values())


@pytest.mark.parametrize(
    "email",
    [
        "x@example.com\nBcc: a@b.com",
        "a..b@example.com",
        ".a@example.com",
        "a@-example.com",
        "a@example",
        "a@a..com",
        None,
    ],
)
def test_email_rejects_header_injection_and_bad_mailboxes(email):
    with pytest.raises(ReviewError):
        normalize_email(email)


def test_approval_is_atomic_and_exactly_replayable(inbox, backend):
    entry, request = signed(inbox), str(uuid4())
    result = approve(inbox, entry, request)
    assert result["created"] and result["slot"] == 1
    assert approve(inbox, entry, request) == {**result, "created": False}
    assert all(value == 1 for value in counts(backend).values())
    with pytest.raises(ReviewError, match="approval_request_conflict"):
        approve(inbox, entry)
    with pytest.raises(ReviewError, match="operator_required"):
        approve(inbox, entry, request, principal=None)


def test_callback_failure_rolls_back_core_and_admission(inbox, backend):
    entry = signed(inbox)
    original = inbox._ingest

    def fail(cur, item, **kwargs):
        original(cur, item, **kwargs)
        raise RuntimeError("synthetic failure after core writes")

    inbox._ingest = fail
    with pytest.raises(RuntimeError):
        approve(inbox, entry)
    assert not any(counts(backend).values())
    inbox._ingest = original
    assert approve(inbox, entry)["created"]


def test_post_ingest_coordinator_mismatch_rolls_back(inbox, backend):
    entry, original = signed(inbox), inbox._ingest

    def mismatch(cur, item, **kwargs):
        original(cur, item, **kwargs)
        return {"created": True, "workspace_id": str(uuid4())}

    inbox._ingest = mismatch
    with pytest.raises(ReviewError, match="coordinator_mismatch"):
        approve(inbox, entry)
    assert not any(counts(backend).values())


def test_approval_lost_commit_ack_replays_same_workspace(inbox, backend):
    entry, request, original = signed(inbox), str(uuid4()), inbox.db

    class LostAck:
        @contextmanager
        def transaction(self, *args):
            with original.transaction(*args) as cur:
                yield cur
            raise CommitOutcomeUnknown("synthetic dropped acknowledgement")

    inbox.db = LostAck()
    with pytest.raises(CommitOutcomeUnknown):
        approve(inbox, entry, request)
    inbox.db = original
    assert approve(inbox, entry, request)["created"] is False
    assert all(value == 1 for value in counts(backend).values())


def test_five_lifetime_admissions_enforced_under_race(inbox, backend):
    entries = [signed(inbox, payload("response-" + str(n))) for n in range(8)]

    def attempt(entry):
        try:
            return approve(inbox, entry)
        except ReviewError as exc:
            assert exc.code == "pilot_admission_limit"
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, entries))
    assert len([r for r in results if r]) == 5
    assert all(value == 5 for value in counts(backend).values())
    with owner_cursor(backend) as cur:
        cur.execute("UPDATE workspaces SET status='deletion_requested'")
    assert attempt(entries[results.index(None)]) is None


def test_parallel_same_approval_has_one_admission(inbox, backend):
    entry, request = signed(inbox), str(uuid4())
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: approve(inbox, entry, request), range(5)))
    assert sum(r["created"] for r in results) == 1
    assert all(value == 1 for value in counts(backend).values())


def test_partnership_never_admitted_and_confirmation_is_explicit(inbox, backend):
    entry = signed(inbox, payload(kind="partner-choice"))
    with pytest.raises(ReviewError, match="partnership_not_pilot_eligible"):
        approve(inbox, entry)
    with pytest.raises(ReviewError, match="confirmation_required"):
        inbox.approve(
            "synthetic-live-operator",
            intake_id=entry["intake_id"],
            request_id=str(uuid4()),
            owner_authority_confirmed=1,
        )
    assert not any(counts(backend).values())


def test_source_key_rotation_fails_closed_and_webhook_rotation_keeps_identity(
    inbox, backend
):
    entry = signed(inbox)
    args = dict(
        cipher=inbox._cipher,
        authorize_staff=authorize,
        ingest_in_transaction=backend.ingest_in_transaction,
        source_suppressed=lambda source: False,
        mapping=inbox.mapping,
        clock=backend.clock,
    )
    with pytest.raises(ReviewError, match="source_key_migration_required"):
        IntakeService(
            backend.db,
            source_key=b"different-stable-source-key-00000",
            webhook_secret=WEBHOOK_KEY,
            **args,
        )
    new_key = b"new-webhook-key-00000000000000000"
    rotated = IntakeService(
        backend.db, source_key=SOURCE_KEY, webhook_secret=new_key, **args
    )
    raw = json.dumps(payload()).encode()
    signature = (
        "sha256="
        + base64.b64encode(hmac.new(new_key, raw, hashlib.sha256).digest()).decode()
    )
    assert rotated.receive_typeform(raw, signature) == {**entry, "created": False}


def test_ciphertext_context_binding_and_no_raw_payload_stored(inbox, backend, caplog):
    first, second = signed(inbox), signed(inbox, payload("other"))
    with owner_cursor(backend) as cur:
        cur.execute("SELECT * FROM intake_inbox")
        stored = repr(cur.fetchall())
        assert (
            "owner@example.com" not in stored
            and "Untrusted display label" not in stored
        )
        cur.execute(
            """UPDATE intake_inbox SET payload_cipher=(SELECT payload_cipher FROM intake_inbox WHERE intake_id=%s)
            WHERE intake_id=%s""",
            (second["intake_id"], first["intake_id"]),
        )
    with pytest.raises(ReviewError, match="intake_integrity_failed"):
        approve(inbox, first)
    assert "owner@example.com" not in caplog.text
    assert SOURCE_KEY.decode() not in repr(inbox)


def test_runtime_cannot_remove_admissions_to_reset_limit(inbox, backend):
    approve(inbox, signed(inbox))
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with backend.db.transaction() as cur:
            cur.execute("DELETE FROM intake_admissions")


def source_for(inbox, reference="response-one"):
    return inbox._digest("source-v1", ["typeform", "xzx5SBJb", reference])


def test_suppressed_unadmitted_source_never_persists_or_encrypts(inbox, backend):
    suppressed = {source_for(inbox)}
    inbox._source_suppressed = suppressed.__contains__
    assert signed(inbox) == {"status": "suppressed"}
    assert not inbox._cipher.values
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS n FROM intake_inbox")
        assert cur.fetchone()["n"] == 0
    assert signed(inbox, payload("distinct-source"))["created"]


def test_suppression_journal_failure_fails_closed(inbox, backend):
    def unavailable(source):
        raise RuntimeError("synthetic journal unavailable")

    inbox._source_suppressed = unavailable
    with pytest.raises(RuntimeError, match="journal unavailable"):
        signed(inbox)
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS n FROM intake_inbox")
        assert cur.fetchone()["n"] == 0
    assert not inbox._cipher.values


@pytest.mark.parametrize("admitted", [False, True])
def test_restored_inbox_is_hidden_and_cannot_read_or_admit(inbox, admitted):
    entry, request = signed(inbox), str(uuid4())
    if admitted:
        approve(inbox, entry, request)
    inbox._source_suppressed = {source_for(inbox)}.__contains__
    assert signed(inbox) == {"status": "suppressed"}
    assert inbox.list_receipts("synthetic-live-operator") == []
    with pytest.raises(ReviewError, match="intake_suppressed"):
        inbox.read_receipt("synthetic-live-operator", entry["intake_id"])
    with pytest.raises(ReviewError, match="intake_suppressed"):
        approve(inbox, entry, request)


@pytest.fixture
def erasure_worker(inbox, backend):
    with owner_cursor(backend) as cur:
        cur.execute(Path("services/catalog_review/erasure-grants.sql").read_text())
        cur.execute("GRANT SELECT ON intake_inbox,intake_admissions TO review_erasure")
        cur.execute(
            "GRANT SELECT(workspace_id) ON portal_mail_attempts TO review_erasure"
        )
        cur.execute(
            "GRANT DELETE ON intake_inbox,portal_mail_attempts TO review_erasure"
        )
        cur.execute("GRANT UPDATE(payload_cipher) ON intake_inbox TO review_erasure")
        cur.execute("""GRANT UPDATE(intake_id,workspace_id,request_id,approved_by,erased_at)
            ON intake_admissions TO review_erasure""")
    return ErasureDatabase(
        backend.test_runtime_dsn.replace("user=review_runtime", "user=review_erasure")
    )


def enqueue(backend, workspace):
    with backend.db.transaction(workspace) as cur:
        cur.execute("SELECT invitation_id FROM invitations")
        invitation = str(cur.fetchone()["invitation_id"])
        MailDispatcher.enqueue_in_transaction(
            cur, workspace, invitation, backend.clock()
        )


def test_erasure_requires_source_journal_before_deleting(
    erasure_worker, inbox, backend
):
    workspace = approve(inbox, signed(inbox))["workspace_id"]
    enqueue(backend, workspace)
    participant = IntakeErasureParticipant(source_suppressed=lambda source: False)
    with pytest.raises(ReviewError, match="source_suppression_required"):
        with erasure_worker.transaction(workspace) as cur:
            participant.erase_in_transaction(cur, workspace)
    with owner_cursor(backend) as cur:
        for table in ("intake_inbox", "intake_admissions", "portal_mail_attempts"):
            cur.execute("SELECT count(*) AS n FROM " + table)
            assert cur.fetchone()["n"] == 1


def test_erasure_participant_rolls_back_with_core_transaction(
    erasure_worker, inbox, backend
):
    workspace = approve(inbox, signed(inbox))["workspace_id"]
    enqueue(backend, workspace)
    participant = IntakeErasureParticipant(source_suppressed=lambda source: True)
    with pytest.raises(RuntimeError, match="core erasure failed"):
        with erasure_worker.transaction(workspace) as cur:
            participant.erase_in_transaction(cur, workspace)
            raise RuntimeError("core erasure failed")
    with owner_cursor(backend) as cur:
        for table in ("intake_inbox", "portal_mail_attempts"):
            cur.execute("SELECT count(*) AS n FROM " + table)
            assert cur.fetchone()["n"] == 1
        cur.execute("SELECT workspace_id,erased_at FROM intake_admissions")
        row = cur.fetchone()
        assert str(row["workspace_id"]) == workspace and row["erased_at"] is None


def test_worker_erasure_removes_payload_and_core_fk_but_keeps_lifetime_slot(
    erasure_worker, inbox, backend
):
    entries = [signed(inbox, payload("response-" + str(n))) for n in range(6)]
    workspaces = [approve(inbox, entry)["workspace_id"] for entry in entries[:5]]
    workspace = workspaces[0]
    enqueue(backend, workspace)
    primary, replica = replicated_journal(backend)
    journal = backend.deletion_journal
    source = source_for(inbox, "response-0")
    journal.record(
        workspace, source, requested_at=backend.clock(), reason="owner_request"
    )
    # Partial write: source stop survived, but workspace key/second replica did not.
    del primary.values[journal._key("workspace", workspace)]
    replica.values.clear()
    assert journal.suppresses(source) and not journal.contains(workspace)
    orphan = workspace + "/orphan-without-document-row"
    other_object = workspaces[1] + "/other-case"
    backend.test_blobs.put_if_absent(orphan, b"synthetic orphan")
    backend.test_blobs.put_if_absent(other_object, b"synthetic other case")

    class EmptyBackup:
        def erase_and_verify(self, value):
            assert value == workspace
            assert len(primary.values) == 2 and primary.values == replica.values
            assert orphan not in backend.test_blobs.objects

    inbox._source_suppressed = journal.suppresses
    participant = IntakeErasureParticipant(source_suppressed=journal.suppresses)
    for _ in range(2):
        result = erase_workspace(
            erasure_worker,
            journal,
            workspace,
            backend.test_blobs,
            EmptyBackup(),
            extensions=(participant,),
        )
        assert result["portal_records_erased"]
        assert backend.test_blobs.objects == {other_object: b"synthetic other case"}
    with owner_cursor(backend) as cur:
        cur.execute("SELECT * FROM intake_admissions WHERE slot=1")
        tombstone = cur.fetchone()
        assert tombstone["erased_at"] is not None
        assert all(
            tombstone[k] is None
            for k in ("intake_id", "workspace_id", "request_id", "approved_by")
        )
        cur.execute("SELECT count(*) AS n FROM intake_admissions")
        assert cur.fetchone()["n"] == 5
        cur.execute(
            "SELECT 1 FROM intake_inbox WHERE intake_id=%s", (entries[0]["intake_id"],)
        )
        assert cur.fetchone() is None
        cur.execute(
            "SELECT 1 FROM portal_mail_attempts WHERE workspace_id=%s", (workspace,)
        )
        assert cur.fetchone() is None
        cur.execute("SELECT 1 FROM workspaces WHERE workspace_id=%s", (workspace,))
        assert cur.fetchone() is None
        cur.execute("SELECT 1 FROM workspaces WHERE workspace_id=%s", (workspaces[1],))
        assert cur.fetchone() is not None
    assert signed(inbox, payload("response-0")) == {"status": "suppressed"}
    with pytest.raises(ReviewError, match="pilot_admission_limit"):
        approve(inbox, entries[5])


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM intake_inbox",
        "DELETE FROM portal_mail_attempts",
        "UPDATE intake_admissions SET intake_id=NULL,workspace_id=NULL,request_id=NULL,approved_by=NULL,erased_at=now()",
    ],
)
def test_runtime_has_no_erasure_privilege(inbox, backend, statement):
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with backend.db.transaction() as cur:
            cur.execute(statement)


@pytest.fixture
def intake_client(inbox):
    app = FastAPI()
    app.include_router(
        create_intake_router(
            inbox,
            origin="https://review.test",
            staff_identity=lambda request: (
                "synthetic-live-operator"
                if request.cookies.get("test-staff") == "opaque"
                else None
            ),
            validate_csrf=lambda request, principal: (
                request.headers.get("x-csrf-token") == "test-csrf"
            ),
            admit_webhook=lambda request: (
                request.headers.get("x-test-throttled") != "true"
            ),
        )
    )
    with TestClient(app, base_url="https://review.test") as client:
        yield client


def webhook_headers(raw):
    return {
        "content-type": "application/json",
        "typeform-signature": "sha256="
        + base64.b64encode(
            hmac.new(WEBHOOK_KEY, raw, hashlib.sha256).digest()
        ).decode(),
    }


STAFF_HEADERS = {
    "origin": "https://review.test",
    "sec-fetch-site": "same-origin",
    "x-csrf-token": "test-csrf",
    "cookie": "test-staff=opaque",
}


def test_webhook_commits_before_generic_ack_and_dedups(intake_client, inbox, backend):
    raw = json.dumps(payload()).encode()
    for _ in range(2):
        response = intake_client.post(
            "/api/intake/typeform", content=raw, headers=webhook_headers(raw)
        )
        assert response.status_code == 202
        assert response.json() == {"status": "request_received"}
        assert response.headers["cache-control"] == "no-store"
        with owner_cursor(backend) as cur:
            cur.execute("SELECT count(*) AS n FROM intake_inbox")
            assert cur.fetchone()["n"] == 1
    inbox._source_suppressed = lambda source: True
    assert (
        intake_client.post(
            "/api/intake/typeform", content=raw, headers=webhook_headers(raw)
        ).json()
        == response.json()
    )


def test_webhook_commit_unknown_is_not_202_but_retry_reconciles(
    intake_client, inbox, backend
):
    original = inbox.db

    class LostAck:
        @contextmanager
        def transaction(self):
            with original.transaction() as cur:
                yield cur
            raise CommitOutcomeUnknown("private diagnostic")

    inbox.db = LostAck()
    raw = json.dumps(payload()).encode()
    response = intake_client.post(
        "/api/intake/typeform", content=raw, headers=webhook_headers(raw)
    )
    assert response.status_code == 503
    assert response.json() == {"error": "temporarily_unavailable"}
    inbox.db = original
    assert (
        intake_client.post(
            "/api/intake/typeform", content=raw, headers=webhook_headers(raw)
        ).status_code
        == 202
    )
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS n FROM intake_inbox")
        assert cur.fetchone()["n"] == 1


@pytest.mark.parametrize(
    "kind,status",
    [
        ("signature", 401),
        ("duplicate_signature", 401),
        ("body", 413),
        ("origin", 403),
        ("same_site", 403),
        ("query", 403),
        ("host", 403),
        ("throttle", 429),
        ("content_type", 415),
    ],
)
def test_webhook_boundary(intake_client, backend, kind, status):
    raw = json.dumps(payload()).encode()
    headers = webhook_headers(raw)
    url = "/api/intake/typeform"
    if kind == "signature":
        headers["typeform-signature"] = "bad"
    elif kind == "duplicate_signature":
        headers = list(headers.items()) + [
            ("typeform-signature", headers["typeform-signature"])
        ]
    elif kind == "body":
        raw = b"x" * (MAX_BODY + 1)
    elif kind == "origin":
        headers["origin"] = "https://spacemusic.io"
    elif kind == "same_site":
        headers["sec-fetch-site"] = "same-site"
    elif kind == "query":
        url += "?token=not-allowed"
    elif kind == "host":
        url = "https://spacemusic.io" + url
    elif kind == "throttle":
        headers["x-test-throttled"] = "true"
    else:
        headers["content-type"] = "text/plain"
    assert intake_client.post(url, content=raw, headers=headers).status_code == status
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS n FROM intake_inbox")
        assert cur.fetchone()["n"] == 0


def test_webhook_stream_limit_without_content_length(intake_client):
    chunks = [b"x" * MAX_BODY, b"x"]
    response = intake_client.post(
        "/api/intake/typeform",
        content=iter(chunks),
        headers=webhook_headers(b"".join(chunks)),
    )
    assert "content-length" not in response.request.headers
    assert response.status_code == 413


@pytest.mark.parametrize(
    "change,status",
    [
        ({"origin": "https://spacemusic.io"}, 403),
        ({"sec-fetch-site": "same-site"}, 403),
        ({"x-csrf-token": "invalid"}, 403),
        ({"cookie": ""}, 401),
    ],
)
def test_staff_endpoint_rejects_sibling_origin_and_untrusted_auth(
    intake_client, change, status
):
    response = intake_client.post(
        "/api/staff/intakes/formspree-receipt",
        json={},
        headers={**STAFF_HEADERS, **change},
    )
    assert response.status_code == status


def test_staff_receipt_read_and_explicit_approval_routes(intake_client, inbox):
    value = {
        "receipt_id": str(uuid4()),
        "email": "owner@example.com",
        "submitted_at": "2026-09-18T12:00:00Z",
    }
    first = intake_client.post(
        "/api/staff/intakes/formspree-receipt", json=value, headers=STAFF_HEADERS
    )
    assert first.status_code == 202
    intake_id = first.json()["intake_id"]
    assert (
        intake_client.post(
            "/api/staff/intakes/formspree-receipt", json=value, headers=STAFF_HEADERS
        ).json()["created"]
        is False
    )
    listing = intake_client.get("/api/staff/intakes", headers=STAFF_HEADERS)
    assert listing.status_code == 200 and len(listing.json()["intakes"]) == 1
    assert "email" not in listing.text and "source_digest" not in listing.text
    detail = intake_client.get("/api/staff/intakes/" + intake_id, headers=STAFF_HEADERS)
    assert detail.json()["email"] == value["email"]
    value = {"request_id": str(uuid4()), "owner_authority_confirmed": True}
    response = intake_client.post(
        f"/api/staff/intakes/{intake_id}/approve", json=value, headers=STAFF_HEADERS
    )
    assert response.status_code == 200 and response.json()["created"]
    assert not intake_client.post(
        f"/api/staff/intakes/{intake_id}/approve", json=value, headers=STAFF_HEADERS
    ).json()["created"]


@pytest.mark.parametrize(
    "body",
    [
        '{"request_id":"x","request_id":"y","owner_authority_confirmed":true}',
        '{"request_id":"x","owner_authority_confirmed":true,"mfa":true}',
        '{"request_id":"x","owner_authority_confirmed":NaN}',
    ],
)
def test_staff_rejects_duplicate_or_claim_fields(intake_client, body):
    response = intake_client.post(
        f"/api/staff/intakes/{uuid4()}/approve",
        content=body,
        headers={**STAFF_HEADERS, "content-type": "application/json"},
    )
    assert response.status_code == 422


class PendingJournal:
    def __init__(self):
        self.sources = set()
        self.records = []

    def suppresses(self, source):
        return source in self.sources

    def record(self, target, source, *, requested_at, reason):
        self.records.append((target, source, requested_at, reason))
        self.sources.add(source)


def pending_eraser(inbox, backend, erasure_worker, journal):
    inbox._source_suppressed = journal.suppresses
    return IntakeErasureParticipant(
        source_suppressed=journal.suppresses,
        database=erasure_worker,
        clock=backend.clock,
    )


def test_pending_purge_90_days_skip_admitted_and_never_extend_on_replay(
    inbox, backend, erasure_worker
):
    pending = signed(inbox)
    admitted = signed(inbox, payload("admitted"))
    approve(inbox, admitted)
    with owner_cursor(backend) as cur:
        cur.execute(
            "SELECT * FROM intake_inbox WHERE intake_id=%s", (pending["intake_id"],)
        )
        original = cur.fetchone()
    backend.clock.advance(6 * 86400)
    assert signed(inbox)["created"] is False
    with owner_cursor(backend) as cur:
        cur.execute(
            "SELECT received_at,submitted_at FROM intake_inbox WHERE intake_id=%s",
            (pending["intake_id"],),
        )
        assert cur.fetchone() == {
            k: original[k] for k in ("received_at", "submitted_at")
        }
    backend.clock.advance(85 * 86400)
    fresh = payload("fresh")
    fresh["form_response"]["submitted_at"] = backend.clock().isoformat()
    signed(inbox, fresh)
    journal = PendingJournal()
    eraser = pending_eraser(inbox, backend, erasure_worker, journal)
    cutoff = backend.clock() - timedelta(days=90)
    assert eraser.purge_pending_receipts(cutoff, journal) == {"purged": 1}
    assert journal.records == [
        (pending["intake_id"], original["source_digest"], backend.clock(), "inactivity")
    ]
    assert eraser.purge_pending_receipts(cutoff, journal) == {"purged": 0}
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS n FROM intake_inbox")
        assert cur.fetchone()["n"] == 2
    # Same source with a new timestamp still cannot create a fresh inbox row.
    replay = payload()
    replay["form_response"]["submitted_at"] = backend.clock().isoformat()
    assert signed(inbox, replay) == {"status": "suppressed"}
    # Simulate restoring the old ciphertext row; journal remains authoritative.
    with owner_cursor(backend) as cur:
        cur.execute(
            "INSERT INTO intake_inbox VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            tuple(original.values()),
        )
    assert all(
        str(row["intake_id"]) != pending["intake_id"]
        for row in inbox.list_receipts("synthetic-live-operator")
    )
    with pytest.raises(ReviewError, match="intake_suppressed"):
        inbox.read_receipt("synthetic-live-operator", pending["intake_id"])
    with pytest.raises(ReviewError, match="intake_suppressed"):
        approve(inbox, pending)


@pytest.mark.parametrize("days", [0, 89])
def test_pending_purge_refuses_recent_cutoff(inbox, backend, erasure_worker, days):
    signed(inbox)
    journal = PendingJournal()
    eraser = pending_eraser(inbox, backend, erasure_worker, journal)
    with pytest.raises(ReviewError, match="retention_cutoff_invalid"):
        eraser.purge_pending_receipts(backend.clock() - timedelta(days=days), journal)
    assert not journal.records


def test_pending_purge_journal_failure_keeps_ciphertext(inbox, backend, erasure_worker):
    entry = signed(inbox)
    backend.clock.advance(91 * 86400)

    class FailedJournal(PendingJournal):
        def record(self, *args, **kwargs):
            super().record(*args, **kwargs)
            raise RuntimeError("replica unavailable")

    journal = FailedJournal()
    eraser = pending_eraser(inbox, backend, erasure_worker, journal)
    with pytest.raises(RuntimeError, match="replica unavailable"):
        eraser.purge_pending_receipts(backend.clock() - timedelta(days=90), journal)
    with owner_cursor(backend) as cur:
        cur.execute(
            "SELECT payload_cipher FROM intake_inbox WHERE intake_id=%s",
            (entry["intake_id"],),
        )
        assert cur.fetchone()["payload_cipher"]
    assert inbox.list_receipts("synthetic-live-operator") == []


@pytest.mark.parametrize("winner", ["approval", "purge"])
def test_pending_purge_and_approval_serialize_on_one_advisory_lock(
    inbox, backend, erasure_worker, winner
):
    entry = signed(inbox)
    backend.clock.advance(91 * 86400)
    journal = PendingJournal()
    eraser = pending_eraser(inbox, backend, erasure_worker, journal)
    cutoff = backend.clock() - timedelta(days=90)
    entered, release, other_started = Event(), Event(), Event()
    original_ingest = inbox._ingest
    original_record = journal.record

    def blocked_ingest(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return original_ingest(*args, **kwargs)

    def blocked_record(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return original_record(*args, **kwargs)

    def approval():
        if winner != "approval":
            other_started.set()
        return approve(inbox, entry)

    def purge():
        if winner != "purge":
            other_started.set()
        return eraser.purge_pending_receipts(cutoff, journal)

    if winner == "approval":
        inbox._ingest = blocked_ingest
    else:
        journal.record = blocked_record
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(approval if winner == "approval" else purge)
        assert entered.wait(2)
        second = pool.submit(purge if winner == "approval" else approval)
        assert other_started.wait(2)
        with pytest.raises(FutureTimeout):
            second.result(timeout=0.05)
        release.set()
        if winner == "approval":
            assert first.result()["created"]
            assert second.result() == {"purged": 0}
            assert not journal.records
        else:
            assert first.result() == {"purged": 1}
            with pytest.raises(ReviewError, match="intake_unavailable"):
                second.result()


def test_pending_purge_runtime_cannot_lock_or_delete(inbox, backend):
    signed(inbox)
    backend.clock.advance(91 * 86400)
    journal = PendingJournal()
    eraser = pending_eraser(inbox, backend, backend.db, journal)
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        eraser.purge_pending_receipts(backend.clock() - timedelta(days=90), journal)
    assert not journal.records


@pytest.mark.parametrize("recent_column", ["received_at", "submitted_at"])
def test_pending_purge_requires_both_immutable_dates_old(
    inbox, backend, erasure_worker, recent_column
):
    signed(inbox)
    backend.clock.advance(91 * 86400)
    with owner_cursor(backend) as cur:
        cur.execute(
            "UPDATE intake_inbox SET " + recent_column + "=%s", (backend.clock(),)
        )
    journal = PendingJournal()
    eraser = pending_eraser(inbox, backend, erasure_worker, journal)
    assert eraser.purge_pending_receipts(
        backend.clock() - timedelta(days=90), journal
    ) == {"purged": 0}
    assert not journal.records
    for database in (backend.db, erasure_worker):
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            with database.transaction() as cur:
                cur.execute("UPDATE intake_inbox SET " + recent_column + "=now()")


def test_pending_purge_commit_loss_leaves_suppression_and_retry_is_safe(
    inbox, backend, erasure_worker
):
    signed(inbox)
    backend.clock.advance(91 * 86400)
    journal = PendingJournal()
    eraser = pending_eraser(inbox, backend, erasure_worker, journal)

    class LostCommit:
        @contextmanager
        def transaction(self):
            with erasure_worker.transaction() as cur:
                yield cur
            raise CommitOutcomeUnknown("synthetic commit acknowledgement lost")

    eraser.db = LostCommit()
    cutoff = backend.clock() - timedelta(days=90)
    with pytest.raises(CommitOutcomeUnknown):
        eraser.purge_pending_receipts(cutoff, journal)
    eraser.db = erasure_worker
    assert eraser.purge_pending_receipts(cutoff, journal) == {"purged": 0}
    replay = payload()
    replay["form_response"]["submitted_at"] = backend.clock().isoformat()
    assert signed(inbox, replay) == {"status": "suppressed"}


def test_pending_purge_serializes_inflight_receipt_before_suppression_check(
    inbox, backend, erasure_worker
):
    signed(inbox)
    backend.clock.advance(91 * 86400)
    journal = PendingJournal()
    eraser = pending_eraser(inbox, backend, erasure_worker, journal)
    entered, release = Event(), Event()
    original = journal.record

    def blocked_record(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return original(*args, **kwargs)

    journal.record = blocked_record
    replay = payload()
    replay["form_response"]["submitted_at"] = backend.clock().isoformat()
    with ThreadPoolExecutor(max_workers=2) as pool:
        purge = pool.submit(
            eraser.purge_pending_receipts, backend.clock() - timedelta(days=90), journal
        )
        assert entered.wait(2)
        receipt = pool.submit(signed, inbox, replay)
        with pytest.raises(FutureTimeout):
            receipt.result(timeout=0.05)
        release.set()
        assert purge.result() == {"purged": 1}
        assert receipt.result() == {"status": "suppressed"}
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS n FROM intake_inbox")
        assert cur.fetchone()["n"] == 0
