from __future__ import annotations

from contextlib import contextmanager
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
from threading import RLock
import time
from uuid import uuid4

from .contracts import CatalogInput, EmailInput, file_metadata


class Conflict(ValueError):
    pass


class LocalPortalStore:
    """Transactional local adapter. Production startup is separately prohibited."""

    def __init__(self, directory: Path, secret: bytes, clock=time.time):
        if len(secret) < 32:
            raise ValueError(
                "An explicit random secret of at least 32 bytes is required"
            )
        self.root = directory.resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self.files = self.root / "documents"
        self.files.mkdir(mode=0o700, exist_ok=True)
        self.secret, self.clock, self.lock = secret, clock, RLock()
        self.db = sqlite3.connect(
            str(self.root / "portal.sqlite"), check_same_thread=False
        )
        os.chmod(self.root / "portal.sqlite", 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY, source_key TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL, contact_json TEXT NOT NULL,
                catalog_json TEXT, revision INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'SUBMITTED', created INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS reviews_email ON reviews(email);
            CREATE TABLE IF NOT EXISTS links (
                hash TEXT PRIMARY KEY, email TEXT NOT NULL, expires INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sessions (
                hash TEXT PRIMARY KEY, email TEXT NOT NULL, expires INTEGER NOT NULL, last_seen INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rate_limits (
                key TEXT PRIMARY KEY, started INTEGER NOT NULL, count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, review_id TEXT NOT NULL REFERENCES reviews(id), kind TEXT NOT NULL,
                name TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL, scan TEXT NOT NULL,
                created INTEGER NOT NULL, UNIQUE(review_id, kind)
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY, review_id TEXT NOT NULL REFERENCES reviews(id), role TEXT NOT NULL,
                body TEXT NOT NULL, created INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, review_id TEXT NOT NULL REFERENCES reviews(id), action TEXT NOT NULL,
                created INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS owner_email_tests (
                id TEXT PRIMARY KEY, origin TEXT NOT NULL, expires INTEGER NOT NULL,
                provider_id TEXT
            );
        """
        )

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def digest(self, value):
        return hmac.new(self.secret, value.encode(), hashlib.sha256).hexdigest()

    def audit(self, review_id, action):
        self.db.execute(
            "INSERT INTO events VALUES(?,?,?,?)",
            (str(uuid4()), review_id, action, int(self.clock())),
        )

    def ingest(self, form: str, submission: dict, public_paths: set):
        if not isinstance(submission, dict) or not submission.get("_date"):
            raise ValueError("A submission timestamp is required")
        email = EmailInput(email=submission.get("email", "")).email
        if email.rsplit("@", 1)[-1] != "example.com":
            raise ValueError(
                "This local test service accepts example.com identities only"
            )
        artist = submission.get("artistLabel", "")
        if not isinstance(artist, str) or not 1 <= len(artist.strip()) <= 300:
            raise ValueError("An artist or label name is required")
        contact = {"email": email, "artist": artist.strip()}
        for source, dest in [
            ("firstName", "name"),
            ("territories", "territories"),
            ("referralId", "referralId"),
        ]:
            value = submission.get(source, "")
            if not isinstance(value, str) or len(value) > 500:
                raise ValueError("Invalid contact field")
            contact[dest] = value
        contact["consentMarketing"] = submission.get("consentMarketing") in (
            True,
            "true",
        )
        for key in ("landing_path", "apply_source_path"):
            value = submission.get(key, "")
            contact[key] = (
                value if isinstance(value, str) and value in public_paths else ""
            )
        # Stable across signature timestamps and JSON key ordering; not an email-only dedupe.
        source_key = self.digest(
            "intake:"
            + json.dumps([form, submission], sort_keys=True, separators=(",", ":"))
        )
        with self.transaction():
            existing = self.db.execute(
                "SELECT id FROM reviews WHERE source_key=?", (source_key,)
            ).fetchone()
            if existing:
                return existing["id"], False
            review_id = str(uuid4())
            self.db.execute(
                "INSERT INTO reviews(id,source_key,email,contact_json,created) VALUES(?,?,?,?,?)",
                (review_id, source_key, email, json.dumps(contact), int(self.clock())),
            )
            self.audit(review_id, "TEST_FORMSPREE_RECEIPT_IMPORTED")
            return review_id, True

    def rate_limit(self, key, maximum, window):
        now = int(self.clock())
        with self.transaction():
            key = self.digest("rate:" + key)
            row = self.db.execute(
                "SELECT * FROM rate_limits WHERE key=?", (key,)
            ).fetchone()
            if row and now - row["started"] < window:
                if row["count"] >= maximum:
                    return False
                self.db.execute(
                    "UPDATE rate_limits SET count=count+1 WHERE key=?", (key,)
                )
            else:
                self.db.execute(
                    "INSERT OR REPLACE INTO rate_limits VALUES(?,?,1)", (key, now)
                )
            self.db.execute("DELETE FROM rate_limits WHERE started<?", (now - 86400,))
            return True

    def issue_link(self, email):
        with self.transaction():
            if not self.db.execute(
                "SELECT 1 FROM reviews WHERE email=?", (email,)
            ).fetchone():
                return None
            token = secrets.token_urlsafe(32)
            # A resend does not invalidate a still-valid delivered link (prevents resend DoS).
            self.db.execute(
                "DELETE FROM links WHERE expires<=? OR used=1", (int(self.clock()),)
            )
            self.db.execute(
                "INSERT INTO links VALUES(?,?,?,0)",
                (self.digest("link:" + token), email, int(self.clock()) + 900),
            )
            return token

    def consume_link(self, token, previous_session=""):
        now = int(self.clock())
        with self.transaction():
            row = self.db.execute(
                "SELECT * FROM links WHERE hash=? AND used=0 AND expires>?",
                (self.digest("link:" + token), now),
            ).fetchone()
            if not row:
                raise PermissionError(
                    "This sign-in link is invalid, expired or already used"
                )
            self.db.execute("UPDATE links SET used=1 WHERE email=?", (row["email"],))
            self.db.execute(
                "DELETE FROM sessions WHERE hash=? OR expires<=?",
                (self.digest("session:" + previous_session), now),
            )
            session = secrets.token_urlsafe(32)
            self.db.execute(
                "INSERT INTO sessions VALUES(?,?,?,?)",
                (self.digest("session:" + session), row["email"], now + 12 * 3600, now),
            )
            return session

    def prepare_owner_email(self, request_id, origin):
        # Derive the same secret token for retries without persisting its plaintext.
        token = (
            base64.urlsafe_b64encode(
                hmac.new(
                    self.secret,
                    ("owner-email-v1:" + request_id).encode(),
                    hashlib.sha256,
                ).digest()
            )
            .decode()
            .rstrip("=")
        )
        now = int(self.clock())
        with self.transaction():
            row = self.db.execute(
                "SELECT * FROM owner_email_tests WHERE id=?", (request_id,)
            ).fetchone()
            if row:
                if row["origin"] != origin:
                    raise Conflict(
                        "The test server address changed. Prepare another email test"
                    )
                if row["provider_id"]:
                    return token, row["provider_id"]
                active = self.db.execute(
                    "SELECT 1 FROM links WHERE hash=? AND used=0 AND expires>?",
                    (self.digest("link:" + token), now),
                ).fetchone()
                if not active:
                    raise Conflict(
                        "This test link expired or was used. Prepare another email test"
                    )
                return token, None
            if not self.db.execute(
                "SELECT 1 FROM reviews WHERE email='alex@example.com'"
            ).fetchone():
                raise Conflict("Create the fictional test application first")
            self.db.execute(
                "INSERT INTO owner_email_tests VALUES(?,?,?,NULL)",
                (request_id, origin, now + 900),
            )
            self.db.execute(
                "INSERT INTO links VALUES(?,?,?,0)",
                (self.digest("link:" + token), "alex@example.com", now + 900),
            )
            return token, None

    def accept_owner_email(self, request_id, provider_id):
        with self.transaction():
            self.db.execute(
                "UPDATE owner_email_tests SET provider_id=? WHERE id=?",
                (provider_id, request_id),
            )

    def latest_owner_email(self):
        with self.lock:
            row = self.db.execute(
                "SELECT * FROM owner_email_tests ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            return {
                "request_id": row["id"],
                "accepted": row["provider_id"] is not None,
                "expired": row["expires"] <= int(self.clock()),
            }

    def authenticate(self, token):
        now = int(self.clock())
        with self.transaction():
            row = self.db.execute(
                "SELECT * FROM sessions WHERE hash=? AND expires>? AND last_seen>?",
                (self.digest("session:" + token), now, now - 1800),
            ).fetchone()
            if not row:
                raise PermissionError(
                    "Your session has expired. Request a new sign-in link"
                )
            self.db.execute(
                "UPDATE sessions SET last_seen=? WHERE hash=?", (now, row["hash"])
            )
            return row["email"]

    def revoke(self, token, all_sessions=False):
        with self.transaction():
            hashed = self.digest("session:" + token)
            if all_sessions:
                self.db.execute(
                    "DELETE FROM sessions WHERE email IN (SELECT email FROM sessions WHERE hash=?)",
                    (hashed,),
                )
            else:
                self.db.execute("DELETE FROM sessions WHERE hash=?", (hashed,))

    def owned_review(self, review_id, email):
        row = self.db.execute(
            "SELECT * FROM reviews WHERE id=? AND email=?", (review_id, email)
        ).fetchone()
        if not row:
            raise KeyError("Review not found")
        return row

    def view(self, review_id, email):
        with self.lock:
            row = self.owned_review(review_id, email)
            return {
                "id": row["id"],
                "contact": json.loads(row["contact_json"]),
                "catalog": (
                    json.loads(row["catalog_json"]) if row["catalog_json"] else None
                ),
                "revision": row["revision"],
                "status": row["status"],
                "created": row["created"],
                "documents": [
                    dict(r)
                    for r in self.db.execute(
                        "SELECT id,kind,name,size,sha256,scan,created FROM documents WHERE review_id=? ORDER BY created,id",
                        (review_id,),
                    )
                ],
                "messages": [
                    dict(r)
                    for r in self.db.execute(
                        "SELECT id,role,body,created FROM messages WHERE review_id=? ORDER BY created,rowid",
                        (review_id,),
                    )
                ],
            }

    def list_reviews(self, email):
        with self.lock:
            return [
                {
                    "id": r["id"],
                    "artist": json.loads(r["contact_json"])["artist"],
                    "status": r["status"],
                }
                for r in self.db.execute(
                    "SELECT * FROM reviews WHERE email=? ORDER BY created,id", (email,)
                )
            ]

    def expect_edit(self, review_id, email, revision):
        row = self.owned_review(review_id, email)
        if row["revision"] != revision:
            raise Conflict(
                "This review changed in another tab. Reload before saving; your input has not been overwritten"
            )
        if row["status"] != "SUBMITTED":
            raise Conflict(
                "The submitted package is read-only. Respond to the reviewer instead"
            )
        return row

    def save_catalog(self, review_id, email, revision, catalog: CatalogInput):
        with self.transaction():
            self.expect_edit(review_id, email, revision)
            self.db.execute(
                "UPDATE reviews SET catalog_json=?,revision=revision+1 WHERE id=?",
                (catalog.model_dump_json(), review_id),
            )
            self.audit(review_id, "CATALOG_SAVED_UNVERIFIED")

    def add_document(self, review_id, email, revision, kind, name, body):
        metadata = file_metadata(name, body, kind)
        document_id = str(uuid4())
        target = self.files / document_id
        try:
            with self.transaction():
                self.expect_edit(review_id, email, revision)
                if self.db.execute(
                    "SELECT 1 FROM documents WHERE review_id=? AND kind=?",
                    (review_id, kind),
                ).fetchone():
                    raise Conflict(
                        "This item already exists. Remove it before uploading a replacement"
                    )
                with open(target, "xb") as stream:
                    os.chmod(target, 0o600)
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                self.db.execute(
                    "INSERT INTO documents(id,review_id,kind,name,size,sha256,scan,created) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        document_id,
                        review_id,
                        kind,
                        metadata["name"],
                        metadata["size"],
                        metadata["sha256"],
                        metadata["scan"],
                        int(self.clock()),
                    ),
                )
                self.db.execute(
                    "UPDATE reviews SET revision=revision+1 WHERE id=?", (review_id,)
                )
                self.audit(review_id, "EVIDENCE_RECEIVED_" + metadata["scan"])
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def remove_document(self, review_id, email, revision, document_id):
        with self.transaction():
            self.expect_edit(review_id, email, revision)
            row = self.db.execute(
                "SELECT * FROM documents WHERE id=? AND review_id=?",
                (document_id, review_id),
            ).fetchone()
            if not row:
                raise KeyError("Document not found")
            self.db.execute("DELETE FROM documents WHERE id=?", (document_id,))
            self.db.execute(
                "UPDATE reviews SET revision=revision+1 WHERE id=?", (review_id,)
            )
            self.audit(review_id, "EVIDENCE_REMOVED")
        (self.files / document_id).unlink(missing_ok=True)

    def document_content(self, review_id, email, document_id):
        with self.lock:
            self.owned_review(review_id, email)
            row = self.db.execute(
                "SELECT * FROM documents WHERE review_id=? AND id=?",
                (review_id, document_id),
            ).fetchone()
            if not row:
                raise KeyError("Document not found")
            if row["scan"] != "TEST_FIXTURE":
                raise Conflict(
                    "This document is quarantined. Download requires content scanning"
                )
            content = self.checked_bytes(row)
            self.db.execute(
                "INSERT INTO events VALUES(?,?,?,?)",
                (str(uuid4()), review_id, "DOCUMENT_DOWNLOADED", int(self.clock())),
            )
            self.db.commit()
            return content, row["name"]

    def checked_bytes(self, row):
        target = self.files / row["id"]
        if target.is_symlink() or not target.is_file():
            raise Conflict(
                "Stored evidence is missing or unavailable. Replace the file before submission"
            )
        content = target.read_bytes()
        if (
            len(content) != row["size"]
            or hashlib.sha256(content).hexdigest() != row["sha256"]
        ):
            raise Conflict(
                "Document integrity check failed. Replace the file before submission"
            )
        return content

    def submit(self, review_id, email, revision):
        with self.transaction():
            row = self.owned_review(review_id, email)
            if row["status"] == "UNDER_REVIEW" and row["revision"] == revision + 1:
                return  # A lost success response may safely be retried.
            self.expect_edit(review_id, email, revision)
            docs = self.db.execute(
                "SELECT * FROM documents WHERE review_id=?", (review_id,)
            ).fetchall()
            if (
                not row["catalog_json"]
                or {d["kind"] for d in docs} != {"royalties", "tracks"}
                or any(d["scan"] != "TEST_FIXTURE" for d in docs)
            ):
                raise Conflict(
                    "Save the catalog and add both test fixtures first. Quarantined files cannot be submitted"
                )
            for document in docs:
                self.checked_bytes(document)
            CatalogInput.model_validate_json(row["catalog_json"])
            self.db.execute(
                "UPDATE reviews SET status='UNDER_REVIEW',revision=revision+1 WHERE id=?",
                (review_id,),
            )
            self.audit(review_id, "PACKAGE_SUBMITTED_FOR_MANUAL_REVIEW")

    def ask(self, review_id, email):
        with self.transaction():
            row = self.owned_review(review_id, email)
            if row["status"] != "UNDER_REVIEW":
                raise Conflict("A submitted package is required")
            self.db.execute(
                "INSERT INTO messages VALUES(?,?,?,?,?)",
                (
                    str(uuid4()),
                    review_id,
                    "TEST_REVIEWER",
                    "Does the reported income represent your share after collaborator splits, or the catalog total?",
                    int(self.clock()),
                ),
            )
            self.db.execute(
                "UPDATE reviews SET status='DATA_REQUIRED',revision=revision+1 WHERE id=?",
                (review_id,),
            )
            self.audit(review_id, "TEST_CLARIFICATION_REQUESTED")

    def reply(self, review_id, email, revision, message):
        with self.transaction():
            row = self.owned_review(review_id, email)
            if row["revision"] != revision or row["status"] != "DATA_REQUIRED":
                raise Conflict("The request changed. Reload before replying")
            self.db.execute(
                "INSERT INTO messages VALUES(?,?,?,?,?)",
                (str(uuid4()), review_id, "SELLER", message, int(self.clock())),
            )
            self.db.execute(
                "UPDATE reviews SET status='UNDER_REVIEW',revision=revision+1 WHERE id=?",
                (review_id,),
            )
            self.audit(review_id, "CLARIFICATION_RECEIVED_UNVERIFIED")
