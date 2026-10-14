from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg2
import pytest
from conftest import owner_cursor, sign_in
from fastapi.testclient import TestClient
from test_review import message, package

from services.catalog_review.http import COOKIE, create_test_app
from services.catalog_review.security import ReviewError


def upload(service, owner, question, request_id=None):
    return service.quarantine(
        owner,
        "statement.csv",
        b"month,net\n2026-01,100\n",
        service.test_blobs,
        request_id or str(uuid4()),
        question,
    )


def accept(service, workspace, document):
    job = service.claim_scan(workspace, document)
    service.complete_scan(job, clean=True, scanned_sha256=job["sha256"])


def test_supplement_hidden_until_published_and_original_unchanged(backend):
    workspace, owner, staff = package(backend)
    original = backend.view(owner)["submission"]
    q = backend.ask_question(staff, {**message(), "request_documents": True})[
        "question_id"
    ]
    d = upload(backend, owner, q)["document_id"]
    accept(backend, workspace, d)
    assert len(backend.view(owner)["documents"]) == 1
    assert backend.view(staff)["documents"] == []
    with pytest.raises(ReviewError, match="document_unavailable"):
        backend.download(staff, d, backend.test_blobs)
    body = {**message("Attached the requested statements."), "document_ids": [d]}
    backend.reply_to_question(owner, q, body)
    before = backend.view(staff)
    assert before["questions"][0]["reply"]["supplement"]["version"] == 1
    assert before["submission"] == original
    assert backend.download(staff, d, backend.test_blobs)[1].startswith(b"month")
    assert not backend.reply_to_question(owner, q, body)["created"]
    assert backend.view(staff) == before
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with backend.db.transaction(workspace) as db:
            db.execute("UPDATE review_supplements SET version=7")


def test_scoped_upload_replay_after_reply_but_new_upload_rejected(backend):
    workspace, owner, staff = package(backend)
    q = backend.ask_question(staff, {**message(), "request_documents": True})[
        "question_id"
    ]
    request = str(uuid4())
    d = upload(backend, owner, q, request)["document_id"]
    accept(backend, workspace, d)
    backend.reply_to_question(owner, q, {**message("Attached."), "document_ids": [d]})
    assert upload(backend, owner, q, request)["document_id"] == d
    with pytest.raises(ReviewError, match="open_document_request_required"):
        upload(backend, owner, q)
    with pytest.raises(ReviewError, match="upload_request_conflict"):
        upload(backend, owner, None, request)


def test_cross_question_unpublished_files_and_quarantine_cannot_be_attached(backend):
    workspace, owner, staff = package(backend)
    q1, q2 = [
        backend.ask_question(staff, {**message(), "request_documents": True})[
            "question_id"
        ]
        for _ in range(2)
    ]
    d = upload(backend, owner, q1)["document_id"]
    with pytest.raises(ReviewError, match="documents_not_ready"):
        backend.reply_to_question(owner, q1, {**message(), "document_ids": [d]})
    accept(backend, workspace, d)
    with pytest.raises(ReviewError, match="document_question_mismatch"):
        backend.reply_to_question(owner, q2, {**message(), "document_ids": [d]})
    backend.reply_to_question(owner, q1, {**message("Published"), "document_ids": [d]})
    backend.reply_to_question(
        owner, q2, {**message("Same source applies"), "document_ids": [d]}
    )
    published = next(
        q for q in backend.view(owner)["questions"] if q["question_id"] == q2
    )
    assert published["reply"]["supplement"]["version"] == 2


def test_question_flag_replay_conflict_and_text_only_request(backend):
    _, owner, staff = package(backend)
    req = message()
    q = backend.ask_question(staff, req)["question_id"]
    with pytest.raises(ReviewError, match="message_request_conflict"):
        backend.ask_question(staff, {**req, "request_documents": True})
    with pytest.raises(ReviewError, match="open_document_request_required"):
        upload(backend, owner, q)


def test_global_40_limit_and_concurrent_same_reply(backend):
    workspace, owner, staff = package(backend)
    q = backend.ask_question(staff, {**message(), "request_documents": True})[
        "question_id"
    ]
    documents = [upload(backend, owner, q)["document_id"] for _ in range(40)]
    with pytest.raises(ReviewError, match="document_limit_reached"):
        upload(backend, owner, q)
    accept(backend, workspace, documents[0])
    req = {**message("Attached."), "document_ids": documents[:1]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: backend.reply_to_question(owner, q, req), range(2))
        )
    assert sorted(r["created"] for r in results) == [False, True]
    with owner_cursor(backend) as db:
        db.execute("SELECT count(*) AS n FROM review_supplements")
        assert db.fetchone()["n"] == 1


def test_sibling_origin_rejected_for_reads_and_scoped_http_upload(backend):
    _, owner, staff = package(backend)
    q = backend.ask_question(staff, {**message(), "request_documents": True})[
        "question_id"
    ]
    with TestClient(
        create_test_app(backend, document_store=backend.test_blobs),
        base_url="https://review.test",
    ) as client:
        client.cookies.set(COOKIE, owner)
        assert (
            client.get(
                "/api/portal/workspace", headers={"sec-fetch-site": "same-site"}
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/api/portal/workspace", headers={"origin": "https://other.review.test"}
            ).status_code
            == 403
        )
        headers = {
            "origin": "https://review.test",
            "x-csrf-token": backend.csrf(owner),
            "x-upload-id": str(uuid4()),
            "content-type": "application/octet-stream",
            "x-document-name": "statement.csv",
        }
        assert (
            client.post(
                f"/api/portal/questions/{q}/documents",
                headers=headers,
                content=b"a,b\n1,2",
            ).status_code
            == 202
        )
        _, outsider, _ = sign_in(backend, "outside")
        client.cookies.set(COOKIE, outsider)
        headers["x-csrf-token"] = backend.csrf(outsider)
        assert (
            client.post(
                f"/api/portal/questions/{q}/documents",
                headers=headers,
                content=b"a,b\n1,2",
            ).status_code
            == 409
        )
