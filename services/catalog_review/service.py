import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from psycopg2.extras import Json

from .access import AccessRecovery
from .contracts import Draft, Intake, LiveIntake, SaveDraft, Submit, Upload
from .database import CommitOutcomeUnknown
from .dealflow import Dealflow
from .lifecycle import RetentionLifecycle
from .review import ReviewConversation
from .security import ReviewError, digest, workspace_from_token


def utcnow():
    return datetime.now(timezone.utc)


class ReviewService(AccessRecovery, ReviewConversation, RetentionLifecycle, Dealflow):
    def __init__(
        self,
        database,
        settings,
        clock=utcnow,
        *,
        deletion_journal=None,
        staff_authorizer=None,
        intake_exporter=None,
        dealflow_enabled=False,
    ):
        settings.validate()
        self.db, self.settings, self.clock = database, settings, clock
        self.deletion_journal = deletion_journal
        self.staff_authorizer = staff_authorizer
        self.intake_exporter = intake_exporter
        if type(dealflow_enabled) is not bool:
            raise ValueError("Explicit dealflow feature selection required")
        self.dealflow_enabled = dealflow_enabled
        if settings.mode != "test" and deletion_journal is None:
            raise RuntimeError("A real replicated deletion journal is required")
        if settings.mode != "test" and not callable(staff_authorizer):
            raise RuntimeError("Live staff authorization is required")

    def _hash(self, kind, value):
        kind = (
            kind
            if self.settings.mode == "test"
            else self.settings.generation + ":" + kind
        )
        return digest(self.settings.digest_key, kind, value)

    def _source_hash(self, kind, value):
        # The legacy fallback exists only for the isolated test profile.
        key = self.settings.source_identity_key or self.settings.digest_key
        return digest(key, kind, value)

    def _audit(self, db, workspace, action):
        db.execute(
            "INSERT INTO audit VALUES (%s,%s,%s,%s)",
            (workspace, str(uuid4()), action, self.clock()),
        )

    def _touch(self, db, workspace):
        db.execute(
            """UPDATE workspaces SET last_activity_at=%s,
            activity_version=activity_version+1,notice_version=NULL WHERE workspace_id=%s""",
            (self.clock(), workspace),
        )
        db.execute(
            "UPDATE retention_notices SET status='cancelled' WHERE status='queued'"
        )

    def _active(self, db, workspace, *, deletion_retry=False):
        # Membership changes/deletion and protected operations serialize on
        # this row. Revocation takes effect before any later operation begins.
        db.execute(
            "SELECT * FROM workspaces WHERE workspace_id=%s FOR UPDATE", (workspace,)
        )
        row = db.fetchone()
        if not row or (row["status"] != "active" and not deletion_retry):
            raise ReviewError("workspace_unavailable", 404)
        if self.deletion_journal and not deletion_retry:
            db.execute(
                "SELECT source_digest FROM receipts WHERE workspace_id=%s", (workspace,)
            )
            receipt = db.fetchone()
            if self.deletion_journal.contains(workspace) or (
                receipt and self.deletion_journal.suppresses(receipt["source_digest"])
            ):
                raise ReviewError("workspace_unavailable", 404)
        return row

    def _authorize(self, db, token, owner=False, *, deletion_retry=False):
        workspace = workspace_from_token(token)
        if self.settings.mode != "test" or self.staff_authorizer is not None:
            db.execute(
                """SELECT m.role,s.principal_id,l.staff_session_digest FROM sessions s
                JOIN memberships m USING(workspace_id,principal_id)
                LEFT JOIN staff_session_links l USING(workspace_id,token_digest)
                WHERE s.token_digest=%s""",
                (self._hash("session", token),),
            )
            preflight = db.fetchone()
            if preflight and preflight["role"] == "reviewer":
                if not preflight["staff_session_digest"] or not self.staff_authorizer:
                    raise ReviewError("authentication_required", 401)
                # Principal/session first, workspace second: same lock order as
                # supervised revocation and staff context establishment.
                identity = self.staff_authorizer(
                    db, preflight["staff_session_digest"], workspace
                )
                if identity.principal_id != str(preflight["principal_id"]):
                    raise ReviewError("authentication_required", 401)
        state = self._active(db, workspace, deletion_retry=deletion_retry)
        db.execute(
            """SELECT s.principal_id, m.role, s.mfa, s.expires_at FROM sessions s
            JOIN memberships m USING (workspace_id, principal_id)
            WHERE s.workspace_id=%s AND s.token_digest=%s AND s.expires_at>%s
            AND m.active""",
            (workspace, self._hash("session", token), self.clock()),
        )
        member = db.fetchone()
        if not member or (member["role"] == "reviewer" and not member["mfa"]):
            raise ReviewError("authentication_required", 401)
        if owner and member["role"] != "owner":
            raise ReviewError("owner_required", 403)
        return workspace, member, state

    def establish_reviewer_context(self, db, identity):
        workspace = str(UUID(identity.workspace_id))
        db.execute("SET LOCAL search_path TO public,pg_catalog")
        db.execute("SELECT set_config('space.workspace_id',%s,true)", (workspace,))
        self._active(db, workspace)
        db.execute(
            """INSERT INTO memberships VALUES(%s,%s,'reviewer',true)
            ON CONFLICT(workspace_id,principal_id) DO UPDATE SET active=true
            WHERE memberships.role='reviewer' RETURNING role""",
            (workspace, identity.principal_id),
        )
        if not db.fetchone():
            raise ReviewError("staff_membership_conflict", 409)
        token = workspace + "." + secrets.token_urlsafe(32)
        hashed = self._hash("session", token)
        db.execute(
            "DELETE FROM sessions WHERE principal_id=%s", (identity.principal_id,)
        )
        db.execute(
            "INSERT INTO sessions VALUES(%s,%s,%s,true,%s)",
            (
                workspace,
                hashed,
                identity.principal_id,
                min(identity.expires_at, self.clock() + timedelta(hours=1)),
            ),
        )
        db.execute(
            "INSERT INTO staff_session_links VALUES(%s,%s,%s)",
            (workspace, hashed, identity.session_reference),
        )
        return token

    def invitation_token(self, workspace, invitation):
        # Reproducible only with a server-held key: retries send the same link;
        # neither the raw token nor an email URL is stored in the outbox.
        value = workspace + "." + invitation
        purpose = (
            "invitation-v1"
            if self.settings.mode == "test"
            else "invitation-v1:" + self.settings.generation
        )
        return value + "." + digest(self.settings.signing_key, purpose, value)

    def ingest(self, value):
        """Trusted internal boundary, not a public webhook or client endpoint.

        A future verified intake adapter must construct this contract. Synthetic
        recipient checks are also enforced by SQL in this tranche.
        """
        if self.settings.mode != "test":
            raise ReviewError("manual_admission_required", 403)
        item = Intake.model_validate(value)
        body = item.model_dump_json()
        source = self._source_hash(
            "source", json.dumps([item.source, item.form_id, item.response_id])
        )
        fingerprint = self._source_hash("intake", body)
        workspace = str(uuid4())
        with self.db.transaction(workspace) as db:
            return self.ingest_in_transaction(db, item, workspace, source, fingerprint)

    def ingest_in_transaction(
        self, db, item, workspace=None, source_digest=None, payload_digest=None
    ):
        """Trusted adapter hook: admission and case creation share ONE commit."""
        item = (
            LiveIntake if self.settings.mode == "production" else Intake
        ).model_validate(item)
        workspace = str(UUID(workspace)) if workspace else str(uuid4())
        db.execute("SELECT set_config('space.workspace_id',%s,true)", (workspace,))
        source = source_digest or self._source_hash(
            "source", json.dumps([item.source, item.form_id, item.response_id])
        )
        fingerprint = payload_digest or self._source_hash(
            "intake", item.model_dump_json()
        )
        if self.deletion_journal and self.deletion_journal.suppresses(source):
            raise ReviewError("intake_suppressed", 409)
        principal, invitation = str(uuid4()), str(uuid4())
        now = self.clock()
        db.execute(
            """INSERT INTO receipts VALUES (%s,%s,%s)
            ON CONFLICT (source_digest) DO NOTHING RETURNING workspace_id""",
            (source, fingerprint, workspace),
        )
        if not db.fetchone():
            db.execute("SELECT * FROM receipts WHERE source_digest=%s", (source,))
            existing = db.fetchone()
            if not hmac.compare_digest(existing["payload_digest"], fingerprint):
                raise ReviewError("intake_reference_conflict")
            return {"workspace_id": str(existing["workspace_id"]), "created": False}
        db.execute(
            "INSERT INTO workspaces(workspace_id,created_at,landing_path,last_activity_at) VALUES(%s,%s,%s,%s)",
            (workspace, now, item.landing_path, now),
        )
        db.execute(
            "INSERT INTO memberships VALUES(%s,%s,'owner',true)", (workspace, principal)
        )
        token = self.invitation_token(workspace, invitation)
        db.execute(
            """INSERT INTO invitations
            (workspace_id,invitation_id,principal_id,recipient,token_digest,expires_at)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (
                workspace,
                invitation,
                principal,
                item.email,
                self._hash("invitation", token),
                now + timedelta(minutes=15),
            ),
        )
        db.execute(
            "INSERT INTO outbox(workspace_id,invitation_id,available_at) VALUES(%s,%s,%s)",
            (workspace, invitation, now),
        )
        self._audit(db, workspace, "application_received")
        return {"workspace_id": workspace, "created": True}

    def throttle_exchange(self, peer):
        now = self.clock()
        with self.db.transaction() as db:
            db.execute(
                """INSERT INTO auth_limits VALUES(%s,%s,1)
                ON CONFLICT(bucket_digest) DO UPDATE SET
                attempts=CASE WHEN auth_limits.started_at<=%s THEN 1 ELSE auth_limits.attempts+1 END,
                started_at=CASE WHEN auth_limits.started_at<=%s THEN EXCLUDED.started_at ELSE auth_limits.started_at END
                RETURNING attempts""",
                (
                    self._hash("auth-peer", peer),
                    now,
                    now - timedelta(minutes=1),
                    now - timedelta(minutes=1),
                ),
            )
            allowed = db.fetchone()["attempts"] <= 10
            db.execute(
                "DELETE FROM auth_limits WHERE started_at<%s",
                (now - timedelta(hours=1),),
            )
        if not allowed:
            raise ReviewError("try_again_later", 429)

    def exchange_invitation(self, token):
        workspace = workspace_from_token(token)
        now = self.clock()
        with self.db.transaction(workspace) as db:
            self._active(db, workspace)
            db.execute(
                """SELECT i.* FROM invitations i JOIN memberships m
                USING(workspace_id,principal_id) WHERE i.token_digest=%s
                AND i.consumed_at IS NULL AND i.expires_at>%s AND m.active
                AND m.role='owner' FOR UPDATE OF i""",
                (self._hash("invitation", token), now),
            )
            row = db.fetchone()
            if not row:
                raise ReviewError("invitation_invalid_or_expired", 401)
            db.execute(
                "UPDATE invitations SET consumed_at=%s WHERE principal_id=%s",
                (now, row["principal_id"]),
            )
            # Re-authentication replaces existing sessions for this membership.
            db.execute(
                "DELETE FROM sessions WHERE principal_id=%s", (row["principal_id"],)
            )
            session = workspace + "." + secrets.token_urlsafe(32)
            db.execute(
                "INSERT INTO sessions VALUES(%s,%s,%s,false,%s)",
                (
                    workspace,
                    self._hash("session", session),
                    row["principal_id"],
                    now + timedelta(hours=1),
                ),
            )
            self._audit(db, workspace, "invitation_consumed")
        return session

    def csrf(self, token):
        return self._hash("csrf", token)

    def view(self, token):
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, member, state = self._authorize(db, token)
            db.execute(
                """SELECT document_id,filename,size_bytes,status,question_id FROM documents d
                WHERE %s OR question_id IS NULL OR EXISTS (
                    SELECT 1 FROM review_supplements s,
                    jsonb_array_elements(s.documents) AS item
                    WHERE item->>'document_id'=d.document_id::text)
                ORDER BY document_id""",
                (member["role"] == "owner",),
            )
            documents = [dict(row) for row in db.fetchall()]
            db.execute(
                "SELECT submission_id,revision,snapshot,created_at FROM submissions"
            )
            submission = db.fetchone()
            questions = self._conversation(db)
            return {
                "workspace_id": workspace,
                "role": member["role"],
                "revision": state["revision"],
                "landing_path": state["landing_path"],
                "draft": state["draft"] or None,
                "documents": documents,
                "submission": dict(submission) if submission else None,
                "questions": questions,
                "session_expires_at": member["expires_at"],
                "review_status": (
                    "not_submitted"
                    if not submission
                    else "needs_information"
                    if any(q["reply"] is None for q in questions)
                    else "under_review"
                    if questions
                    else "submitted"
                ),
            }

    def save_draft(self, token, value):
        change = SaveDraft.model_validate(value)
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, _, state = self._authorize(db, token, owner=True)
            self._editable(db, state, change.revision)
            self._documents(db, change.draft.document_ids)
            if state["draft"] == change.draft.model_dump(mode="json"):
                return {"revision": state["revision"]}
            db.execute(
                "UPDATE workspaces SET draft=%s,revision=revision+1 WHERE workspace_id=%s RETURNING revision",
                (Json(change.draft.model_dump(mode="json")), workspace),
            )
            revision = db.fetchone()["revision"]
            self._audit(db, workspace, "draft_saved")
            self._touch(db, workspace)
            return {"revision": revision}

    def _editable(self, db, state, revision):
        db.execute("SELECT 1 FROM submissions")
        if db.fetchone():
            raise ReviewError("submission_locked")
        if state["revision"] != revision:
            raise ReviewError("draft_changed_reload_required")

    def _documents(self, db, identifiers, accepted=False):
        result = []
        for document_id in identifiers:
            db.execute(
                "SELECT document_id,filename,size_bytes,sha256,status,question_id FROM documents WHERE document_id=%s",
                (str(document_id),),
            )
            doc = db.fetchone()
            if not doc:
                raise ReviewError("document_unavailable", 404)
            if accepted and doc["status"] != "accepted_for_review":
                raise ReviewError("documents_not_ready")
            result.append(dict(doc))
        return result

    def submit(self, token, value):
        request = Submit.model_validate(value)
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, _, state = self._authorize(db, token, owner=True)
            db.execute("SELECT * FROM submissions")
            existing = db.fetchone()
            if existing:
                if (
                    str(existing["request_id"]) == str(request.request_id)
                    and existing["revision"] == request.revision
                ):
                    return {
                        "submission_id": str(existing["submission_id"]),
                        "created": False,
                    }
                raise ReviewError("submission_locked")
            self._editable(db, state, request.revision)
            if not state["draft"]:
                raise ReviewError("draft_incomplete")
            draft = Draft.model_validate(state["draft"])
            docs = self._documents(db, draft.document_ids, accepted=True)
            snapshot = {
                "draft": draft.model_dump(mode="json"),
                "documents": docs,
                "missing_evidence": not bool(docs),
                "rights_verified": False,
                "consent_version": "review-scope-v1",
                "future_music_excluded": True,
            }
            submission = str(uuid4())
            db.execute(
                "INSERT INTO submissions VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    workspace,
                    submission,
                    str(request.request_id),
                    request.revision,
                    Json(snapshot),
                    self.clock(),
                ),
            )
            self._audit(db, workspace, "submitted")
            self._touch(db, workspace)
            return {"submission_id": submission, "created": True}

    def quarantine(
        self, token, filename, content, blobs, request_id=None, question_id=None
    ):
        filename = Upload(filename=filename).filename
        if not isinstance(content, bytes) or not 0 < len(content) <= 25 * 1024 * 1024:
            raise ReviewError("invalid_document_size", 413)
        # Only a prefilter; this never substitutes for a real sandboxed parser/AV.
        if (filename.lower().endswith(".pdf") and not content.startswith(b"%PDF-")) or (
            filename.lower().endswith(".xlsx") and not content.startswith(b"PK\x03\x04")
        ):
            raise ReviewError("document_type_mismatch", 422)
        workspace = workspace_from_token(token)
        document, key = str(uuid4()), workspace + "/" + str(uuid4())
        request_id = str(UUID(str(request_id))) if request_id else str(uuid4())
        question_id = str(UUID(str(question_id))) if question_id else None
        checksum = hashlib.sha256(content).hexdigest()
        uploaded = False
        try:
            with self.db.transaction(workspace) as db:
                _, member, state = self._authorize(db, token, owner=True)
                db.execute(
                    "SELECT * FROM documents WHERE upload_request_id=%s", (request_id,)
                )
                prior = db.fetchone()
                if prior:
                    if (
                        prior["filename"] != filename
                        or prior["size_bytes"] != len(content)
                        or not hmac.compare_digest(prior["sha256"], checksum)
                        or str(prior["uploader_id"]) != str(member["principal_id"])
                        or (str(prior["question_id"]) if prior["question_id"] else None)
                        != question_id
                    ):
                        raise ReviewError("upload_request_conflict")
                    return {
                        "document_id": str(prior["document_id"]),
                        "status": prior["status"],
                    }
                if question_id:
                    db.execute(
                        """SELECT 1 FROM review_questions q WHERE question_id=%s
                        AND request_documents AND NOT EXISTS
                        (SELECT 1 FROM review_replies r WHERE r.question_id=q.question_id)""",
                        (question_id,),
                    )
                    if not db.fetchone():
                        raise ReviewError("open_document_request_required")
                else:
                    self._editable(db, state, state["revision"])
                db.execute("SELECT count(*) AS count FROM documents")
                if db.fetchone()["count"] >= 40:
                    raise ReviewError("document_limit_reached")
                # Object stores must implement immutable put-if-absent. No
                # caller-supplied path/URL or presigned public URL is accepted.
                blobs.put_if_absent(key, content)
                uploaded = True
                db.execute(
                    """INSERT INTO documents
                    (workspace_id,document_id,uploader_id,object_key,filename,size_bytes,sha256,upload_request_id,question_id)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        workspace,
                        document,
                        member["principal_id"],
                        key,
                        filename,
                        len(content),
                        checksum,
                        request_id,
                        question_id,
                    ),
                )
                self._audit(db, workspace, "document_quarantined")
                self._touch(db, workspace)
        except CommitOutcomeUnknown:
            # The document may already be committed. Never erase its object on
            # an ambiguous acknowledgement; reconcile by object_key first.
            raise
        except Exception:
            # Best-effort cleanup is not the only control: an unreferenced
            # quarantine object must also expire via the future storage policy.
            if uploaded:
                try:
                    blobs.delete(key)
                except Exception:
                    pass
            raise
        return {"document_id": document, "status": "quarantined"}

    def claim_scan(self, workspace, document):
        now, lease = self.clock(), str(uuid4())
        with self.db.transaction(workspace) as db:
            self._active(db, workspace)
            db.execute(
                """UPDATE documents SET status='quarantined',scan_lease_id=NULL,scan_lease_until=NULL
                WHERE document_id=%s AND status='scanning' AND scan_lease_until<=%s AND scan_attempts>=3""",
                (document, now),
            )
            db.execute(
                """UPDATE documents d SET status='scanning',scan_attempts=scan_attempts+1,scan_lease_id=%s,scan_lease_until=%s
                WHERE document_id=%s AND (status='quarantined' OR (status='scanning' AND scan_lease_until<=%s))
                AND scan_attempts<3
                AND EXISTS(SELECT 1 FROM memberships m WHERE m.principal_id=d.uploader_id AND m.active)
                RETURNING document_id, object_key, sha256, size_bytes, filename""",
                (lease, now + timedelta(minutes=2), document, now),
            )
            doc = db.fetchone()
            return (
                {**dict(doc), "workspace_id": workspace, "lease_id": lease}
                if doc
                else None
            )

    def complete_scan(self, job, *, clean, scanned_sha256):
        with self.db.transaction(job["workspace_id"]) as db:
            self._active(db, job["workspace_id"])
            db.execute(
                """UPDATE documents d SET status=%s,scan_lease_id=NULL,scan_lease_until=NULL
                WHERE document_id=%s AND status='scanning' AND scan_lease_id=%s AND scan_lease_until>%s
                AND sha256=%s AND EXISTS(SELECT 1 FROM memberships m WHERE m.principal_id=d.uploader_id AND m.active)
                RETURNING document_id""",
                (
                    "accepted_for_review" if clean is True else "rejected",
                    job["document_id"],
                    job["lease_id"],
                    self.clock(),
                    scanned_sha256,
                ),
            )
            if not db.fetchone():
                raise ReviewError("scan_result_stale")
            self._audit(db, job["workspace_id"], "document_scanned")

    def download(self, token, document, blobs):
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, member, _ = self._authorize(db, token)
            db.execute(
                "SELECT * FROM documents WHERE document_id=%s AND status='accepted_for_review'",
                (document,),
            )
            doc = db.fetchone()
            if not doc:
                raise ReviewError("document_unavailable", 404)
            if member["role"] == "reviewer" and doc["question_id"]:
                db.execute(
                    """SELECT 1 FROM review_supplements s,
                    jsonb_array_elements(s.documents) AS item
                    WHERE item->>'document_id'=%s""",
                    (str(document),),
                )
                if not db.fetchone():
                    raise ReviewError("document_unavailable", 404)
            content = blobs.get(doc["object_key"])
            if len(content) != doc["size_bytes"] or not hmac.compare_digest(
                hashlib.sha256(content).hexdigest(), doc["sha256"]
            ):
                raise ReviewError("document_integrity_failed")
            self._audit(db, workspace, "document_read")
            return doc["filename"], content

    def request_deletion(self, token):
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, _, _ = self._authorize(
                db, token, owner=True, deletion_retry=True
            )
            self._record_deletion(db, workspace, "owner_request")
            self._stop_workspace(db, workspace)
        # This is an access stop and durable request, NOT a claim of erasure.
        return {"status": "deletion_requested", "erasure_completed": False}

    def logout(self, token):
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, _, _ = self._authorize(db, token)
            db.execute(
                "DELETE FROM sessions WHERE token_digest=%s",
                (self._hash("session", token),),
            )
            self._audit(db, workspace, "session_closed")

    def claim_invitation(self, workspace):
        now, lease = self.clock(), str(uuid4())
        with self.db.transaction(workspace) as db:
            self._active(db, workspace)
            db.execute(
                """UPDATE outbox o SET status='dead',lease_id=NULL,lease_until=NULL
                FROM invitations i WHERE i.invitation_id=o.invitation_id
                AND o.status IN ('queued','leased') AND (i.expires_at<=%s OR i.consumed_at IS NOT NULL
                OR (o.attempts>=5 AND (o.status='queued' OR o.lease_until<=%s))
                OR NOT EXISTS(SELECT 1 FROM memberships m WHERE m.principal_id=i.principal_id AND m.active))""",
                (now, now),
            )
            db.execute(
                """SELECT o.invitation_id, i.recipient FROM outbox o JOIN invitations i USING(workspace_id,invitation_id)
                WHERE (o.status='queued' AND o.available_at<=%s)
                OR (o.status='leased' AND o.lease_until<=%s)
                ORDER BY o.available_at LIMIT 1 FOR UPDATE OF o SKIP LOCKED""",
                (now, now),
            )
            row = db.fetchone()
            if not row:
                return None
            invitation = str(row["invitation_id"])
            db.execute(
                "UPDATE outbox SET status='leased',attempts=attempts+1,lease_id=%s,lease_until=%s WHERE invitation_id=%s",
                (lease, now + timedelta(seconds=60), invitation),
            )
            token = self.invitation_token(workspace, invitation)
            return {
                "workspace_id": workspace,
                "invitation_id": invitation,
                "lease_id": lease,
                "recipient": row["recipient"],
                "url": self.settings.origin + "/workspace/#invitation=" + token,
                "idempotency_key": "review-invitation-" + invitation,
            }

    def finish_invitation(self, job, *, accepted, provider_reference=None):
        if accepted and (
            not isinstance(provider_reference, str)
            or not 1 <= len(provider_reference) <= 200
        ):
            raise ReviewError("provider_reference_required")
        with self.db.transaction(job["workspace_id"]) as db:
            self._active(db, job["workspace_id"])
            db.execute(
                """UPDATE outbox SET status=%s,provider_reference=%s,
                available_at=%s,lease_id=NULL,lease_until=NULL
                WHERE invitation_id=%s AND status='leased' AND lease_id=%s AND lease_until>%s RETURNING attempts""",
                (
                    "accepted" if accepted else "queued",
                    provider_reference if accepted else None,
                    self.clock() + timedelta(seconds=60),
                    job["invitation_id"],
                    job["lease_id"],
                    self.clock(),
                ),
            )
            if not db.fetchone():
                raise ReviewError("invitation_lease_stale")
