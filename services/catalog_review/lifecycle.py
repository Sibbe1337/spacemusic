"""Fail-closed erasure journal and activity-version fenced retention.

Journal storage is deliberately outside the restorable application database.
Two independently credentialed EU stores must acknowledge a deletion before the
API can acknowledge it. Either copy blocks access; an unavailable copy blocks
operations rather than being interpreted as an empty journal.
"""

import hashlib
import json
import re
from contextlib import closing
from datetime import datetime, timedelta
from uuid import UUID

from .security import ReviewError


class JournalUnavailable(RuntimeError):
    pass


class S3JournalReplica:
    """Minimal append-only journal transport; no delete or overwrite method.

    Use bucket-scoped writer credentials with deletion denied and no lifecycle
    expiry. Endpoint/region/IAM verification belongs to the deployment gate.
    """

    def __init__(self, client, bucket, endpoint):
        if not (
            re.fullmatch(
                r"https://[a-f0-9]{32}\.eu\.r2\.cloudflarestorage\.com", endpoint
            )
            or endpoint == "https://s3.fr-par.scw.cloud"
        ):
            raise ValueError("Explicit EU journal endpoint required")
        if client.meta.endpoint_url != endpoint:
            raise ValueError("Journal endpoint mismatch")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
            raise ValueError("Invalid journal bucket")
        verify = getattr(
            getattr(client._endpoint, "http_session", None), "_verify", None
        )
        if verify is not True:
            raise ValueError("Journal TLS verification required")
        config = client.meta.config
        if any(
            type(getattr(config, name, None)) not in (int, float)
            or not 0 < getattr(config, name) <= 10
            for name in ("read_timeout", "connect_timeout")
        ):
            raise ValueError("Bounded journal transport required")
        self.client, self.bucket = client, bucket
        self.identity = (endpoint, bucket)

    def read(self, key):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as error:
            status = (
                getattr(error, "response", {})
                .get("ResponseMetadata", {})
                .get("HTTPStatusCode")
            )
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if status == 404 and code in ("NoSuchKey", "NotFound"):
                return None
            raise JournalUnavailable("Journal read unconfirmed") from None
        try:
            with closing(response["Body"]) as body:
                raw = body.read(4097)
            if (
                response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 200
                or len(raw) > 4096
                or response["ContentLength"] != len(raw)
            ):
                raise ValueError()
            return raw
        except Exception:
            raise JournalUnavailable("Invalid journal record") from None

    def append(self, key, content):
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType="application/json",
                IfNoneMatch="*",
            )
        except Exception:
            # Lost acceptance or precondition failure is reconciled by exact read.
            pass
        if self.read(key) != content:
            raise JournalUnavailable("Journal write not confirmed")


class ReplicatedDeletionJournal:
    def __init__(self, primary, replica):
        if primary.identity == replica.identity:
            raise ValueError("Independent deletion journal stores required")
        self.stores = (primary, replica)

    @staticmethod
    def _key(kind, value):
        if kind == "workspace":
            value = str(UUID(str(value)))
        elif kind == "source" and not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("Expected stable source digest")
        return "deletions/v1/" + kind + "/" + value

    def _read(self, key):
        records = [store.read(key) for store in self.stores]
        for record in records:
            if record is not None:
                try:
                    decoded = json.loads(record)
                    if decoded.get("schema") != 1 or decoded.get("key") != key:
                        raise ValueError()
                    UUID(decoded["workspace_id"])
                    if not re.fullmatch(r"[0-9a-f]{64}", decoded["source_digest"]):
                        raise ValueError()
                    if key not in (
                        self._key("workspace", decoded["workspace_id"]),
                        self._key("source", decoded["source_digest"]),
                    ) or decoded["reason"] not in ("owner_request", "inactivity"):
                        raise ValueError()
                    if datetime.fromisoformat(decoded["requested_at"]).tzinfo is None:
                        raise ValueError()
                except (ValueError, AttributeError, TypeError, KeyError):
                    raise JournalUnavailable("Invalid deletion journal") from None
        if all(records) and records[0] != records[1]:
            raise JournalUnavailable("Journal replicas disagree")
        return next((record for record in records if record is not None), None)

    def contains(self, workspace):
        return self._read(self._key("workspace", workspace)) is not None

    def suppresses(self, source):
        return self._read(self._key("source", source)) is not None

    def record(self, workspace, source, *, requested_at, reason):
        workspace = str(UUID(str(workspace)))
        if reason not in ("owner_request", "inactivity"):
            raise ValueError("Invalid deletion reason")
        existing = [
            self._read(self._key(kind, value))
            for kind, value in (("source", source), ("workspace", workspace))
        ]
        base = None
        for raw in existing:
            if raw is not None:
                decoded = json.loads(raw)
                decoded.pop("key")
                if (
                    decoded["workspace_id"] != workspace
                    or decoded["source_digest"] != source
                ):
                    raise JournalUnavailable("Deletion identity mismatch")
                if base is not None and decoded != base:
                    raise JournalUnavailable("Deletion records disagree")
                base = decoded
        base = base or {
            "schema": 1,
            "workspace_id": workspace,
            "source_digest": source,
            "requested_at": requested_at.isoformat(),
            "reason": reason,
        }
        # Source suppression goes first: even a restore predating this case must
        # not recreate it from a delayed webhook. Access checks both identities.
        for kind, value in (("source", source), ("workspace", workspace)):
            key = self._key(kind, value)
            content = json.dumps(
                {**base, "key": key}, sort_keys=True, separators=(",", ":")
            ).encode()
            for store in self.stores:
                store.append(key, content)
        return hashlib.sha256(content).hexdigest()

    def reconcile(self, workspace, source=None):
        raw = self._read(self._key("workspace", workspace))
        if raw is None and source is not None:
            raw = self._read(self._key("source", source))
        if raw is None:
            return False
        record = json.loads(raw)
        if record["workspace_id"] != str(workspace) or (
            source is not None and source != record["source_digest"]
        ):
            raise JournalUnavailable("Deletion reconciliation identity mismatch")
        self.record(
            workspace,
            record["source_digest"],
            requested_at=datetime.fromisoformat(record["requested_at"]),
            reason=record["reason"],
        )
        return True


class RetentionLifecycle:
    def queue_retention_notice(self, workspace, activity_version):
        with self.db.transaction(workspace) as db:
            state = self._active(db, workspace)
            deadline = state["last_activity_at"] + timedelta(days=90)
            if (
                state["activity_version"] != activity_version
                or not deadline - timedelta(days=14) <= self.clock() < deadline
            ):
                return {"queued": False}
            db.execute(
                """INSERT INTO retention_notices
                (workspace_id,activity_version,deadline,created_at) VALUES(%s,%s,%s,%s)
                ON CONFLICT DO NOTHING RETURNING workspace_id""",
                (workspace, activity_version, deadline, self.clock()),
            )
            created = bool(db.fetchone())
            return {"queued": created, "delivered": False}

    def continue_interest(self, token, request_id):
        from .security import workspace_from_token

        request_id = str(UUID(str(request_id)))
        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, _, _ = self._authorize(db, token, owner=True)
            db.execute(
                "INSERT INTO interest_events VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING request_id",
                (workspace, request_id),
            )
            created = bool(db.fetchone())
            if created:
                self._touch(db, workspace)
            return {"recorded": True, "created": created}

    def retention_state(self, workspace):
        with self.db.transaction(workspace) as db:
            state = self._active(db, workspace)
            deadline = state["last_activity_at"] + timedelta(days=90)
            return {
                "workspace_id": workspace,
                "activity_version": state["activity_version"],
                "deadline": deadline,
                "notice_due": self.clock() >= deadline - timedelta(days=14),
                "deletion_due": self.clock() >= deadline,
            }

    def expire_inactive(self, workspace, activity_version):
        if self.deletion_journal is None:
            raise ReviewError("deletion_journal_required", 503)
        with self.db.transaction(workspace) as db:
            state = self._active(db, workspace)
            if state["activity_version"] != activity_version or self.clock() < state[
                "last_activity_at"
            ] + timedelta(days=90):
                return {"expired": False}
            self._record_deletion(db, workspace, "inactivity")
            self._stop_workspace(db, workspace)
            return {"expired": True, "erasure_completed": False}

    def _record_deletion(self, db, workspace, reason):
        if self.deletion_journal is None:
            if self.settings.mode != "test":
                raise ReviewError("deletion_journal_required", 503)
            return
        db.execute(
            "SELECT source_digest FROM receipts WHERE workspace_id=%s", (workspace,)
        )
        source = db.fetchone()
        if not source:
            raise ReviewError("deletion_source_unavailable", 503)
        self.deletion_journal.record(
            workspace, source["source_digest"], requested_at=self.clock(), reason=reason
        )

    def _stop_workspace(self, db, workspace):
        db.execute(
            "UPDATE workspaces SET status='deletion_requested' WHERE workspace_id=%s",
            (workspace,),
        )
        db.execute("DELETE FROM sessions")
        db.execute("UPDATE memberships SET active=false")
        db.execute(
            "UPDATE invitations SET consumed_at=COALESCE(consumed_at,%s)",
            (self.clock(),),
        )
        db.execute(
            "UPDATE outbox SET status='dead',lease_id=NULL,lease_until=NULL WHERE status IN ('queued','leased','uncertain')"
        )
        db.execute("UPDATE documents SET scan_lease_id=NULL,scan_lease_until=NULL")
        self._audit(db, workspace, "deletion_requested")

    def export_case(self, token):
        from .security import workspace_from_token

        with self.db.transaction(workspace_from_token(token)) as db:
            workspace, _, _ = self._authorize(db, token, owner=True)
            result = {
                "scope": "SPACE review portal only; source forms and mail are separate",
                "workspace_id": workspace,
            }
            # No session digests, signing material, private object keys or other
            # parties' authentication identifiers are included in the export.
            for name, query in (
                (
                    "workspace",
                    "SELECT revision,draft,created_at,last_activity_at FROM workspaces",
                ),
                (
                    "submission",
                    "SELECT submission_id,revision,snapshot,created_at FROM submissions",
                ),
                (
                    "documents",
                    "SELECT document_id,filename,size_bytes,status,question_id FROM documents",
                ),
                (
                    "supplements",
                    "SELECT supplement_id,version,documents,created_at FROM review_supplements",
                ),
                ("contact", "SELECT DISTINCT recipient FROM invitations"),
                ("dealflow_reviews", "SELECT revision,source_digest,body,created_at FROM dealflow_reviews ORDER BY revision"),
                ("dealflow_packages", "SELECT package_id,revision,payload,digest,created_at,expires_at FROM dealflow_packages ORDER BY created_at"),
                ("dealflow_decisions", "SELECT package_id,decision,digest,created_at FROM dealflow_decisions ORDER BY sequence"),
                ("activity", "SELECT action,created_at FROM audit ORDER BY created_at"),
                (
                    "retention_notices",
                    "SELECT deadline,status,reason,created_at,updated_at FROM retention_notices ORDER BY created_at",
                ),
            ):
                db.execute(query)
                result[name] = [dict(row) for row in db.fetchall()]
            result["questions"] = self._conversation(db)
            if callable(self.intake_exporter):
                result["intake"] = self.intake_exporter(db, workspace)
            elif self.settings.mode != "test":
                raise ReviewError("intake_export_unavailable", 503)
            return result
