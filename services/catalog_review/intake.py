"""Signed intake, manual Formspree receipts and five-place pilot admission.

No HTTP routes, provider fetches, secrets loading or automatic admissions.
The application must inject:
* a Database-compatible transaction() yielding a psycopg RealDictCursor;
* an AEAD codec seal(bytes, aad=bytes)/open(bytes, aad=bytes), with versioned keys;
* authorize_staff(cursor, opaque_principal, action) -> active operator UUID;
* source_suppressed(source_digest) -> bool, backed by the external deletion journal;
* ingest_in_transaction(cursor, item, workspace=..., source_digest=...,
  payload_digest=...) -> {workspace_id, created}, using ONLY that cursor and
  NEVER committing, opening another transaction, or performing external I/O.

Do not pass ReviewService.ingest. The transaction owner is this coordinator.
The source key is independent of webhook/session keys and is stable across their
rotation. Changing it requires an explicit source-index migration, not restart.
Typeform: https://www.typeform.com/developers/webhooks/secure-your-webhooks/
Formspree stays manual until account capability and stable provider IDs are proven.
"""

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from .security import ReviewError

MAX_BODY = 128 * 1024
REFERENCE = re.compile(r"[A-Za-z0-9_-]{1,200}")
PATHS = {
    "/",
    "/apply/",
    "/sell/",
    "/calculator/",
    "/guides/music-catalog-valuation-2026/",
}
KINDS = {"owner", "representative", "partnership", "unknown"}
PILOT_LOCK = (1936744803, 5)


def normalize_email(value):
    """Conservative ASCII mailbox policy; preserve local-part case and plus tags."""
    if not isinstance(value, str) or len(value) > 254:
        raise ReviewError("invalid_email", 422)
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+", value):
        raise ReviewError("invalid_email", 422)
    local, domain = value.rsplit("@", 1)
    labels = domain.split(".")
    if (
        len(local) > 64
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or len(labels) < 2
        or any(
            not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part)
            for part in labels
        )
    ):
        raise ReviewError("invalid_email", 422)
    return local + "@" + domain.lower()


def _uuid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ReviewError("invalid_reference", 422) from None


def _timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise ReviewError("invalid_submission_time", 422) from None


def _json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


@dataclass(frozen=True)
class TypeformMapping:
    form_id: str = "xzx5SBJb"
    email_field_id: str = "oY3yxQa3CAD3"
    inquiry_field_id: str = ""
    # Actual webhook choice IDs, not labels or editor UUID refs.
    inquiry_choices: dict = field(default_factory=dict)
    version: int = 1

    def __post_init__(self):
        if (
            not REFERENCE.fullmatch(self.form_id)
            or len(self.form_id) > 120
            or not REFERENCE.fullmatch(self.email_field_id)
            or (
                self.inquiry_field_id and not REFERENCE.fullmatch(self.inquiry_field_id)
            )
            or type(self.version) is not int
            or self.version < 1
            or any(
                not REFERENCE.fullmatch(k) or v not in KINDS
                for k, v in self.inquiry_choices.items()
            )
        ):
            raise ValueError("Invalid Typeform mapping")
        object.__setattr__(self, "inquiry_choices", dict(self.inquiry_choices))


class IntakeService:
    def __init__(
        self,
        db,
        *,
        source_key,
        webhook_secret,
        cipher,
        authorize_staff,
        ingest_in_transaction,
        source_suppressed,
        mapping=None,
        clock=None,
    ):
        if (
            not isinstance(source_key, bytes)
            or len(source_key) < 32
            or not isinstance(webhook_secret, bytes)
            or len(webhook_secret) < 32
            or hmac.compare_digest(source_key, webhook_secret)
        ):
            raise ValueError(
                "Independent source and webhook keys of at least 32 bytes required"
            )
        if not all(
            callable(method)
            for method in (
                cipher.seal,
                cipher.open,
                authorize_staff,
                ingest_in_transaction,
                source_suppressed,
            )
        ):
            raise ValueError("Trusted intake dependencies required")
        self.db = db
        self._source_key = source_key
        self._webhook_secret = webhook_secret
        self._cipher = cipher
        self._authorize_staff = authorize_staff
        self._ingest = ingest_in_transaction
        self._source_suppressed = source_suppressed
        self.mapping = mapping or TypeformMapping()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        with self.db.transaction() as cur:
            self._check_source_key(cur)

    def _digest(self, purpose, value):
        return hmac.new(
            self._source_key, purpose.encode() + b":" + _json(value), hashlib.sha256
        ).hexdigest()

    def _check_source_key(self, cur):
        check = self._digest("key-binding-v1", "catalog-review-intake")
        cur.execute(
            "INSERT INTO intake_key_binding VALUES(true,%s) ON CONFLICT DO NOTHING",
            (check,),
        )
        cur.execute("SELECT key_check FROM intake_key_binding WHERE singleton")
        if not hmac.compare_digest(cur.fetchone()["key_check"], check):
            raise ReviewError("source_key_migration_required", 503)

    def _actor(self, cur, principal, action):
        # The injected authenticator must recheck live staff session, UV and
        # operator permission; a role/MFA boolean supplied by a browser is not one.
        actor = self._authorize_staff(cur, principal, action)
        if actor is None:
            raise ReviewError("operator_required", 403)
        return _uuid(actor)

    def receive_typeform(self, raw_body, signature):
        if not isinstance(raw_body, bytes) or not 0 < len(raw_body) <= MAX_BODY:
            raise ReviewError("intake_body_limit", 413)
        expected = (
            "sha256="
            + base64.b64encode(
                hmac.new(self._webhook_secret, raw_body, hashlib.sha256).digest()
            ).decode()
        )
        if (
            not isinstance(signature, str)
            or not re.fullmatch(r"sha256=[A-Za-z0-9+/]{43}=", signature)
            or not hmac.compare_digest(signature, expected)
        ):
            raise ReviewError("invalid_intake_signature", 401)
        try:
            payload = json.loads(
                raw_body,
                object_pairs_hook=_strict_object,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
            )
            if not isinstance(payload, dict):
                raise ValueError()
            form = payload.get("form_response")
            if payload.get("event_type") != "form_response":
                return {"status": "ignored"}
            if (
                not isinstance(form, dict)
                or form.get("form_id") != self.mapping.form_id
            ):
                raise ValueError()
            if form.get("response_type", "completed") != "completed":
                return {"status": "ignored"}
            reference = form.get("token")
            if not isinstance(reference, str) or not REFERENCE.fullmatch(reference):
                raise ValueError()
            submitted = _timestamp(form.get("submitted_at"))
            now = self.clock()
            if not now - timedelta(days=7) <= submitted <= now + timedelta(minutes=5):
                raise ReviewError("submission_outside_window", 422)
            answers = form.get("answers")
            if (
                not isinstance(answers, list)
                or len(answers) > 100
                or any(not isinstance(a, dict) for a in answers)
            ):
                raise ValueError()
            emails = [
                a
                for a in answers
                if isinstance(a.get("field"), dict)
                and a["field"].get("id") == self.mapping.email_field_id
            ]
            if len(emails) != 1 or emails[0].get("type") != "email":
                raise ValueError()
            email = normalize_email(emails[0].get("email"))
            kind = "unknown"
            if self.mapping.inquiry_field_id:
                choices = [
                    a
                    for a in answers
                    if isinstance(a.get("field"), dict)
                    and a["field"].get("id") == self.mapping.inquiry_field_id
                ]
                if (
                    len(choices) != 1
                    or choices[0].get("type") != "choice"
                    or not isinstance(choices[0].get("choice"), dict)
                ):
                    raise ValueError()
                kind = self.mapping.inquiry_choices.get(choices[0]["choice"].get("id"))
                if kind is None:
                    raise ReviewError("intake_mapping_changed", 422)
            hidden = form.get("hidden", {})
            landing = (
                hidden.get("landing_path", "/apply/")
                if isinstance(hidden, dict)
                else "/apply/"
            )
            if not isinstance(landing, str) or landing not in PATHS:
                landing = "/apply/"
        except ReviewError:
            raise
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            raise ReviewError("invalid_intake_payload", 422) from None
        item = self._item(
            "typeform",
            self.mapping.form_id,
            reference,
            email,
            landing,
            submitted,
            kind,
            self.mapping.version,
        )
        with self.db.transaction() as cur:
            return self._record(cur, item)

    @staticmethod
    def _item(source, form, reference, email, landing, submitted, kind, version):
        return {
            "source": source,
            "form_id": form,
            "response_id": reference,
            "email": email,
            "landing_path": landing,
            "submitted_at": submitted.isoformat(),
            "inquiry_kind": kind,
            "mapping_version": version,
        }

    def record_formspree_receipt(
        self, principal, *, receipt_id, email, submitted_at, landing_path="/apply/"
    ):
        """Operator-attested receipt, NOT a Formspree webhook or provider-ID claim.

        receipt_id is an internal UUID retained by the operator across retries.
        Duplicate checking against the original Formspree record remains manual.
        """
        reference, email = _uuid(receipt_id), normalize_email(email)
        submitted = _timestamp(submitted_at)
        if landing_path not in PATHS or submitted > self.clock() + timedelta(minutes=5):
            raise ReviewError("invalid_manual_receipt", 422)
        item = self._item(
            "short_form",
            "mpwdnokz",
            reference,
            email,
            landing_path,
            submitted,
            "unknown",
            1,
        )
        with self.db.transaction() as cur:
            actor = self._actor(cur, principal, "intake.record_manual")
            return self._record(cur, item, actor)

    def _record(self, cur, item, actor=None):
        # Serialize suppression-check + insert with pending-receipt erasure,
        # including an in-flight replay that began before the journal write.
        cur.execute("SELECT pg_advisory_xact_lock(%s,%s)", PILOT_LOCK)
        self._check_source_key(cur)
        source = self._digest(
            "source-v1", [item[k] for k in ("source", "form_id", "response_id")]
        )
        if self._source_suppressed(source):
            return {"status": "suppressed"}
        fingerprint = self._digest("payload-v1", item)
        intake_id = str(uuid4())
        encrypted = self._cipher.seal(
            _json(item), aad=("intake-v1:" + intake_id).encode()
        )
        if not isinstance(encrypted, bytes) or not 0 < len(encrypted) <= 16384:
            raise ReviewError("intake_encryption_failed", 503)
        cur.execute(
            """INSERT INTO intake_inbox
            (intake_id,source,form_id,source_digest,payload_digest,mapping_version,inquiry_kind,
             payload_cipher,submitted_at,received_at,recorded_by)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(source_digest) DO NOTHING RETURNING intake_id""",
            (
                intake_id,
                item["source"],
                item["form_id"],
                source,
                fingerprint,
                item["mapping_version"],
                item["inquiry_kind"],
                encrypted,
                _timestamp(item["submitted_at"]),
                self.clock(),
                actor,
            ),
        )
        created = cur.fetchone() is not None
        cur.execute(
            "SELECT intake_id,payload_digest FROM intake_inbox WHERE source_digest=%s",
            (source,),
        )
        row = cur.fetchone()
        if not hmac.compare_digest(row["payload_digest"], fingerprint):
            raise ReviewError("intake_reference_conflict", 409)
        return {
            "intake_id": str(row["intake_id"]),
            "created": created,
            "status": "pending_review",
        }

    def list_receipts(self, principal):
        with self.db.transaction() as cur:
            self._actor(cur, principal, "intake.read")
            cur.execute("""SELECT i.intake_id,i.source_digest,i.source,i.form_id,i.inquiry_kind,i.submitted_at,
                i.received_at,a.workspace_id FROM intake_inbox i LEFT JOIN intake_admissions a USING(intake_id)
                ORDER BY i.received_at DESC,i.intake_id LIMIT 50""")
            result = []
            for row in cur.fetchall():
                if not self._source_suppressed(row["source_digest"]):
                    result.append(
                        {k: v for k, v in row.items() if k != "source_digest"}
                    )
            return result

    def _open(self, row):
        if self._source_suppressed(row["source_digest"]):
            raise ReviewError("intake_suppressed", 409)
        try:
            raw = self._cipher.open(
                bytes(row["payload_cipher"]),
                aad=("intake-v1:" + str(row["intake_id"])).encode(),
            )
            item = json.loads(raw, object_pairs_hook=_strict_object)
            if not hmac.compare_digest(
                self._digest("payload-v1", item), row["payload_digest"]
            ):
                raise ValueError()
            return item
        except Exception:
            raise ReviewError("intake_integrity_failed", 503) from None

    def read_receipt(self, principal, intake_id):
        intake_id = _uuid(intake_id)
        with self.db.transaction() as cur:
            self._actor(cur, principal, "intake.read")
            self._check_source_key(cur)
            cur.execute("SELECT * FROM intake_inbox WHERE intake_id=%s", (intake_id,))
            row = cur.fetchone()
            if not row:
                raise ReviewError("intake_unavailable", 404)
            return {"intake_id": intake_id, **self._open(row)}

    def export_in_transaction(self, cur, workspace):
        """Trusted core export hook, after owner authorization under case lock.

        Only this case's admitted receipt is read. Operator IDs, suppression keys,
        encrypted payloads and other pending applications are never exported.
        """
        workspace = _uuid(workspace)
        self._check_source_key(cur)
        cur.execute(
            """SELECT i.* FROM intake_inbox i JOIN intake_admissions a
            USING(intake_id) WHERE a.workspace_id=%s AND a.erased_at IS NULL""",
            (workspace,),
        )
        row = cur.fetchone()
        if not row:
            raise ReviewError("intake_export_unavailable", 503)
        result = {"receipt": self._open(row), "received_at": row["received_at"]}
        cur.execute(
            """SELECT status,reason,created_at,updated_at FROM portal_mail_attempts
            WHERE workspace_id=%s ORDER BY created_at""",
            (workspace,),
        )
        result["portal_mail"] = [dict(item) for item in cur.fetchall()]
        return result

    def approve(self, principal, *, intake_id, request_id, owner_authority_confirmed):
        intake_id, request_id = _uuid(intake_id), _uuid(request_id)
        if owner_authority_confirmed is not True:
            raise ReviewError("owner_authority_confirmation_required", 422)
        with self.db.transaction() as cur:
            actor = self._actor(cur, principal, "intake.approve")
            self._check_source_key(cur)
            cur.execute("SELECT pg_advisory_xact_lock(%s,%s)", PILOT_LOCK)
            cur.execute(
                "SELECT * FROM intake_admissions WHERE request_id=%s OR intake_id=%s",
                (request_id, intake_id),
            )
            prior = cur.fetchone()
            if prior:
                if (
                    str(prior["request_id"]) != request_id
                    or str(prior["intake_id"]) != intake_id
                    or str(prior["approved_by"]) != actor
                ):
                    raise ReviewError("approval_request_conflict", 409)
                cur.execute(
                    "SELECT source_digest FROM intake_inbox WHERE intake_id=%s",
                    (intake_id,),
                )
                if self._source_suppressed(cur.fetchone()["source_digest"]):
                    raise ReviewError("intake_suppressed", 409)
                return {
                    "workspace_id": str(prior["workspace_id"]),
                    "created": False,
                    "slot": prior["slot"],
                }
            cur.execute("SELECT * FROM intake_inbox WHERE intake_id=%s", (intake_id,))
            row = cur.fetchone()
            if not row:
                raise ReviewError("intake_unavailable", 404)
            if row["inquiry_kind"] == "partnership":
                raise ReviewError("partnership_not_pilot_eligible", 409)
            cur.execute(
                "SELECT n FROM generate_series(1,5) n WHERE n NOT IN (SELECT slot FROM intake_admissions) ORDER BY n LIMIT 1"
            )
            slot = cur.fetchone()
            if not slot:
                raise ReviewError("pilot_admission_limit", 409)
            item = self._open(row)
            workspace = str(uuid4())
            cur.execute("SELECT set_config('space.workspace_id',%s,true)", (workspace,))
            core_item = {
                key: item[key]
                for key in ("source", "form_id", "response_id", "email", "landing_path")
            }
            result = self._ingest(
                cur,
                core_item,
                workspace=workspace,
                source_digest=row["source_digest"],
                payload_digest=row["payload_digest"],
            )
            if (
                not isinstance(result, dict)
                or result.get("created") is not True
                or str(result.get("workspace_id")) != workspace
            ):
                raise ReviewError("admission_coordinator_mismatch", 503)
            cur.execute("SELECT 1 FROM workspaces WHERE workspace_id=%s", (workspace,))
            if not cur.fetchone():
                raise ReviewError("admission_coordinator_mismatch", 503)
            cur.execute(
                """INSERT INTO intake_admissions
                (slot,intake_id,workspace_id,request_id,approved_by,approved_at) VALUES(%s,%s,%s,%s,%s,%s)""",
                (slot["n"], intake_id, workspace, request_id, actor, self.clock()),
            )
            return {"workspace_id": workspace, "created": True, "slot": slot["n"]}


class IntakeErasureParticipant:
    """Call before core erasure, on the SAME worker-role cursor/transaction.

    First durably record source suppression in the external deletion journal.
    This participant never deletes that journal or frees a lifetime pilot slot.
    No runtime DELETE/UPDATE grants are added. The optional database must use
    the separate worker role; purge_pending_receipts processes at most 50 rows
    per call. Its journal target is the intake UUID, not an admitted workspace.
    """

    def __init__(self, *, source_suppressed, database=None, clock=None):
        if not callable(source_suppressed):
            raise ValueError("External source suppression required")
        self._source_suppressed = source_suppressed
        self.db = database
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def purge_pending_receipts(self, older_than, journal):
        now = self.clock()
        if (
            not isinstance(older_than, datetime)
            or older_than.tzinfo is None
            or older_than > now - timedelta(days=90)
        ):
            raise ReviewError("intake_retention_cutoff_invalid", 422)
        if self.db is None:
            raise ReviewError("erasure_database_required", 503)
        with self.db.transaction() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s,%s)", PILOT_LOCK)
            cur.execute(
                """SELECT i.intake_id,i.source_digest FROM intake_inbox i
                WHERE i.received_at < %s AND i.submitted_at < %s
                AND NOT EXISTS (SELECT 1 FROM intake_admissions a WHERE a.intake_id=i.intake_id)
                ORDER BY i.received_at,i.intake_id LIMIT 50 FOR UPDATE OF i""",
                (older_than, older_than),
            )
            rows = cur.fetchall()
            for row in rows:
                journal.record(
                    str(row["intake_id"]),
                    row["source_digest"],
                    requested_at=now,
                    reason="inactivity",
                )
                if not self._source_suppressed(row["source_digest"]):
                    raise ReviewError("source_suppression_required", 409)
                cur.execute(
                    "DELETE FROM intake_inbox WHERE intake_id=%s", (row["intake_id"],)
                )
        return {"purged": len(rows)}

    def erase_in_transaction(self, cur, workspace):
        workspace = _uuid(workspace)
        cur.execute("SELECT set_config('space.workspace_id',%s,true)", (workspace,))
        cur.execute(
            """SELECT a.intake_id,i.source_digest FROM intake_admissions a
            JOIN intake_inbox i USING(intake_id) WHERE a.workspace_id=%s FOR UPDATE OF a""",
            (workspace,),
        )
        row = cur.fetchone()
        if row and not self._source_suppressed(row["source_digest"]):
            raise ReviewError("source_suppression_required", 409)
        cur.execute(
            "DELETE FROM portal_mail_attempts WHERE workspace_id=%s", (workspace,)
        )
        if row:
            cur.execute(
                """UPDATE intake_admissions SET intake_id=NULL,workspace_id=NULL,
                request_id=NULL,approved_by=NULL,erased_at=CURRENT_TIMESTAMP WHERE workspace_id=%s""",
                (workspace,),
            )
            cur.execute(
                "DELETE FROM intake_inbox WHERE intake_id=%s", (row["intake_id"],)
            )
