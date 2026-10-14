from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from conftest import owner_cursor, sign_in
from test_lifecycle import journal

from services.catalog_review.erasure import (
    ErasureDatabase,
    ErasureUnconfirmed,
    VersionedBackupStore,
    erase_workspace,
)
from services.catalog_review.security import ReviewError


class BackupClient:
    def __init__(self, workspace):
        self.meta = SimpleNamespace(
            endpoint_url="https://s3.fr-par.scw.cloud",
            config=SimpleNamespace(read_timeout=5, connect_timeout=5),
        )
        self._endpoint = SimpleNamespace(
            host="https://s3.fr-par.scw.cloud",
            http_session=SimpleNamespace(_verify=True),
        )
        self.items = [
            {"Key": workspace + "/doc", "VersionId": "one"},
            {"Key": workspace + "/doc", "VersionId": "two"},
        ]
        self.deleted, self.keep = [], False

    def list_object_versions(self, **kwargs):
        assert kwargs["Prefix"].endswith("/")
        return {
            "Versions": self.items[:1],
            "DeleteMarkers": self.items[1:],
            "IsTruncated": False,
        }

    def delete_object(self, Bucket, **item):
        self.deleted.append(item)
        if not self.keep:
            self.items.remove(item)


def test_actual_versions_checked_not_lifecycle_flag(backend):
    workspace, _, _ = sign_in(backend)
    client = BackupClient(workspace)
    store = VersionedBackupStore(client, "synthetic-backup")
    client.keep = True
    with pytest.raises(ErasureUnconfirmed, match="remain"):
        store.erase_and_verify(workspace)
    client.keep = False
    store.erase_and_verify(workspace)
    assert client.items == []


def test_backup_transport_requires_verified_tls_before_every_inventory(backend):
    workspace, _, _ = sign_in(backend)
    client = BackupClient(workspace)
    client._endpoint.http_session._verify = False
    with pytest.raises(ValueError, match="TLS"):
        VersionedBackupStore(client, "synthetic")
    client._endpoint.http_session._verify = True
    store = VersionedBackupStore(client, "synthetic")
    client._endpoint.http_session._verify = False
    with pytest.raises(ValueError, match="TLS"):
        store.erase_and_verify(workspace)
    assert client.deleted == []


def test_erasure_cannot_run_without_journal_or_use_runtime_delete(backend):
    journal(backend)
    workspace, owner, _ = sign_in(backend)
    store = VersionedBackupStore(BackupClient(workspace), "synthetic")
    with pytest.raises(ReviewError, match="durable_deletion_required"):
        erase_workspace(
            backend.db, backend.deletion_journal, workspace, backend.test_blobs, store
        )
    backend.request_deletion(owner)
    # Runtime credentials deliberately cannot erase immutable evidence.
    import psycopg2

    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        erase_workspace(
            backend.db, backend.deletion_journal, workspace, backend.test_blobs, store
        )


def test_deletion_serializes_with_inflight_upload(backend):
    journal(backend)
    workspace, owner, _ = sign_in(backend)
    entered, release = Event(), Event()
    original = backend.test_blobs.put_if_absent

    def blocked_put(key, value):
        entered.set()
        assert release.wait(2)
        original(key, value)

    backend.test_blobs.put_if_absent = blocked_put
    with ThreadPoolExecutor(max_workers=2) as pool:
        upload = pool.submit(
            backend.quarantine, owner, "statement.csv", b"a,b\n1,2", backend.test_blobs
        )
        assert entered.wait(2)
        deletion = pool.submit(backend.request_deletion, owner)
        release.set()
        document = upload.result()["document_id"]
        assert deletion.result()["status"] == "deletion_requested"
    with owner_cursor(backend) as db:
        db.execute(
            "SELECT count(*) AS n FROM documents WHERE workspace_id=%s", (workspace,)
        )
        assert db.fetchone()["n"] == 1  # Retained manifest lets the eraser find it.
    with pytest.raises(ReviewError, match="workspace_unavailable"):
        backend.claim_scan(workspace, document)


def test_scoped_erasure_removes_case_but_keeps_other_case_and_source_suppression(
    backend,
):
    journal(backend)
    workspace, owner, _ = sign_in(backend)
    other, other_owner, _ = sign_in(backend, "other")
    backend.quarantine(owner, "statement.csv", b"a,b\n1,2", backend.test_blobs)
    # Simulate storage acceptance followed by a lost DB commit. No document row
    # exists for this key, so only an independent prefix inventory can find it.
    orphan = workspace + "/" + str(uuid4())
    backend.test_blobs.put_if_absent(orphan, b"private orphan")
    foreign = other + "/" + str(uuid4())
    backend.test_blobs.put_if_absent(foreign, b"other customer")
    backend.request_deletion(owner)
    with owner_cursor(backend) as db:
        db.execute(Path("services/catalog_review/erasure-grants.sql").read_text())
    eraser = ErasureDatabase(
        backend.test_owner_dsn.replace("user=review_migration", "user=review_erasure")
    )

    def erase_live(key):
        backend.test_blobs.delete(key)
        assert key not in backend.test_blobs.objects

    backend.test_blobs.delete_and_verify = erase_live
    result = erase_workspace(
        eraser,
        backend.deletion_journal,
        workspace,
        backend.test_blobs,
        VersionedBackupStore(BackupClient(workspace), "synthetic"),
    )
    assert result["portal_records_erased"] and not result["all_backups_erased"]
    assert orphan not in backend.test_blobs.objects
    assert backend.test_blobs.objects == {foreign: b"other customer"}
    # Also cover a later orphan with no remaining workspace/document DB rows.
    backend.test_blobs.put_if_absent(orphan, b"late restored orphan")
    erase_workspace(
        eraser,
        backend.deletion_journal,
        workspace,
        backend.test_blobs,
        VersionedBackupStore(BackupClient(workspace), "synthetic"),
    )
    assert orphan not in backend.test_blobs.objects
    assert backend.view(other_owner)["workspace_id"] == other
    with owner_cursor(backend) as db:
        db.execute(
            "SELECT count(*) AS n FROM workspaces WHERE workspace_id=%s", (workspace,)
        )
        assert db.fetchone()["n"] == 0
        db.execute(
            "SELECT source_digest FROM receipts WHERE workspace_id=%s", (workspace,)
        )
        assert backend.deletion_journal.suppresses(db.fetchone()["source_digest"])
