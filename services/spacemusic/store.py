from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Optional
from uuid import UUID, uuid4

from libs.catalog.models import (
    ApplicationStatus,
    CatalogPassport,
    CatalogPassportDraft,
    DocumentCreate,
    DocumentRecord,
    DocumentStatus,
    RoyaltyReport,
    RoyaltyReportCreate,
    SupportRequestCreate,
    PayoutView,
    SellerApplication,
    SellerApplicationCreate,
    ValuationResult,
    OfferScenario,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_secret(value: str) -> str:
    secret = os.getenv("SPACEMUSIC_SELLER_TOKEN_SECRET", "local-development-only")
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


class SellerStore:
    """Small transactional store for the seller vertical slice.

    SQLite is used for local development and tests. Production should point this
    adapter at an encrypted managed database or replace it behind this interface.
    """

    def __init__(self, database_path: Optional[str] = None, storage_dir: Optional[str] = None) -> None:
        self.database_path = database_path or os.getenv("SPACEMUSIC_DB_PATH", ":memory:")
        self.storage_dir = Path(storage_dir or os.getenv("SPACEMUSIC_DOCUMENT_DIR", "/tmp/spacemusic-documents"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        if self.database_path != ":memory:":
            Path(self.database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _initialize(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL,
                    contact_email TEXT NOT NULL,
                    seller_name TEXT,
                    status TEXT NOT NULL,
                    passport_json TEXT NOT NULL,
                    valuation_json TEXT,
                    offers_json TEXT NOT NULL,
                    accepted_offer_id TEXT,
                    consent_version TEXT NOT NULL,
                    consent_marketing INTEGER NOT NULL DEFAULT 0,
                    referral_id TEXT,
                    consent_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_applications_status ON applications(status);
                CREATE TABLE IF NOT EXISTS passport_versions (
                    id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL REFERENCES applications(id),
                    version INTEGER NOT NULL,
                    passport_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(application_id, version)
                );
                CREATE INDEX IF NOT EXISTS ix_passport_versions_application_id
                    ON passport_versions(application_id, version);
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL REFERENCES applications(id),
                    document_type TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    storage_key TEXT,
                    upload_token_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    uploaded_at TEXT,
                    verified_at TEXT
                );
                CREATE INDEX IF NOT EXISTS ix_documents_application_id ON documents(application_id);
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL REFERENCES applications(id),
                    actor_role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_audit_application_id_created_at
                    ON audit_events(application_id, created_at);
                CREATE TABLE IF NOT EXISTS payout_intents (
                    id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL REFERENCES applications(id),
                    offer_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    recipient_token_hash TEXT,
                    amount_cents INTEGER NOT NULL,
                    currency_code TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider_reference TEXT,
                    failure_reason TEXT,
                    receipt_sha256 TEXT,
                    receipt_version TEXT,
                    receipt_storage_key TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ledger_entries (
                    id TEXT PRIMARY KEY,
                    payout_intent_id TEXT NOT NULL UNIQUE REFERENCES payout_intents(id),
                    application_id TEXT NOT NULL REFERENCES applications(id),
                    debit_account TEXT NOT NULL,
                    credit_account TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    currency_code TEXT NOT NULL,
                    reference_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS royalty_reports (
                    id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL REFERENCES applications(id),
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    currency_code TEXT NOT NULL,
                    source TEXT NOT NULL,
                    notes TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_royalty_reports_application_id
                    ON royalty_reports(application_id, period_start);
                CREATE TABLE IF NOT EXISTS support_requests (
                    id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL REFERENCES applications(id),
                    subject TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column("applications", "consent_marketing", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("applications", "referral_id", "TEXT")
            self._ensure_column("payout_intents", "receipt_sha256", "TEXT")
            self._ensure_column("payout_intents", "receipt_version", "TEXT")
            self._ensure_column("payout_intents", "receipt_storage_key", "TEXT")
            self._ensure_column("payout_intents", "recipient_token_hash", "TEXT")

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self._connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _audit(self, application_id: UUID, action: str, details: dict[str, Any], actor_role: str) -> None:
        self._connection.execute(
            "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid4()), str(application_id), actor_role, action, json.dumps(details, sort_keys=True), _now_iso()),
        )

    def _row_to_application(self, row: sqlite3.Row) -> SellerApplication:
        return SellerApplication(
            id=UUID(row["id"]),
            contact_email=row["contact_email"],
            seller_name=row["seller_name"],
            status=ApplicationStatus(row["status"]),
            catalog_passport=CatalogPassport.model_validate_json(row["passport_json"]),
            valuation=ValuationResult.model_validate_json(row["valuation_json"]) if row["valuation_json"] else None,
            offers=[OfferScenario.model_validate(item) for item in json.loads(row["offers_json"])],
            accepted_offer_id=UUID(row["accepted_offer_id"]) if row["accepted_offer_id"] else None,
            consent_version=row["consent_version"],
            consent_marketing=bool(row["consent_marketing"]),
            referral_id=row["referral_id"],
            consent_at=datetime.fromisoformat(row["consent_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _get_row(self, application_id: UUID) -> sqlite3.Row:
        row = self._connection.execute("SELECT * FROM applications WHERE id = ?", (str(application_id),)).fetchone()
        if row is None:
            raise KeyError("application_not_found")
        return row

    def _assert_token(self, row: sqlite3.Row, token: str) -> None:
        if not token or not hmac.compare_digest(row["token_hash"], _hash_secret(token)):
            raise PermissionError("invalid_seller_token")

    def create_application(self, data: SellerApplicationCreate) -> tuple[SellerApplication, str]:
        application_id = uuid4()
        owner_id = uuid4()
        now = _now_iso()
        token = secrets.token_urlsafe(32)
        passport = CatalogPassport(
            owner_id=owner_id,
            artist_label=data.artist_label,
            territories=data.territories,
            royalty_sources=data.royalty_sources,
        )
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO applications
                (id, token_hash, contact_email, seller_name, status, passport_json,
                 valuation_json, offers_json, accepted_offer_id, consent_version,
                 consent_marketing, referral_id, consent_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?, NULL, ?, ?, ?, ?, ?, ?)""",
                (
                    str(application_id),
                    _hash_secret(token),
                    data.contact_email,
                    data.seller_name,
                    ApplicationStatus.SUBMITTED.value,
                    passport.model_dump_json(),
                    json.dumps([]),
                    data.consent_version,
                    int(data.consent_marketing),
                    data.referral_id,
                    now,
                    now,
                    now,
                ),
            )
            self._connection.execute(
                "INSERT INTO passport_versions (id, application_id, version, passport_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid4()), str(application_id), passport.version, passport.model_dump_json(), now),
            )
            self._audit(application_id, "APPLICATION_SUBMITTED", {"consent_version": data.consent_version}, "SELLER")
            row = self._get_row(application_id)
        return self._row_to_application(row), token

    def get_application(self, application_id: UUID, seller_token: str) -> SellerApplication:
        with self._lock:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            return self._row_to_application(row)

    def get_application_internal(self, application_id: UUID) -> SellerApplication:
        with self._lock:
            return self._row_to_application(self._get_row(application_id))

    def update_passport(
        self,
        application_id: UUID,
        seller_token: str,
        draft: CatalogPassportDraft,
    ) -> CatalogPassport:
        with self._lock, self._connection:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            if row["status"] in (ApplicationStatus.PAID.value, ApplicationStatus.REJECTED.value):
                raise ValueError("application_is_closed")
            current = CatalogPassport.model_validate_json(row["passport_json"])
            updated = CatalogPassport(
                **draft.model_dump(),
                id=current.id,
                owner_id=current.owner_id,
                version=current.version + 1,
                created_at=current.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            now = _now_iso()
            self._connection.execute(
                "UPDATE applications SET passport_json = ?, updated_at = ? WHERE id = ?",
                (updated.model_dump_json(), now, str(application_id)),
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO passport_versions (id, application_id, version, passport_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid4()), str(application_id), current.version, current.model_dump_json(), current.updated_at.isoformat()),
            )
            self._connection.execute(
                "INSERT INTO passport_versions (id, application_id, version, passport_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid4()), str(application_id), updated.version, updated.model_dump_json(), now),
            )
            self._audit(application_id, "PASSPORT_UPDATED", {"version": updated.version}, "SELLER")
            return updated

    def list_passport_versions(self, application_id: UUID, seller_token: str) -> list[CatalogPassport]:
        with self._lock:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            rows = self._connection.execute(
                "SELECT passport_json FROM passport_versions WHERE application_id = ? ORDER BY version",
                (str(application_id),),
            ).fetchall()
            if not rows:
                return [CatalogPassport.model_validate_json(row["passport_json"])]
            return [CatalogPassport.model_validate_json(item["passport_json"]) for item in rows]

    def set_status(
        self,
        application_id: UUID,
        status: ApplicationStatus,
        *,
        actor_role: str,
        action: str,
        reason: Optional[str] = None,
    ) -> None:
        with self._lock, self._connection:
            row = self._get_row(application_id)
            current = ApplicationStatus(row["status"])
            allowed = {
                ApplicationStatus.SUBMITTED: {ApplicationStatus.DATA_REQUIRED, ApplicationStatus.UNDER_REVIEW, ApplicationStatus.REJECTED},
                ApplicationStatus.DATA_REQUIRED: {ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW, ApplicationStatus.REJECTED},
                ApplicationStatus.UNDER_REVIEW: {ApplicationStatus.DATA_REQUIRED, ApplicationStatus.OFFER_READY, ApplicationStatus.REJECTED},
                ApplicationStatus.OFFER_READY: {
                    ApplicationStatus.ACCEPTED,
                    ApplicationStatus.REJECTED,
                    ApplicationStatus.UNDER_REVIEW,
                },
                ApplicationStatus.ACCEPTED: {ApplicationStatus.PAID},
                ApplicationStatus.PAID: set(),
                ApplicationStatus.REJECTED: set(),
            }
            if status != current and status not in allowed[current]:
                raise ValueError(f"invalid_status_transition:{current.value}->{status.value}")
            now = _now_iso()
            self._connection.execute(
                "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, str(application_id)),
            )
            details: dict[str, Any] = {"status": status.value}
            if reason:
                details["reason"] = reason[:500]
            self._audit(application_id, action, details, actor_role)

    def create_document(self, application_id: UUID, seller_token: str, data: DocumentCreate) -> tuple[DocumentRecord, str]:
        with self._lock, self._connection:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            if row["status"] in (ApplicationStatus.PAID.value, ApplicationStatus.REJECTED.value):
                raise ValueError("application_is_closed")
            document_id = uuid4()
            upload_token = secrets.token_urlsafe(32)
            safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", data.original_filename)[:180]
            version_row = self._connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM documents WHERE application_id = ? AND document_type = ?",
                (str(application_id), data.document_type.value),
            ).fetchone()
            version = int(version_row["next_version"])
            storage_key = f"{application_id}/{document_id}/v{version}-{safe_name}"
            document = DocumentRecord(
                id=document_id,
                application_id=application_id,
                document_type=data.document_type,
                original_filename=safe_name,
                content_type=data.content_type,
                size_bytes=data.size_bytes,
                sha256=data.sha256.lower(),
                storage_key=storage_key,
                version=version,
            )
            self._connection.execute(
                """INSERT INTO documents
                (id, application_id, document_type, original_filename, content_type,
                 size_bytes, sha256, storage_key, upload_token_hash, status, version,
                 uploaded_at, verified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
                (
                    str(document.id), str(application_id), document.document_type.value,
                    document.original_filename, document.content_type, document.size_bytes,
                    document.sha256, storage_key, _hash_secret(upload_token), document.status.value, document.version,
                ),
            )
            self._audit(application_id, "DOCUMENT_UPLOAD_REQUESTED", {"document_id": str(document.id)}, "SELLER")
            return document, upload_token

    def complete_document(
        self,
        document_id: UUID,
        upload_token: str,
        content: bytes,
        application_id: Optional[UUID] = None,
    ) -> DocumentRecord:
        with self._lock, self._connection:
            row = self._connection.execute("SELECT * FROM documents WHERE id = ?", (str(document_id),)).fetchone()
            if row is None:
                raise KeyError("document_not_found")
            if application_id is not None and row["application_id"] != str(application_id):
                raise KeyError("document_not_found")
            if not hmac.compare_digest(row["upload_token_hash"], _hash_secret(upload_token)):
                raise PermissionError("invalid_upload_token")
            if len(content) != row["size_bytes"]:
                raise ValueError("document_size_mismatch")
            digest = hashlib.sha256(content).hexdigest()
            if not hmac.compare_digest(digest, row["sha256"].lower()):
                raise ValueError("document_hash_mismatch")
            target = self.storage_dir / row["storage_key"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            now = _now_iso()
            self._connection.execute(
                "UPDATE documents SET status = ?, uploaded_at = ?, verified_at = ?, upload_token_hash = '' WHERE id = ?",
                (DocumentStatus.UPLOADED.value, now, None, str(document_id)),
            )
            self._audit(UUID(row["application_id"]), "DOCUMENT_UPLOADED", {"document_id": str(document_id)}, "SELLER")
            return self._document_from_row(
                self._connection.execute("SELECT * FROM documents WHERE id = ?", (str(document_id),)).fetchone()
            )

    def review_document(self, document_id: UUID, status: DocumentStatus, reason: Optional[str] = None) -> DocumentRecord:
        if status not in (DocumentStatus.VERIFIED, DocumentStatus.REJECTED):
            raise ValueError("document_review_status_must_be_verified_or_rejected")
        with self._lock, self._connection:
            row = self._connection.execute("SELECT * FROM documents WHERE id = ?", (str(document_id),)).fetchone()
            if row is None:
                raise KeyError("document_not_found")
            now = _now_iso()
            verified_at = now if status == DocumentStatus.VERIFIED else None
            self._connection.execute(
                "UPDATE documents SET status = ?, verified_at = ? WHERE id = ?",
                (status.value, verified_at, str(document_id)),
            )
            self._audit(
                UUID(row["application_id"]),
                "DOCUMENT_REVIEWED",
                {"document_id": str(document_id), "status": status.value, "reason": (reason or "")[:200]},
                "ADMIN",
            )
            return self._document_from_row(
                self._connection.execute("SELECT * FROM documents WHERE id = ?", (str(document_id),)).fetchone()
            )

    def get_document_internal(self, document_id: UUID) -> DocumentRecord:
        with self._lock:
            row = self._connection.execute("SELECT * FROM documents WHERE id = ?", (str(document_id),)).fetchone()
            if row is None:
                raise KeyError("document_not_found")
            return self._document_from_row(row)

    def document_download_token(self, document_id: UUID, ttl_seconds: int = 900) -> str:
        with self._lock:
            row = self._connection.execute("SELECT * FROM documents WHERE id = ?", (str(document_id),)).fetchone()
            if row is None or row["status"] != DocumentStatus.VERIFIED.value:
                raise KeyError("document_not_available")
            return self._signed_download_token("document", document_id, ttl_seconds)

    def read_document(self, document_id: UUID, download_token: str) -> tuple[bytes, str, str]:
        with self._lock:
            self._verify_download_token("document", document_id, download_token)
            row = self._connection.execute("SELECT * FROM documents WHERE id = ?", (str(document_id),)).fetchone()
            if row is None or row["status"] != DocumentStatus.VERIFIED.value:
                raise KeyError("document_not_available")
            path = (self.storage_dir / row["storage_key"]).resolve()
            if self.storage_dir.resolve() not in path.parents or not path.is_file():
                raise KeyError("document_not_available")
            return path.read_bytes(), row["content_type"], row["sha256"]

    def _document_from_row(self, row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            id=UUID(row["id"]), application_id=UUID(row["application_id"]),
            document_type=row["document_type"], original_filename=row["original_filename"],
            content_type=row["content_type"], size_bytes=row["size_bytes"], sha256=row["sha256"],
            storage_key=row["storage_key"], status=row["status"], version=row["version"],
            uploaded_at=datetime.fromisoformat(row["uploaded_at"]) if row["uploaded_at"] else None,
            verified_at=datetime.fromisoformat(row["verified_at"]) if row["verified_at"] else None,
        )

    def list_documents(self, application_id: UUID, seller_token: str) -> list[DocumentRecord]:
        with self._lock:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            rows = self._connection.execute(
                "SELECT * FROM documents WHERE application_id = ? ORDER BY version, id", (str(application_id),)
            ).fetchall()
            return [self._document_from_row(item) for item in rows]

    def list_documents_internal(self, application_id: UUID) -> list[DocumentRecord]:
        with self._lock:
            self._get_row(application_id)
            rows = self._connection.execute(
                "SELECT * FROM documents WHERE application_id = ? ORDER BY version, id", (str(application_id),)
            ).fetchall()
            return [self._document_from_row(item) for item in rows]

    def save_valuation(
        self,
        application_id: UUID,
        valuation: ValuationResult,
        offers: list[OfferScenario],
        *,
        status: ApplicationStatus = ApplicationStatus.OFFER_READY,
    ) -> None:
        with self._lock, self._connection:
            self._get_row(application_id)
            now = _now_iso()
            self._connection.execute(
                "UPDATE applications SET status = ?, valuation_json = ?, offers_json = ?, updated_at = ? WHERE id = ?",
                (
                    status.value,
                    valuation.model_dump_json(),
                    json.dumps([offer.model_dump(mode="json") for offer in offers]),
                    now,
                    str(application_id),
                ),
            )
            self._audit(application_id, "VALUATION_COMPLETED", {"valuation_version": valuation.version}, "SYSTEM")
            self._audit(application_id, "OFFERS_CREATED", {"count": len(offers)}, "SYSTEM")

    def accept_offer(self, application_id: UUID, seller_token: str, offer_id: UUID) -> OfferScenario:
        with self._lock, self._connection:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            application = self._row_to_application(row)
            if application.status != ApplicationStatus.OFFER_READY:
                raise ValueError("application_not_ready_for_acceptance")
            offer = next((item for item in application.offers if item.id == offer_id), None)
            if offer is None:
                raise KeyError("offer_not_found")
            if datetime.now(timezone.utc).date() > offer.valid_until:
                raise ValueError("offer_expired")
            now = _now_iso()
            self._connection.execute(
                "UPDATE applications SET status = ?, accepted_offer_id = ?, updated_at = ? WHERE id = ?",
                (ApplicationStatus.ACCEPTED.value, str(offer_id), now, str(application_id)),
            )
            self._audit(application_id, "OFFER_ACCEPTED", {"offer_id": str(offer_id)}, "SELLER")
            return offer

    def decline_offer(self, application_id: UUID, seller_token: str, offer_id: UUID) -> None:
        with self._lock, self._connection:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            application = self._row_to_application(row)
            if application.status != ApplicationStatus.OFFER_READY:
                raise ValueError("application_not_ready_for_decline")
            if not any(item.id == offer_id for item in application.offers):
                raise KeyError("offer_not_found")
            now = _now_iso()
            self._connection.execute(
                "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
                (ApplicationStatus.REJECTED.value, now, str(application_id)),
            )
            self._audit(application_id, "OFFER_DECLINED", {"offer_id": str(offer_id)}, "SELLER")

    def create_payout_intent(
        self,
        application_id: UUID,
        offer_id: UUID,
        idempotency_key: str,
        amount_cents: int,
        currency_code: str,
        recipient_token: Optional[str] = None,
    ) -> PayoutView:
        with self._lock, self._connection:
            application = self._row_to_application(self._get_row(application_id))
            existing = self._connection.execute(
                "SELECT * FROM payout_intents WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if existing:
                recipient_hash = _hash_secret(recipient_token) if recipient_token else None
                if (
                    existing["application_id"] != str(application_id)
                    or existing["offer_id"] != str(offer_id)
                    or existing["amount_cents"] != amount_cents
                    or existing["currency_code"] != currency_code
                    or (existing["recipient_token_hash"] and existing["recipient_token_hash"] != recipient_hash)
                ):
                    raise ValueError("idempotency_key_conflict")
                return self._payout_from_row(existing)
            already_paid = self._connection.execute(
                """SELECT id FROM payout_intents
                   WHERE application_id = ? AND offer_id = ? AND status = 'SUCCEEDED'""",
                (str(application_id), str(offer_id)),
            ).fetchone()
            if already_paid:
                raise ValueError("payout_already_succeeded")
            if application.status != ApplicationStatus.ACCEPTED:
                raise ValueError("application_not_accepted")
            if application.accepted_offer_id != offer_id:
                raise ValueError("offer_not_accepted")
            intent_id = uuid4()
            now = _now_iso()
            self._connection.execute(
                """INSERT INTO payout_intents
                (id, application_id, offer_id, idempotency_key, recipient_token_hash, amount_cents,
                 currency_code, status, provider_reference, failure_reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'PROCESSING', NULL, NULL, ?, ?)""",
                (
                    str(intent_id),
                    str(application_id),
                    str(offer_id),
                    idempotency_key,
                    _hash_secret(recipient_token) if recipient_token else None,
                    amount_cents,
                    currency_code,
                    now,
                    now,
                ),
            )
            self._audit(application_id, "PAYOUT_INTENT_CREATED", {"payout_intent_id": str(intent_id)}, "SYSTEM")
            return self._payout_from_row(
                self._connection.execute("SELECT * FROM payout_intents WHERE id = ?", (str(intent_id),)).fetchone()
            )

    def complete_payout(self, payout_intent_id: UUID, provider_reference: str) -> PayoutView:
        with self._lock, self._connection:
            row = self._connection.execute("SELECT * FROM payout_intents WHERE id = ?", (str(payout_intent_id),)).fetchone()
            if row is None:
                raise KeyError("payout_intent_not_found")
            if row["status"] == "SUCCEEDED":
                return self._payout_from_row(row)
            now = _now_iso()
            receipt_version = "receipt-v1"
            receipt_key = f"{row['application_id']}/{payout_intent_id}/{receipt_version}.pdf"
            receipt_path = self.storage_dir / "receipts" / receipt_key
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_bytes = self._make_receipt_pdf(row, provider_reference, now)
            receipt_path.write_bytes(receipt_bytes)
            receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
            self._connection.execute(
                """UPDATE payout_intents SET status = 'SUCCEEDED', provider_reference = ?,
                   receipt_sha256 = ?, receipt_version = ?, receipt_storage_key = ?, updated_at = ?
                   WHERE id = ?""",
                (provider_reference, receipt_sha256, receipt_version, receipt_key, now, str(payout_intent_id)),
            )
            self._connection.execute(
                """INSERT OR IGNORE INTO ledger_entries
                (id, payout_intent_id, application_id, debit_account, credit_account,
                 amount_cents, currency_code, reference_id, created_at)
                VALUES (?, ?, ?, 'catalog_acquisition', 'seller_payable', ?, ?, ?, ?)""",
                (
                    str(uuid4()), str(payout_intent_id), row["application_id"], row["amount_cents"],
                    row["currency_code"], provider_reference, now,
                ),
            )
            self._connection.execute(
                "UPDATE applications SET status = 'PAID', updated_at = ? WHERE id = ?",
                (now, row["application_id"]),
            )
            self._audit(UUID(row["application_id"]), "PAYOUT_SUCCEEDED", {"reference": provider_reference}, "SYSTEM")
            return self._payout_from_row(
                self._connection.execute("SELECT * FROM payout_intents WHERE id = ?", (str(payout_intent_id),)).fetchone()
            )

    def fail_payout(self, payout_intent_id: UUID, failure_reason: str) -> PayoutView:
        with self._lock, self._connection:
            row = self._connection.execute("SELECT * FROM payout_intents WHERE id = ?", (str(payout_intent_id),)).fetchone()
            if row is None:
                raise KeyError("payout_intent_not_found")
            now = _now_iso()
            self._connection.execute(
                "UPDATE payout_intents SET status = 'FAILED', failure_reason = ?, updated_at = ? WHERE id = ?",
                (failure_reason[:500], now, str(payout_intent_id)),
            )
            self._audit(UUID(row["application_id"]), "PAYOUT_FAILED", {"reason": failure_reason[:200]}, "SYSTEM")
            return self._payout_from_row(
                self._connection.execute("SELECT * FROM payout_intents WHERE id = ?", (str(payout_intent_id),)).fetchone()
            )

    def list_payouts(self, application_id: UUID, seller_token: str) -> list[PayoutView]:
        with self._lock:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            rows = self._connection.execute(
                "SELECT * FROM payout_intents WHERE application_id = ? ORDER BY created_at", (str(application_id),)
            ).fetchall()
            return [self._payout_from_row(item) for item in rows]

    def get_payout(self, application_id: UUID, seller_token: str, payout_intent_id: UUID) -> PayoutView:
        with self._lock:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            payout = self._connection.execute(
                "SELECT * FROM payout_intents WHERE id = ? AND application_id = ?",
                (str(payout_intent_id), str(application_id)),
            ).fetchone()
            if payout is None:
                raise KeyError("payout_not_found")
            return self._payout_from_row(payout)

    def get_payout_internal(self, payout_intent_id: UUID) -> PayoutView:
        with self._lock:
            payout = self._connection.execute(
                "SELECT * FROM payout_intents WHERE id = ?", (str(payout_intent_id),)
            ).fetchone()
            if payout is None:
                raise KeyError("payout_not_found")
            return self._payout_from_row(payout)

    def _make_receipt_pdf(self, payout_row: sqlite3.Row, provider_reference: str, created_at: str) -> bytes:
        """Create a minimal text PDF without requiring native PDF libraries."""
        lines = [
            "SpaceMusic payout receipt",
            f"Payout intent: {payout_row['id']}",
            f"Offer: {payout_row['offer_id']}",
            f"Amount: {payout_row['amount_cents']} {payout_row['currency_code']}",
            f"Reference: {provider_reference}",
            f"Created: {created_at}",
        ]
        def pdf_escape(value: str) -> str:
            return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        stream = "BT /F1 11 Tf 50 760 Td " + " 0 -24 Td ".join(
            f"({pdf_escape(line)}) Tj" for line in lines
        ) + " ET"
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            f"<< /Length {len(stream.encode('ascii'))} >>\nstream\n{stream}\nendstream".encode("ascii"),
        ]
        result = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(result))
            result.extend(f"{index} 0 obj\n".encode("ascii"))
            result.extend(obj)
            result.extend(b"\nendobj\n")
        xref_offset = len(result)
        result.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        result.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            result.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        result.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
        return bytes(result)

    def _signed_download_token(self, kind: str, object_id: UUID, ttl_seconds: int = 900) -> str:
        expires_at = int(datetime.now(timezone.utc).timestamp()) + ttl_seconds
        signature = _hash_secret(f"download:{kind}:{object_id}:{expires_at}")
        return f"{expires_at}.{signature}"

    def _verify_download_token(self, kind: str, object_id: UUID, token: str) -> None:
        try:
            expires_text, signature = token.split(".", 1)
            expires_at = int(expires_text)
        except (AttributeError, ValueError):
            raise PermissionError("invalid_download_token")
        if expires_at < int(datetime.now(timezone.utc).timestamp()):
            raise PermissionError("download_token_expired")
        expected = _hash_secret(f"download:{kind}:{object_id}:{expires_at}")
        if not hmac.compare_digest(expected, signature):
            raise PermissionError("invalid_download_token")

    def receipt_download_token(self, payout_intent_id: UUID, ttl_seconds: int = 900) -> str:
        with self._lock:
            row = self._connection.execute("SELECT * FROM payout_intents WHERE id = ?", (str(payout_intent_id),)).fetchone()
            if row is None or not row["receipt_storage_key"]:
                raise KeyError("receipt_not_found")
            return self._signed_download_token("receipt", payout_intent_id, ttl_seconds)

    def read_receipt(self, payout_intent_id: UUID, download_token: str) -> tuple[bytes, str]:
        with self._lock:
            self._verify_download_token("receipt", payout_intent_id, download_token)
            row = self._connection.execute("SELECT * FROM payout_intents WHERE id = ?", (str(payout_intent_id),)).fetchone()
            if row is None or not row["receipt_storage_key"]:
                raise KeyError("receipt_not_found")
            path = (self.storage_dir / "receipts" / row["receipt_storage_key"]).resolve()
            if self.storage_dir.resolve() not in path.parents or not path.is_file():
                raise KeyError("receipt_not_found")
            return path.read_bytes(), row["receipt_sha256"]

    def create_royalty_report(self, application_id: UUID, seller_token: str, data: RoyaltyReportCreate) -> RoyaltyReport:
        with self._lock, self._connection:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            report = RoyaltyReport(application_id=application_id, **data.model_dump())
            self._connection.execute(
                """INSERT INTO royalty_reports
                (id, application_id, period_start, period_end, amount_cents, currency_code, source, notes, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(report.id), str(application_id), report.period_start.isoformat(), report.period_end.isoformat(),
                 report.amount_cents, report.currency_code, report.source.value, report.notes,
                 report.status.value, report.created_at.isoformat()),
            )
            self._audit(application_id, "ROYALTY_REPORT_SUBMITTED", {"report_id": str(report.id)}, "SELLER")
            return report

    def list_royalty_reports(self, application_id: UUID, seller_token: str) -> list[RoyaltyReport]:
        with self._lock:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            rows = self._connection.execute(
                "SELECT * FROM royalty_reports WHERE application_id = ? ORDER BY period_start DESC",
                (str(application_id),),
            ).fetchall()
            return [
                RoyaltyReport(
                    id=UUID(item["id"]), application_id=UUID(item["application_id"]),
                    period_start=item["period_start"], period_end=item["period_end"],
                    amount_cents=item["amount_cents"], currency_code=item["currency_code"],
                    source=item["source"], notes=item["notes"], status=item["status"],
                    created_at=datetime.fromisoformat(item["created_at"]),
                )
                for item in rows
            ]

    def create_support_request(self, application_id: UUID, seller_token: str, data: SupportRequestCreate) -> dict[str, Any]:
        with self._lock, self._connection:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            ticket_id = uuid4()
            now = _now_iso()
            self._connection.execute(
                "INSERT INTO support_requests (id, application_id, subject, message, status, created_at) VALUES (?, ?, ?, ?, 'OPEN', ?)",
                (str(ticket_id), str(application_id), data.subject, data.message, now),
            )
            self._audit(application_id, "SUPPORT_REQUESTED", {"ticket_id": str(ticket_id)}, "SELLER")
            return {"id": ticket_id, "status": "OPEN", "created_at": now}

    def list_applications_internal(self, status: Optional[ApplicationStatus] = None) -> list[SellerApplication]:
        with self._lock:
            if status:
                rows = self._connection.execute(
                    "SELECT * FROM applications WHERE status = ? ORDER BY created_at", (status.value,)
                ).fetchall()
            else:
                rows = self._connection.execute("SELECT * FROM applications ORDER BY created_at").fetchall()
            return [self._row_to_application(row) for row in rows]

    def redact_personal_data(self, application_id: UUID) -> None:
        with self._lock, self._connection:
            self._get_row(application_id)
            now = _now_iso()
            self._connection.execute(
                "UPDATE applications SET contact_email = ?, seller_name = NULL, consent_marketing = 0, token_hash = ?, updated_at = ? WHERE id = ?",
                (f"redacted+{application_id}@invalid.local", secrets.token_hex(32), now, str(application_id)),
            )
            self._connection.execute("UPDATE support_requests SET message = '[REDACTED]' WHERE application_id = ?", (str(application_id),))
            self._audit(application_id, "PERSONAL_DATA_REDACTED", {}, "ADMIN")

    def timeline(self, application_id: UUID, seller_token: str) -> list[dict[str, Any]]:
        with self._lock:
            row = self._get_row(application_id)
            self._assert_token(row, seller_token)
            events = self._connection.execute(
                "SELECT id, actor_role, action, details_json, created_at FROM audit_events WHERE application_id = ? ORDER BY created_at",
                (str(application_id),),
            ).fetchall()
            return [
                {
                    "id": item["id"], "actor_role": item["actor_role"], "action": item["action"],
                    "details": json.loads(item["details_json"]), "created_at": item["created_at"],
                }
                for item in events
            ]

    def _payout_from_row(self, row: sqlite3.Row) -> PayoutView:
        return PayoutView(
            id=UUID(row["id"]), application_id=UUID(row["application_id"]), offer_id=UUID(row["offer_id"]),
            amount_cents=row["amount_cents"], currency_code=row["currency_code"], status=row["status"],
            provider_reference=row["provider_reference"], failure_reason=row["failure_reason"],
            receipt_sha256=row["receipt_sha256"], receipt_version=row["receipt_version"],
            created_at=datetime.fromisoformat(row["created_at"]), updated_at=datetime.fromisoformat(row["updated_at"]),
        )
