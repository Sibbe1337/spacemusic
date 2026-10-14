import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import psycopg2
import pytest
from conftest import draft, owner_cursor, sign_in
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.catalog_review.contracts import ReviewMessage
from services.catalog_review.database import Database
from services.catalog_review.http import COOKIE, create_test_app
from services.catalog_review.security import ReviewError


def reviewer(service, workspace, *, mfa=True):
    """Fixture identity only, never a public login/provisioning endpoint."""
    principal = str(uuid4())
    token = workspace + "." + secrets.token_urlsafe(32)
    with owner_cursor(service) as cur:
        cur.execute(
            "INSERT INTO memberships VALUES(%s,%s,'reviewer',true)",
            (workspace, principal),
        )
        cur.execute(
            "INSERT INTO sessions VALUES(%s,%s,%s,%s,%s)",
            (
                workspace,
                service._hash("session", token),
                principal,
                mfa,
                service.clock() + timedelta(hours=1),
            ),
        )
    return token


def package(service):
    workspace, owner, _ = sign_in(service)
    service.save_draft(owner, {"revision": 0, "draft": draft()})
    service.submit(owner, {"request_id": str(uuid4()), "revision": 1, "consent": True})
    return workspace, owner, reviewer(service, workspace)


def message(body="Please clarify the missing reporting period."):
    return {"request_id": str(uuid4()), "body": body}


def test_question_reply_and_snapshot_remains_immutable(backend):
    _, owner, staff = package(backend)
    before = backend.view(owner)["submission"]
    assert backend.view(owner)["review_status"] == "submitted"
    request = message()
    result = backend.ask_question(staff, request)
    assert result["created"]
    assert backend.ask_question(staff, request) == {**result, "created": False}
    assert backend.view(owner)["review_status"] == "needs_information"
    question = backend.view(owner)["questions"][0]
    assert set(question) == {
        "question_id",
        "body",
        "created_at",
        "reply",
        "request_documents",
    }
    assert question["reply"] is None
    reply = message("Those statements are not available yet.")
    response = backend.reply_to_question(owner, result["question_id"], reply)
    assert response["created"]
    assert (
        backend.reply_to_question(owner, result["question_id"], reply)["created"]
        is False
    )
    after = backend.view(staff)
    assert after["review_status"] == "under_review"
    assert after["questions"][0]["reply"]["body"] == reply["body"]
    assert after["submission"] == before


def test_no_review_before_submission_and_owner_cannot_ask(backend):
    workspace, owner, _ = sign_in(backend)
    staff = reviewer(backend, workspace)
    with pytest.raises(ReviewError, match="submission_required"):
        backend.ask_question(staff, message())
    with pytest.raises(ReviewError, match="reviewer_required"):
        backend.ask_question(owner, message())


def test_assigned_reviewer_mfa_and_current_membership(backend):
    workspace, owner, staff = package(backend)
    without_mfa = reviewer(backend, workspace, mfa=False)
    with pytest.raises(ReviewError, match="authentication_required"):
        backend.ask_question(without_mfa, message())
    question = backend.ask_question(staff, message())["question_id"]
    with pytest.raises(ReviewError, match="owner_required"):
        backend.reply_to_question(staff, question, message())
    with owner_cursor(backend) as cur:
        cur.execute(
            "UPDATE memberships SET active=false WHERE workspace_id=%s AND role='reviewer'",
            (workspace,),
        )
    with pytest.raises(ReviewError, match="authentication_required"):
        backend.ask_question(staff, message())


def test_question_isolation_and_unassigned_reviewer(backend):
    first, owner, staff = package(backend)
    second, other, _ = sign_in(backend, "second")
    outsider = reviewer(backend, second)
    qid = backend.ask_question(staff, message())["question_id"]
    assert backend.view(other)["questions"] == []
    with pytest.raises(ReviewError, match="question_unavailable"):
        backend.reply_to_question(other, qid, message())
    with pytest.raises(ReviewError):
        backend.view(first + "." + outsider.split(".")[1])
    with backend.db.transaction(second) as cur:
        cur.execute("SELECT * FROM review_questions")
        assert not cur.fetchall()
    with backend.db.transaction() as cur:
        cur.execute("SELECT * FROM review_questions")
        assert not cur.fetchall()
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with backend.db.transaction(first) as cur:
            cur.execute("UPDATE review_questions SET body='changed'")


def test_replay_with_different_body_author_or_question_is_rejected(backend):
    workspace, owner, staff = package(backend)
    request = message()
    qid = backend.ask_question(staff, request)["question_id"]
    with pytest.raises(ReviewError, match="message_request_conflict"):
        backend.ask_question(staff, {**request, "body": "different"})
    with pytest.raises(ReviewError, match="message_request_conflict"):
        backend.ask_question(reviewer(backend, workspace), request)
    reply = message("Answer")
    backend.reply_to_question(owner, qid, reply)
    for changed in [message("Second answer"), {**reply, "body": "Changed answer"}]:
        with pytest.raises(ReviewError, match="reply_locked"):
            backend.reply_to_question(owner, qid, changed)
    other_qid = backend.ask_question(staff, message())["question_id"]
    with pytest.raises(ReviewError, match="reply_locked"):
        backend.reply_to_question(owner, other_qid, reply)


def test_concurrent_double_click_creates_one_question_and_reply(backend):
    _, owner, staff = package(backend)
    request = message()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: backend.ask_question(staff, request), range(2))
        )
    assert sorted(r["created"] for r in results) == [False, True]
    reply = message("Answer")
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda _: backend.reply_to_question(
                    owner, results[0]["question_id"], reply
                ),
                range(2),
            )
        )
    assert sorted(r["created"] for r in replies) == [False, True]


def test_question_limit_and_replay_at_limit(backend):
    _, _, staff = package(backend)
    first = message()
    backend.ask_question(staff, first)
    for _ in range(19):
        backend.ask_question(staff, message())
    assert backend.ask_question(staff, first)["created"] is False
    with pytest.raises(ReviewError, match="question_limit_reached"):
        backend.ask_question(staff, message())


@pytest.mark.parametrize(
    "body", ["", " \n\t", "x" * 4001, "bad\x00text", "bad\x01text", 1, True]
)
def test_message_validation(body):
    with pytest.raises(ValidationError):
        ReviewMessage.model_validate(message(body))


@pytest.mark.parametrize(
    "statement",
    [
        "ALTER TABLE review_questions DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE review_replies NO FORCE ROW LEVEL SECURITY",
        "GRANT UPDATE(body) ON review_questions TO review_runtime",
        "GRANT DELETE ON review_replies TO review_runtime",
        "GRANT TRUNCATE ON review_questions TO review_runtime",
    ],
)
def test_review_table_misconfiguration_blocks_startup(backend, statement):
    with owner_cursor(backend) as cur:
        cur.execute(statement)
    with pytest.raises(RuntimeError):
        Database(backend.test_runtime_dsn)


def test_expiry_and_deletion_stop_conversation(backend):
    workspace, owner, staff = package(backend)
    qid = backend.ask_question(staff, message())["question_id"]
    backend.request_deletion(owner)
    for call in [
        lambda: backend.ask_question(staff, message()),
        lambda: backend.reply_to_question(owner, qid, message()),
    ]:
        with pytest.raises(ReviewError, match="workspace_unavailable"):
            call()


def test_http_questions_require_csrf_and_roles(backend):
    _, owner, staff = package(backend)
    with TestClient(
        create_test_app(backend), base_url="https://review.test"
    ) as browser:
        browser.cookies.set(COOKIE, staff)
        headers = {"origin": "https://review.test", "x-csrf-token": backend.csrf(staff)}
        assert browser.post("/api/portal/questions", json=message()).status_code == 403
        response = browser.post(
            "/api/portal/questions", json=message(), headers=headers
        )
        assert response.status_code == 200
        qid = response.json()["question_id"]
        browser.cookies.set(COOKIE, owner)
        headers["x-csrf-token"] = backend.csrf(owner)
        assert (
            browser.post(
                "/api/portal/questions", json=message(), headers=headers
            ).status_code
            == 403
        )
        assert (
            browser.post(
                f"/api/portal/questions/{qid}/reply", json=message(), headers=headers
            ).status_code
            == 200
        )
        assert browser.post(
            "/api/portal/questions/not-a-uuid/reply", json=message(), headers=headers
        ).json() == {"error": "invalid_fields"}
