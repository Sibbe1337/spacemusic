import secrets
import subprocess
from dataclasses import replace
from uuid import uuid4

import pytest
from conftest import draft, owner_cursor, receipt, sign_in

from services.catalog_review.lifecycle import (
    JournalUnavailable,
    ReplicatedDeletionJournal,
)
from services.catalog_review.security import ReviewError
from services.catalog_review.service import ReviewService


class Replica:
    def __init__(self, name):
        self.identity, self.values, self.fail = name, {}, False

    def read(self, key):
        if self.fail:
            raise JournalUnavailable("unavailable")
        return self.values.get(key)

    def append(self, key, content):
        if self.fail:
            raise JournalUnavailable("unavailable")
        self.values.setdefault(key, content)
        assert self.values[key] == content


def journal(service):
    primary, replica = Replica("EU-primary"), Replica("Paris-independent")
    service.deletion_journal = ReplicatedDeletionJournal(primary, replica)
    return primary, replica


def test_meaningful_changes_only_and_notice_window(backend):
    workspace, owner, _ = sign_in(backend)
    initial = backend.retention_state(workspace)
    backend.clock.advance(100)
    backend.view(owner)
    assert backend.retention_state(workspace) == initial
    backend.save_draft(owner, {"revision": 0, "draft": draft()})
    changed = backend.retention_state(workspace)
    assert changed["activity_version"] == 1
    backend.clock.advance(100)
    assert backend.save_draft(owner, {"revision": 1, "draft": draft()}) == {
        "revision": 1
    }
    assert backend.retention_state(workspace) == changed
    request = str(uuid4())
    assert backend.continue_interest(owner, request)["created"]
    current = backend.retention_state(workspace)
    backend.clock.advance(100)
    assert not backend.continue_interest(owner, request)["created"]
    assert backend.retention_state(workspace) == current
    backend.clock.advance(76 * 86400)
    assert backend.retention_state(workspace)["notice_due"]
    assert not backend.retention_state(workspace)["deletion_due"]


def test_retention_rechecks_version_under_lock(backend):
    journal(backend)
    workspace, owner, _ = sign_in(backend)
    old = backend.retention_state(workspace)
    backend.continue_interest(owner, str(uuid4()))
    backend.clock.advance(91 * 86400)
    assert backend.expire_inactive(workspace, old["activity_version"]) == {
        "expired": False
    }
    current = backend.retention_state(workspace)
    assert backend.expire_inactive(workspace, current["activity_version"])["expired"]
    assert backend.deletion_journal.contains(workspace)


def test_journal_failure_is_not_acknowledged_or_treated_as_empty(backend):
    _, replica = journal(backend)
    workspace, owner, _ = sign_in(backend)
    replica.fail = True
    with pytest.raises(JournalUnavailable):
        backend.request_deletion(owner)
    with pytest.raises(JournalUnavailable):
        backend.view(owner)
    replica.fail = False
    assert backend.view(owner)["workspace_id"] == workspace


def test_partial_replication_blocks_access_even_when_local_commit_rolls_back(backend):
    primary, replica = journal(backend)
    workspace, owner, _ = sign_in(backend)
    original = replica.append
    replica.append = lambda *_: (_ for _ in ()).throw(JournalUnavailable("lost ack"))
    with pytest.raises(JournalUnavailable):
        backend.request_deletion(owner)
    assert primary.values
    with pytest.raises(ReviewError, match="workspace_unavailable"):
        backend.view(owner)
    replica.append = original
    with owner_cursor(backend) as db:
        db.execute(
            "SELECT source_digest FROM receipts WHERE workspace_id=%s", (workspace,)
        )
        source = db.fetchone()["source_digest"]
    assert backend.deletion_journal.suppresses(source)
    assert not backend.deletion_journal.contains(workspace)
    # Partial replication can be retried through the owner API, not an unsafe
    # manual bypass. Source suppression already prevents a recreated case.
    assert backend.request_deletion(owner)["status"] == "deletion_requested"
    assert primary.values == replica.values
    assert backend.deletion_journal.contains(workspace)


def test_partial_source_tombstone_survives_restore_predating_intake(backend):
    _, replica = journal(backend)
    workspace, owner, _ = sign_in(backend)
    append = replica.append
    replica.append = lambda *_: (_ for _ in ()).throw(JournalUnavailable("lost ack"))
    with pytest.raises(JournalUnavailable):
        backend.request_deletion(owner)
    replica.append = append
    with owner_cursor(backend) as db:
        db.execute("TRUNCATE workspaces,receipts CASCADE")
    with pytest.raises(ReviewError, match="intake_suppressed"):
        backend.ingest(receipt())


def test_operator_can_reconcile_partial_journal_without_owner_session(backend):
    primary, replica = journal(backend)
    workspace, owner, _ = sign_in(backend)
    append = replica.append
    replica.append = lambda *_: (_ for _ in ()).throw(JournalUnavailable("lost ack"))
    with pytest.raises(JournalUnavailable):
        backend.request_deletion(owner)
    replica.append = append
    with owner_cursor(backend) as db:
        db.execute(
            "SELECT source_digest FROM receipts WHERE workspace_id=%s", (workspace,)
        )
        source = db.fetchone()["source_digest"]
    assert backend.deletion_journal.reconcile(workspace, source)
    assert primary.values == replica.values


def test_old_database_backup_does_not_restore_access_files_or_mail(backend):
    journal(backend)
    workspace, owner, invitation = sign_in(backend)
    document = backend.quarantine(
        owner, "statement.csv", b"a,b\n1,2", backend.test_blobs
    )["document_id"]
    dump = subprocess.run(
        [
            "pg_dump",
            "--dbname",
            backend.test_owner_dsn,
            "--data-only",
            "--no-owner",
            "--no-privileges",
        ],
        check=True,
        capture_output=True,
    ).stdout
    backend.request_deletion(owner)
    with owner_cursor(backend) as db:
        db.execute("TRUNCATE workspaces,receipts,auth_limits CASCADE")
    subprocess.run(
        [
            "psql",
            "--dbname",
            backend.test_owner_dsn,
            "--single-transaction",
            "--set",
            "ON_ERROR_STOP=1",
        ],
        input=dump,
        check=True,
        capture_output=True,
    )
    for operation in (
        lambda: backend.view(owner),
        lambda: backend.exchange_invitation(invitation),
        lambda: backend.download(owner, document, backend.test_blobs),
        lambda: backend.claim_scan(workspace, document),
        lambda: backend.claim_invitation(workspace),
    ):
        with pytest.raises(ReviewError, match="workspace_unavailable"):
            operation()
    with pytest.raises(ReviewError, match="intake_suppressed"):
        backend.ingest(receipt())


def test_auth_key_rotation_does_not_change_source_identity(backend):
    stable = secrets.token_bytes(32)
    settings = replace(backend.settings, source_identity_key=stable)
    before = ReviewService(backend.db, settings, backend.clock)
    first = before.ingest(receipt())
    after = ReviewService(
        backend.db,
        replace(
            settings,
            digest_key=secrets.token_bytes(32),
            signing_key=secrets.token_bytes(32),
        ),
        backend.clock,
    )
    assert after.ingest(receipt()) == {**first, "created": False}


def test_export_is_owner_only_without_tokens_or_storage_keys(backend):
    from test_review import package

    _, owner, staff = package(backend)
    exported = backend.export_case(owner)
    assert exported["submission"]
    assert "session" not in str(exported)
    assert "token_digest" not in str(exported)
    with pytest.raises(ReviewError, match="owner_required"):
        backend.export_case(staff)
