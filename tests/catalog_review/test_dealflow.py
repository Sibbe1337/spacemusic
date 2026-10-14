from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from conftest import draft, owner_cursor, sign_in
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_review import message, reviewer
from test_supplements import accept, upload

from services.catalog_review.dealflow_contracts import CHECKS, ReviewRecord
from services.catalog_review.erasure import (
    ErasureDatabase,
    VersionedBackupStore,
    erase_workspace,
)
from services.catalog_review.http import COOKIE, create_test_app
from services.catalog_review.security import ReviewError


def make_case(service, suffix="first"):
    service.dealflow_enabled = True
    workspace, owner, _ = sign_in(service, suffix)
    doc = service.quarantine(
        owner,
        "evidence.csv",
        b"period,net\n2025,60000\n",
        service.test_blobs,
        str(uuid4()),
    )["document_id"]
    accept(service, workspace, doc)
    service.save_draft(owner, {"revision": 0, "draft": draft([doc])})
    service.submit(owner, {"request_id": str(uuid4()), "revision": 1, "consent": True})
    return workspace, owner, reviewer(service, workspace), doc


def record(service, staff, *, ready=True):
    view = service.dealflow_view(staff)
    source = next(
        s["id"] for s in view["evidence"]["sources"] if s["kind"] == "document"
    )
    return {
        "request_id": str(uuid4()),
        "revision": view["revision"],
        "source_digest": view["evidence"]["digest"],
        "rights": "masters",
        "structure": "partial_sale",
        "seller_goal": "A partial sale of the listed existing masters.",
        "exclusions": "Publishing and all future releases are excluded.",
        "annual_net": "60000.00",
        "currency": "EUR",
        "period_start": "2025-09-01",
        "period_end": "2026-08-31",
        "checks": [
            {
                "key": k,
                "status": "reviewed" if ready else "missing",
                "sources": [source] if ready else [],
                "note": "Synthetic reviewer note, not verification.",
            }
            for k in CHECKS
        ],
        "buyers": [
            {
                "buyer_id": str(uuid4()),
                "name": "Fictional buyer",
                "mandate_reference": "Synthetic mandate dated September 18",
                "checked_on": "2026-09-18",
                "expires_on": "2026-10-18",
                "rights": ["masters"],
                "structures": ["partial_sale"],
                "minimum_annual_net": "50000.00",
                "currency": "EUR",
            }
        ],
    }


def prepare(service, staff, doc, value=None):
    value = value or record(service, staff)
    version = service.save_dealflow_review(staff, value)["revision"]
    request = {
        "request_id": str(uuid4()),
        "revision": version,
        "buyer_id": value["buyers"][0]["buyer_id"],
        "document_ids": [doc],
    }
    result = service.prepare_dealflow_package(staff, request)
    return result["package_id"], request


def decide(service, owner, identifier, decision="approved"):
    item = next(
        p
        for p in service.dealflow_view(owner)["packages"]
        if p["package_id"] == identifier
    )
    value = {"request_id": str(uuid4()), "digest": item["digest"], "decision": decision}
    return service.decide_dealflow_package(owner, identifier, value)


def test_complete_flow_has_no_delivery_or_automatic_valuation(backend):
    _, owner, staff, doc = make_case(backend)
    assert len(backend.dealflow_view(staff)["assessment"]["actions"]) == 6
    identifier, request = prepare(backend, staff, doc)
    assert not backend.prepare_dealflow_package(staff, request)["created"]
    with pytest.raises(ReviewError, match="owner_approval_required"):
        backend.approved_dealflow_package(staff, identifier)
    assert decide(backend, owner, identifier)["created"]
    result = backend.approved_dealflow_package(staff, identifier)
    assert result["delivery_enabled"] is False
    assert len(result["payload"]["review_notes"]) == 6
    assert "valuation" not in result["payload"]
    assert result["payload"]["future_music_excluded"]
    assert "review" not in backend.dealflow_view(owner)
    assert len(backend.export_case(owner)["dealflow_decisions"]) == 1


def test_feature_off_and_auth_boundaries(backend):
    workspace, owner, staff, _ = make_case(backend)
    body = record(backend, staff)
    with pytest.raises(ReviewError, match="reviewer_required"):
        backend.save_dealflow_review(owner, body)
    without_mfa = reviewer(backend, workspace, mfa=False)
    with pytest.raises(ReviewError, match="authentication_required"):
        backend.dealflow_view(without_mfa)
    backend.dealflow_enabled = False
    with pytest.raises(ReviewError, match="dealflow_disabled"):
        backend.dealflow_view(staff)
    with TestClient(create_test_app(backend), base_url="https://review.test") as client:
        client.cookies.set(COOKIE, staff)
        assert client.get("/api/portal/dealflow").status_code == 404


def test_replays_concurrency_and_no_activity_on_reads(backend):
    workspace, owner, staff, _ = make_case(backend)
    body = record(backend, staff)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: backend.save_dealflow_review(staff, body), range(2))
        )
    assert sorted(r["created"] for r in results) == [False, True]
    first = backend.export_case(owner)["workspace"][0]["last_activity_at"]
    backend.clock.advance(30)
    backend.dealflow_view(staff)
    backend.save_dealflow_review(staff, body)
    assert backend.export_case(owner)["workspace"][0]["last_activity_at"] == first
    with pytest.raises(ReviewError, match="review_request_conflict"):
        backend.save_dealflow_review(staff, {**body, "seller_goal": "Changed"})
    with pytest.raises(ReviewError, match="review_stale"):
        backend.save_dealflow_review(staff, {**body, "request_id": str(uuid4())})
    with backend.db.transaction(str(uuid4())) as db:
        db.execute("SELECT * FROM dealflow_reviews")
        assert db.fetchall() == []
    with (
        pytest.raises(psycopg2.errors.InsufficientPrivilege),
        backend.db.transaction(workspace) as db,
    ):
        db.execute("DELETE FROM dealflow_reviews")


@pytest.mark.parametrize("key", CHECKS)
def test_missing_or_conflicting_check_blocks_introduction(backend, key):
    _, _, staff, doc = make_case(backend)
    body = record(backend, staff)
    next(c for c in body["checks"] if c["key"] == key)["status"] = "conflicting"
    backend.save_dealflow_review(staff, body)
    view = backend.dealflow_view(staff)
    assert view["assessment"]["stage"] == "conflicting_evidence"
    assert key in view["assessment"]["conflicts"]
    with pytest.raises(ReviewError, match="introduction_not_ready"):
        backend.prepare_dealflow_package(
            staff,
            {
                "request_id": str(uuid4()),
                "revision": 1,
                "buyer_id": body["buyers"][0]["buyer_id"],
                "document_ids": [doc],
            },
        )


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"currency": "USD"}, "needs_review"),
        ({"minimum_annual_net": "60000.01"}, "outside_mandate"),
        ({"minimum_annual_net": "60000.00"}, "candidate_for_introduction"),
        ({"rights": ["publishing"]}, "outside_mandate"),
        ({"structures": ["full_sale"]}, "outside_mandate"),
        ({"checked_on": "2026-09-01", "expires_on": "2026-09-17"}, "needs_review"),
    ],
)
def test_explainable_buyer_criteria_no_currency_conversion(backend, changes, expected):
    _, _, staff, _ = make_case(backend)
    body = record(backend, staff)
    body["buyers"][0].update(changes)
    backend.save_dealflow_review(staff, body)
    match = backend.dealflow_view(staff)["assessment"]["matches"][0]
    assert match["status"] == expected
    assert match["reasons"]


def test_zero_revenue_is_not_missing(backend):
    _, _, staff, _ = make_case(backend)
    body = record(backend, staff)
    body["annual_net"] = "0.00"
    body["buyers"][0]["minimum_annual_net"] = "0.00"
    backend.save_dealflow_review(staff, body)
    assert (
        backend.dealflow_view(staff)["assessment"]["matches"][0]["status"]
        == "candidate_for_introduction"
    )


def test_new_published_evidence_and_new_review_invalidate_approval(backend):
    _, owner, staff, doc = make_case(backend)
    identifier, _ = prepare(backend, staff, doc)
    decide(backend, owner, identifier)
    q = backend.ask_question(staff, message("New restriction?"))["question_id"]
    backend.reply_to_question(owner, q, message("There may be a lien."))
    assert backend.dealflow_view(staff)["assessment"]["stage"] == "re_review_required"
    with pytest.raises(ReviewError, match="owner_approval_required"):
        backend.approved_dealflow_package(staff, identifier)
    body = record(backend, staff)
    backend.save_dealflow_review(staff, body)
    assert backend.dealflow_view(owner)["packages"][0]["status"] == "stale"


def test_unpublished_or_foreign_evidence_cannot_be_referenced(backend):
    workspace, owner, staff, _ = make_case(backend)
    q = backend.ask_question(staff, {**message(), "request_documents": True})[
        "question_id"
    ]
    doc = upload(backend, owner, q)["document_id"]
    accept(backend, workspace, doc)
    body = record(backend, staff)
    body["checks"][0]["sources"] = ["document:" + doc]
    with pytest.raises(ReviewError, match="evidence_reference_unavailable"):
        backend.save_dealflow_review(staff, body)
    body["checks"][0]["sources"] = ["document:" + str(uuid4())]
    with pytest.raises(ReviewError, match="evidence_reference_unavailable"):
        backend.save_dealflow_review(staff, body)


def test_submission_claim_alone_is_not_document_review(backend):
    _, _, staff, _ = make_case(backend)
    body = record(backend, staff)
    for check in body["checks"]:
        check["sources"] = [
            backend.dealflow_view(staff)["evidence"]["sources"][0]["id"]
        ]
    with pytest.raises(ReviewError, match="document_evidence_required"):
        backend.save_dealflow_review(staff, body)


def test_revocation_owner_only_and_expiry(backend):
    _, owner, staff, doc = make_case(backend)
    identifier, _ = prepare(backend, staff, doc)
    package = backend.dealflow_view(owner)["packages"][0]
    with pytest.raises(ReviewError, match="owner_required"):
        backend.decide_dealflow_package(
            staff,
            identifier,
            {
                "request_id": str(uuid4()),
                "digest": package["digest"],
                "decision": "approved",
            },
        )
    decide(backend, owner, identifier)
    decide(backend, owner, identifier, "revoked")
    with pytest.raises(ReviewError, match="owner_approval_required"):
        backend.approved_dealflow_package(staff, identifier)
    with pytest.raises(ReviewError, match="new_package_required"):
        decide(backend, owner, identifier)
    # Keep the fixture session valid while advancing only package expiry.
    with owner_cursor(backend) as db:
        db.execute(
            "UPDATE dealflow_packages SET expires_at=%s",
            (backend.clock() - timedelta(seconds=1),),
        )
    assert backend.dealflow_view(owner)["packages"][0]["status"] == "expired"


def test_deletion_stops_access(backend):
    _, owner, staff, doc = make_case(backend)
    identifier, _ = prepare(backend, staff, doc)
    decide(backend, owner, identifier)
    backend.request_deletion(owner)
    with pytest.raises(ReviewError, match="workspace_unavailable"):
        backend.approved_dealflow_package(staff, identifier)


def test_http_origin_csrf_and_cross_case(backend):
    _, _, staff, doc = make_case(backend)
    identifier, _ = prepare(backend, staff, doc)
    _, other, _ = sign_in(backend, "other")
    with pytest.raises(ReviewError, match="package_unavailable"):
        backend.decide_dealflow_package(
            other,
            identifier,
            {"request_id": str(uuid4()), "digest": "a" * 64, "decision": "approved"},
        )
    with TestClient(create_test_app(backend), base_url="https://review.test") as client:
        client.cookies.set(COOKIE, staff)
        assert client.get("/api/portal/dealflow").status_code == 200
        assert (
            client.get(
                "/api/portal/dealflow", headers={"origin": "https://spacemusic.io"}
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/api/portal/dealflow", headers={"sec-fetch-site": "same-site"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/portal/dealflow/reviews",
                json={},
                headers={"origin": "https://review.test"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/portal/dealflow/reviews",
                json={},
                headers={
                    "origin": "https://review.test",
                    "x-csrf-token": backend.csrf(staff),
                },
            ).status_code
            == 422
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b: b.update(annual_net="NaN"),
        lambda b: b.update(currency=None),
        lambda b: b.update(period_start="2026-01-01"),
        lambda b: b.update(rights="unknown"),
        lambda b: b["checks"].pop(),
        lambda b: b["buyers"][0].update(minimum_annual_net="-1"),
        lambda b: b["checks"][0].update(sources=[]),
        lambda b: b.update(arbitrary_customer_field="not allowed"),
    ],
)
def test_invalid_contracts(backend, mutation):
    _, _, staff, _ = make_case(backend)
    body = deepcopy(record(backend, staff))
    mutation(body)
    with pytest.raises(ValidationError):
        ReviewRecord.model_validate(body)


def test_erasure_removes_populated_dealflow_tables_and_preserves_other_case(backend):
    from test_erasure import BackupClient
    from test_lifecycle import journal

    journal(backend)
    workspace, owner, staff, doc = make_case(backend)
    identifier, _ = prepare(backend, staff, doc)
    decide(backend, owner, identifier)
    _, other_owner, other_staff, other_doc = make_case(backend, "other-deal")
    other_package, _ = prepare(backend, other_staff, other_doc)
    decide(backend, other_owner, other_package)
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
    erase_workspace(
        eraser,
        backend.deletion_journal,
        workspace,
        backend.test_blobs,
        VersionedBackupStore(BackupClient(workspace), "synthetic"),
    )
    with owner_cursor(backend) as db:
        for table in ("dealflow_reviews", "dealflow_packages", "dealflow_decisions"):
            db.execute(
                f"SELECT count(*) AS n FROM {table} WHERE workspace_id=%s", (workspace,)
            )
            assert db.fetchone()["n"] == 0
    assert (
        backend.approved_dealflow_package(other_staff, other_package)[
            "delivery_enabled"
        ]
        is False
    )


def test_selected_document_and_decision_replays_are_bound(backend):
    _, owner, staff, doc = make_case(backend)
    identifier, request = prepare(backend, staff, doc)
    with pytest.raises(ReviewError, match="package_request_conflict"):
        backend.prepare_dealflow_package(staff, {**request, "document_ids": []})
    with pytest.raises(ReviewError, match="evidence_reference_unavailable"):
        backend.prepare_dealflow_package(
            staff,
            {**request, "request_id": str(uuid4()), "document_ids": [str(uuid4())]},
        )
    package = backend.dealflow_view(owner)["packages"][0]
    decision = {
        "request_id": str(uuid4()),
        "digest": package["digest"],
        "decision": "approved",
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: backend.decide_dealflow_package(owner, identifier, decision),
                range(2),
            )
        )
    assert sorted(r["created"] for r in results) == [False, True]
    with pytest.raises(ReviewError, match="decision_request_conflict"):
        backend.decide_dealflow_package(
            owner, identifier, {**decision, "decision": "revoked"}
        )


def test_quarantined_or_changed_published_evidence_closes_approval(backend):
    workspace, owner, staff, doc = make_case(backend)
    identifier, _ = prepare(backend, staff, doc)
    decide(backend, owner, identifier)
    with owner_cursor(backend) as db:
        db.execute(
            "UPDATE documents SET sha256=%s WHERE workspace_id=%s AND document_id=%s",
            ("a" * 64, workspace, doc),
        )
    with pytest.raises(ReviewError, match="published_evidence_unavailable"):
        backend.approved_dealflow_package(staff, identifier)
