"""Private, manually reviewed deal preparation. No model or delivery transport."""

import hashlib
import json
from datetime import datetime, time, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from psycopg2.extras import Json

from .dealflow_contracts import PackageRequest, ReviewRecord, ShareDecision
from .dealflow_policy import assess
from .security import ReviewError, workspace_from_token


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            jsonable_encoder(value), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


class Dealflow:
    def _dealflow_authorize(self, db, token, *, reviewer=False, owner=False):
        workspace, member, state = self._authorize(db, token, owner=owner)
        if not self.dealflow_enabled:
            raise ReviewError("dealflow_disabled", 404)
        if reviewer and member["role"] != "reviewer":
            raise ReviewError("reviewer_required", 403)
        return workspace, member, state

    def _dealflow_sources(self, db):
        db.execute("SELECT submission_id,snapshot,created_at FROM submissions")
        submission = db.fetchone()
        if not submission:
            raise ReviewError("submission_required", 409)
        questions = self._conversation(db)
        sources = [
            {
                "id": "submission:" + str(submission["submission_id"]),
                "label": "Submitted catalog scope",
                "kind": "submission",
            }
        ]
        docs = {str(d["document_id"]): d for d in submission["snapshot"]["documents"]}
        for question in questions:
            if question["reply"]:
                sources.append(
                    {
                        "id": "reply:" + question["question_id"],
                        "label": "Published reply " + question["question_id"],
                        "kind": "reply",
                    }
                )
                for doc in (question["reply"]["supplement"] or {}).get("documents", []):
                    docs[str(doc["document_id"])] = doc
        # Published snapshots choose visibility. Current scan status still fences use.
        for identifier in sorted(docs):
            db.execute(
                "SELECT document_id,filename,sha256,status FROM documents WHERE document_id=%s",
                (identifier,),
            )
            current = db.fetchone()
            if (
                not current
                or current["status"] != "accepted_for_review"
                or current["sha256"] != docs[identifier]["sha256"]
            ):
                raise ReviewError("published_evidence_unavailable", 409)
            sources.append(
                {
                    "id": "document:" + identifier,
                    "label": current["filename"],
                    "kind": "document",
                    "sha256": current["sha256"],
                }
            )
        return {
            "digest": fingerprint(
                {"submission": submission, "questions": questions, "sources": sources}
            ),
            "sources": sources,
        }

    @staticmethod
    def _dealflow_latest(db):
        db.execute("SELECT * FROM dealflow_reviews ORDER BY revision DESC LIMIT 1")
        return db.fetchone()

    def _package_status(self, db, package, review, source_digest):
        db.execute(
            "SELECT decision FROM dealflow_decisions WHERE package_id=%s ORDER BY sequence DESC LIMIT 1",
            (package["package_id"],),
        )
        decision = db.fetchone()
        if (
            not review
            or package["revision"] != review["revision"]
            or review["source_digest"] != source_digest
        ):
            return "stale"
        if package["expires_at"] <= self.clock():
            return "expired"
        return decision["decision"] if decision else "awaiting_owner_approval"

    def dealflow_view(self, token):
        with self.db.transaction(workspace_from_token(token)) as db:
            _, member, _ = self._dealflow_authorize(db, token)
            evidence = self._dealflow_sources(db)
            review = self._dealflow_latest(db)
            db.execute("SELECT * FROM dealflow_packages ORDER BY created_at,package_id")
            packages = db.fetchall()
            result = {
                "role": member["role"],
                "revision": review["revision"] if review else 0,
                "packages": [],
            }
            for package in packages:
                result["packages"].append(
                    {
                        "package_id": str(package["package_id"]),
                        "payload": package["payload"],
                        "digest": package["digest"],
                        "expires_at": package["expires_at"],
                        "status": self._package_status(
                            db, package, review, evidence["digest"]
                        ),
                    }
                )
            if member["role"] == "reviewer":
                result.update(
                    {
                        "evidence": evidence,
                        "review": review["body"] if review else None,
                        "assessment": assess(
                            review["body"] if review else None,
                            stale=bool(
                                review and review["source_digest"] != evidence["digest"]
                            ),
                            today=self.clock().date(),
                        ),
                    }
                )
            return result

    def save_dealflow_review(self, token, value):
        item = ReviewRecord.model_validate(value)
        body = item.model_dump(
            mode="json", exclude={"request_id", "revision", "source_digest"}
        )
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, member, _ = self._dealflow_authorize(db, token, reviewer=True)
            db.execute(
                "SELECT * FROM dealflow_reviews WHERE request_id=%s",
                (str(item.request_id),),
            )
            prior = db.fetchone()
            if prior:
                if (
                    prior["author_id"] != member["principal_id"]
                    or prior["body"] != body
                    or prior["source_digest"] != item.source_digest
                    or prior["revision"] != item.revision + 1
                ):
                    raise ReviewError("review_request_conflict", 409)
                return {"revision": prior["revision"], "created": False}
            evidence = self._dealflow_sources(db)
            latest = self._dealflow_latest(db)
            revision = latest["revision"] if latest else 0
            if revision != item.revision or evidence["digest"] != item.source_digest:
                raise ReviewError("review_stale", 409)
            if revision >= 100:
                raise ReviewError("review_limit_reached", 409)
            if (
                latest
                and latest["body"] == body
                and latest["source_digest"] == item.source_digest
            ):
                raise ReviewError("no_review_change", 409)
            references = {source["id"]: source for source in evidence["sources"]}
            for check in item.checks:
                if any(reference not in references for reference in check.sources):
                    raise ReviewError("evidence_reference_unavailable", 422)
                if (
                    check.status == "reviewed"
                    and check.key in ("ownership", "income", "agreements", "catalog")
                    and not any(
                        references[s]["kind"] == "document" for s in check.sources
                    )
                ):
                    raise ReviewError("document_evidence_required", 422)
            today = self.clock().date()
            if item.period_end and item.period_end >= today:
                raise ReviewError("completed_reporting_period_required", 422)
            if any(b.checked_on > today for b in item.buyers):
                raise ReviewError("future_mandate_check", 422)
            db.execute(
                "INSERT INTO dealflow_reviews VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    workspace,
                    revision + 1,
                    str(item.request_id),
                    member["principal_id"],
                    item.source_digest,
                    Json(body),
                    self.clock(),
                ),
            )
            self._touch(db, workspace)
            return {"revision": revision + 1, "created": True}

    def prepare_dealflow_package(self, token, value):
        item = PackageRequest.model_validate(value)
        request_body = item.model_dump(mode="json", exclude={"request_id"})
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, member, _ = self._dealflow_authorize(db, token, reviewer=True)
            db.execute(
                "SELECT * FROM dealflow_packages WHERE request_id=%s",
                (str(item.request_id),),
            )
            prior = db.fetchone()
            if prior:
                if (
                    prior["request_body"] != request_body
                    or prior["author_id"] != member["principal_id"]
                ):
                    raise ReviewError("package_request_conflict", 409)
                return {"package_id": str(prior["package_id"]), "created": False}
            evidence = self._dealflow_sources(db)
            review = self._dealflow_latest(db)
            if (
                not review
                or review["revision"] != item.revision
                or review["source_digest"] != evidence["digest"]
            ):
                raise ReviewError("review_stale", 409)
            body = review["body"]
            assessment = assess(body, stale=False, today=self.clock().date())
            match = next(
                (
                    m
                    for m in assessment["matches"]
                    if m["buyer_id"] == str(item.buyer_id)
                ),
                None,
            )
            if not match or match["status"] != "candidate_for_introduction":
                raise ReviewError("introduction_not_ready", 409)
            selected = [
                s
                for s in evidence["sources"]
                if s["id"] in {"document:" + str(d) for d in item.document_ids}
            ]
            if len(selected) != len(item.document_ids):
                raise ReviewError("evidence_reference_unavailable", 422)
            db.execute("SELECT count(*) AS count FROM dealflow_packages")
            if db.fetchone()["count"] >= 50:
                raise ReviewError("package_limit_reached", 409)
            buyer = next(
                b for b in body["buyers"] if b["buyer_id"] == str(item.buyer_id)
            )
            payload = {
                "recipient": {"buyer_id": buyer["buyer_id"], "name": buyer["name"]},
                "purpose": "One private catalog introduction to this recipient only. No resale of contact data, onward circulation or mailing-list enrollment.",
                "rights": body["rights"],
                "structure": body["structure"],
                "seller_goal": body["seller_goal"],
                "exclusions": body["exclusions"],
                "future_music_excluded": True,
                "reported_financials": {
                    k: body[k]
                    for k in ("annual_net", "currency", "period_start", "period_end")
                },
                "review_notes": [
                    {"key": c["key"], "status": c["status"], "note": c["note"]}
                    for c in body["checks"]
                ],
                "documents": selected,
                "limitations": "Reviewed preparation only; not a valuation, warranty of ownership, legal opinion or confirmed buyer interest. Only listed documents are approved for this proposed introduction. Other source documents are not included.",
                "review_revision": review["revision"],
                "source_digest": evidence["digest"],
            }
            identifier = str(uuid4())
            expires = min(
                self.clock() + timedelta(days=7),
                datetime.combine(
                    datetime.fromisoformat(buyer["expires_on"]).date()
                    + timedelta(days=1),
                    time.min,
                    timezone.utc,
                ),
            )
            db.execute(
                "INSERT INTO dealflow_packages VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    workspace,
                    identifier,
                    str(item.request_id),
                    item.revision,
                    member["principal_id"],
                    Json(request_body),
                    Json(payload),
                    fingerprint(payload),
                    self.clock(),
                    expires,
                ),
            )
            self._touch(db, workspace)
            return {"package_id": identifier, "created": True}

    def decide_dealflow_package(self, token, package_id, value):
        item = ShareDecision.model_validate(value)
        package_id = str(UUID(str(package_id)))
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, member, _ = self._dealflow_authorize(db, token, owner=True)
            db.execute(
                "SELECT * FROM dealflow_decisions WHERE request_id=%s",
                (str(item.request_id),),
            )
            prior = db.fetchone()
            if prior:
                if (
                    str(prior["package_id"]) != package_id
                    or prior["digest"] != item.digest
                    or prior["decision"] != item.decision
                    or prior["author_id"] != member["principal_id"]
                ):
                    raise ReviewError("decision_request_conflict", 409)
                return {"created": False}
            db.execute(
                "SELECT * FROM dealflow_packages WHERE package_id=%s", (package_id,)
            )
            package = db.fetchone()
            if not package or package["digest"] != item.digest:
                raise ReviewError("package_unavailable", 404)
            db.execute(
                "SELECT decision FROM dealflow_decisions WHERE package_id=%s ORDER BY sequence DESC LIMIT 1",
                (package_id,),
            )
            previous = db.fetchone()
            if previous and previous["decision"] == item.decision:
                return {"created": False}
            if previous and previous["decision"] in ("revoked", "declined"):
                raise ReviewError("new_package_required", 409)
            if item.decision == "approved":
                evidence = self._dealflow_sources(db)
                status = self._package_status(
                    db, package, self._dealflow_latest(db), evidence["digest"]
                )
                if status != "awaiting_owner_approval":
                    raise ReviewError("new_package_required", 409)
            db.execute(
                "SELECT COALESCE(max(sequence),0) AS sequence FROM dealflow_decisions"
            )
            sequence = db.fetchone()["sequence"]
            if sequence >= 200:
                raise ReviewError("decision_limit_reached", 409)
            db.execute(
                "INSERT INTO dealflow_decisions VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    workspace,
                    sequence + 1,
                    str(item.request_id),
                    package_id,
                    member["principal_id"],
                    item.digest,
                    item.decision,
                    self.clock(),
                ),
            )
            self._touch(db, workspace)
            return {"created": True}

    def approved_dealflow_package(self, token, package_id):
        """Internal preview only. No public link, attachment transfer or sending."""
        with self.db.transaction(workspace_from_token(token)) as db:
            self._dealflow_authorize(db, token, reviewer=True)
            db.execute(
                "SELECT * FROM dealflow_packages WHERE package_id=%s",
                (str(UUID(str(package_id))),),
            )
            package = db.fetchone()
            if not package:
                raise ReviewError("package_unavailable", 404)
            evidence = self._dealflow_sources(db)
            if (
                self._package_status(
                    db, package, self._dealflow_latest(db), evidence["digest"]
                )
                != "approved"
            ):
                raise ReviewError("owner_approval_required", 409)
            return {
                "payload": package["payload"],
                "digest": package["digest"],
                "delivery_enabled": False,
            }
