import hashlib
import json
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode
from uuid import UUID

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.decode_credential_public_key import decode_credential_public_key
from webauthn.helpers.decoded_public_key_to_cryptography import (
    decoded_public_key_to_cryptography,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    CredentialDeviceType,
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)

from .config import StaffError, b64, unb64, utcnow
from .repository import audit, lock_principal


@dataclass(frozen=True)
class StaffIdentity:
    principal_id: str
    display_name: str
    issuer: str
    subject: str
    workspace_id: Optional[str]
    uv_at: Optional[datetime]
    role: str
    state: str
    session_reference: str
    expires_at: datetime


class StaffService:
    """No bool-MFA setter. Only verified signatures can produce a fresh UV proof."""

    def __init__(
        self,
        repository,
        settings,
        *,
        oidc_verifier=None,
        exchange_code=None,
        clock=utcnow,
    ):
        settings.validate()
        if oidc_verifier is not None and oidc_verifier.client_id != settings.client_id:
            raise ValueError("OIDC verifier must use the configured client ID")
        self.repo, self.settings, self.clock = repository, settings, clock
        self.oidc_verifier, self.exchange_code = oidc_verifier, exchange_code

    def _challenge(self, db, kind, binding, payload, seconds=120):
        now = self.clock()
        nonce = secrets.token_bytes(32)
        payload = {**payload, "nonce": b64(nonce)}
        identifier = self.repo.add_challenge(
            db,
            kind=kind,
            binding=binding,
            generation=self.settings.generation,
            payload=payload,
            now=now,
            expires=now + timedelta(seconds=seconds),
        )
        return identifier, nonce

    def begin_oidc(self):
        if self.exchange_code is None or self.oidc_verifier is None:
            raise StaffError("staff_identity_unavailable", 503)
        binding, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.repo.transaction() as db:
            state, nonce = self._challenge(
                db,
                "oidc",
                self.settings.digest("browser", binding),
                {"pkce_verifier": verifier},
                seconds=300,
            )
        query = urlencode(
            {
                "client_id": self.settings.client_id,
                "redirect_uri": self.settings.redirect_uri,
                "response_type": "code",
                "scope": "openid email",
                "state": state,
                "nonce": b64(nonce),
                "code_challenge_method": "S256",
                "code_challenge": b64(hashlib.sha256(verifier.encode()).digest()),
            }
        )
        # The adapter MUST put browser_binding in a dedicated HttpOnly cookie,
        # not in the URL, browser storage, or the response's public JSON.
        return {
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?"
            + query,
            "browser_binding": binding,
            "state": state,
        }

    def complete_oidc(self, *, state, browser_binding, code):
        if self.exchange_code is None or self.oidc_verifier is None:
            raise StaffError("staff_identity_unavailable", 503)
        challenge = self.repo.take_challenge(
            state,
            "oidc",
            self.settings.digest("browser", browser_binding),
            self.settings.generation,
            self.clock(),
        )
        if not isinstance(code, str) or not 1 <= len(code) <= 4096:
            raise StaffError("invalid_google_identity")
        try:
            token = self.exchange_code(
                code=code,
                code_verifier=challenge["payload"]["pkce_verifier"],
                redirect_uri=self.settings.redirect_uri,
            )
        except Exception:
            raise StaffError("staff_identity_unavailable", 503) from None
        identity = self.oidc_verifier.verify(
            token,
            nonce=challenge["payload"]["nonce"],
            started_at=challenge["created_at"],
        )
        session = secrets.token_urlsafe(32)
        with self.repo.transaction() as db:
            db.execute(
                "SELECT * FROM catalog_staff.principals WHERE issuer=%s AND subject=%s FOR UPDATE",
                (identity["issuer"], identity["subject"]),
            )
            principal = db.fetchone()
            now = self.clock()
            if (
                not principal
                or principal["state"] == "suspended"
                or challenge["expires_at"] <= now
            ):
                raise StaffError()
            expires = min(
                now + timedelta(hours=1),
                datetime.fromtimestamp(identity["expires"], timezone.utc),
            )
            if expires <= now:
                raise StaffError()
            db.execute(
                "UPDATE catalog_staff.sessions SET revoked_at=%s WHERE principal_id=%s AND revoked_at IS NULL",
                (now, principal["principal_id"]),
            )
            db.execute(
                """INSERT INTO catalog_staff.sessions
                (session_digest,principal_id,enrollment_epoch,generation,created_at,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s)""",
                (
                    self.settings.digest("session", session),
                    principal["principal_id"],
                    principal["enrollment_epoch"],
                    self.settings.generation,
                    now,
                    expires,
                ),
            )
            audit(db, principal["principal_id"], "oidc_authenticated", now)
        return session

    def cancel_oidc(self, *, state, browser_binding):
        self.repo.take_challenge(
            state,
            "oidc",
            self.settings.digest("browser", browser_binding),
            self.settings.generation,
            self.clock(),
        )

    def _session(self, db, token):
        digest = self.settings.digest("session", token)
        return self._session_reference(db, digest)

    def _session_reference(self, db, digest):
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise StaffError()
        db.execute(
            "SELECT principal_id FROM catalog_staff.sessions WHERE session_digest=%s",
            (digest,),
        )
        row = db.fetchone()
        if not row:
            raise StaffError()
        # Every administrator mutation uses this same principal-first lock order.
        principal = lock_principal(db, row["principal_id"])
        db.execute(
            "SELECT * FROM catalog_staff.sessions WHERE session_digest=%s FOR UPDATE",
            (digest,),
        )
        session = db.fetchone()
        now = self.clock()
        if (
            not session
            or session["revoked_at"] is not None
            or not session["created_at"] <= now < session["expires_at"]
        ):
            raise StaffError()
        if (
            principal["state"] == "suspended"
            or session["enrollment_epoch"] != principal["enrollment_epoch"]
            or str(session["generation"]) != self.settings.generation
        ):
            raise StaffError()
        return principal, session

    def _enrolling(self, principal, session):
        if principal["state"] != "enrolling" or self.clock() - session[
            "created_at"
        ] > timedelta(minutes=5):
            raise StaffError("supervised_enrollment_required", 403)

    @staticmethod
    def _credentials(db, principal):
        db.execute(
            "SELECT * FROM catalog_staff.credentials WHERE principal_id=%s AND active ORDER BY slot",
            (principal,),
        )
        return db.fetchall()

    def _enrolled(self, db, principal):
        credentials = self._credentials(db, principal["principal_id"])
        if (
            principal["state"] != "active"
            or len(credentials) != 2
            or any(c["confirmed_at"] is None for c in credentials)
        ):
            raise StaffError("staff_enrollment_required", 403)
        return credentials

    def begin_enrollment(self, session_token, permit):
        with self.repo.transaction() as db:
            principal, session = self._session(db, session_token)
            self._enrolling(principal, session)
            now = self.clock()
            db.execute(
                """UPDATE catalog_staff.enrollment_permits SET consumed_at=%s
                WHERE permit_digest=%s AND principal_id=%s AND enrollment_epoch=%s
                AND generation=%s AND consumed_at IS NULL AND expires_at>%s RETURNING *""",
                (
                    now,
                    self.settings.digest("permit", permit),
                    principal["principal_id"],
                    principal["enrollment_epoch"],
                    self.settings.generation,
                    now,
                ),
            )
            approval = db.fetchone()
            if not approval:
                raise StaffError("supervised_enrollment_required", 403)
            credentials = self._credentials(db, principal["principal_id"])
            if any(c["slot"] == approval["slot"] for c in credentials):
                raise StaffError("enrollment_slot_occupied", 409)
            identifier, challenge = self._challenge(
                db,
                "enroll",
                session["session_digest"],
                {"permit": approval["permit_digest"], "slot": approval["slot"]},
            )
            options = generate_registration_options(
                rp_id=self.settings.rp_id,
                rp_name="SPACE staff review",
                user_id=UUID(str(principal["principal_id"])).bytes,
                user_name=principal["display_name"],
                challenge=challenge,
                timeout=120000,
                supported_pub_key_algs=[COSEAlgorithmIdentifier.ECDSA_SHA_256],
                authenticator_selection=AuthenticatorSelectionCriteria(
                    user_verification=UserVerificationRequirement.REQUIRED
                ),
                exclude_credentials=[
                    PublicKeyCredentialDescriptor(id=bytes(c["credential_id"]))
                    for c in credentials
                ],
            )
        return {
            "challenge_id": identifier,
            "publicKey": json.loads(options_to_json(options)),
        }

    @staticmethod
    def _proof(value):
        try:
            if not isinstance(value, dict) or len(json.dumps(value).encode()) > 65536:
                raise ValueError()

            def unique(pairs):
                result = {}
                for key, item in pairs:
                    if key in result:
                        raise ValueError()
                    result[key] = item
                return result

            client_data = json.loads(
                unb64(value["response"]["clientDataJSON"]), object_pairs_hook=unique
            )
            if (
                client_data.get("crossOrigin", False) is not False
                or "topOrigin" in client_data
            ):
                raise ValueError()
            return value
        except Exception:
            raise StaffError("invalid_staff_proof") from None

    def _take(self, token, identifier, kind):
        return self.repo.take_challenge(
            identifier,
            kind,
            self.settings.digest("session", token),
            self.settings.generation,
            self.clock(),
        )

    def complete_enrollment(self, session_token, challenge_id, response):
        challenge = self._take(session_token, challenge_id, "enroll")
        proof = self._proof(response)
        try:
            result = verify_registration_response(
                credential=proof,
                expected_challenge=unb64(challenge["payload"]["nonce"]),
                expected_rp_id=self.settings.rp_id,
                expected_origin=self.settings.origin,
                require_user_verification=True,
                require_user_presence=True,
                supported_pub_key_algs=[COSEAlgorithmIdentifier.ECDSA_SHA_256],
            )
            if (
                result.credential_device_type != CredentialDeviceType.SINGLE_DEVICE
                or not 16 <= len(result.credential_id) <= 1024
            ):
                raise ValueError()
            canonical_key = decoded_public_key_to_cryptography(
                decode_credential_public_key(result.credential_public_key)
            ).public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        except Exception:
            raise StaffError("invalid_staff_proof") from None
        with self.repo.transaction() as db:
            principal, session = self._session(db, session_token)
            self._enrolling(principal, session)
            db.execute(
                """SELECT * FROM catalog_staff.enrollment_permits WHERE permit_digest=%s
                AND principal_id=%s AND enrollment_epoch=%s AND generation=%s AND expires_at>%s""",
                (
                    challenge["payload"]["permit"],
                    principal["principal_id"],
                    principal["enrollment_epoch"],
                    self.settings.generation,
                    self.clock(),
                ),
            )
            permit = db.fetchone()
            if not permit or challenge["expires_at"] <= self.clock():
                raise StaffError("supervised_enrollment_required", 403)
            db.execute(
                """INSERT INTO catalog_staff.credentials
                (credential_id,principal_id,slot,public_key,public_key_digest,sign_count,permit_digest)
                VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING credential_id""",
                (
                    result.credential_id,
                    principal["principal_id"],
                    permit["slot"],
                    result.credential_public_key,
                    hashlib.sha256(canonical_key).hexdigest(),
                    result.sign_count,
                    permit["permit_digest"],
                ),
            )
            if not db.fetchone():
                raise StaffError("credential_already_registered", 409)
            audit(db, principal["principal_id"], "credential_registered", self.clock())
        # Registration (including attestation='none') is NOT a possession proof.
        # A signed assertion must confirm each credential before activation.
        return {
            "credential_id": b64(result.credential_id),
            "confirmation_required": True,
        }

    def begin_uv(self, session_token, *, confirm_credential=None):
        with self.repo.transaction() as db:
            principal, session = self._session(db, session_token)
            if confirm_credential is not None:
                self._enrolling(principal, session)
                credential_id = unb64(confirm_credential)
                credentials = [
                    c
                    for c in self._credentials(db, principal["principal_id"])
                    if bytes(c["credential_id"]) == credential_id
                    and c["confirmed_at"] is None
                ]
                if len(credentials) != 1:
                    raise StaffError("invalid_staff_proof")
                kind = "confirm"
            else:
                credentials = self._enrolled(db, principal)
                kind = "authenticate"
            identifier, challenge = self._challenge(
                db,
                kind,
                session["session_digest"],
                {
                    "credential_ids": [
                        b64(bytes(c["credential_id"])) for c in credentials
                    ]
                },
            )
            options = generate_authentication_options(
                rp_id=self.settings.rp_id,
                challenge=challenge,
                timeout=120000,
                allow_credentials=[
                    PublicKeyCredentialDescriptor(id=bytes(c["credential_id"]))
                    for c in credentials
                ],
                user_verification=UserVerificationRequirement.REQUIRED,
            )
        return {
            "challenge_id": identifier,
            "publicKey": json.loads(options_to_json(options)),
        }

    def complete_uv(self, session_token, challenge_id, response, *, confirmation=False):
        kind = "confirm" if confirmation else "authenticate"
        challenge = self._take(session_token, challenge_id, kind)
        proof = self._proof(response)
        with self.repo.transaction() as db:
            principal, session = self._session(db, session_token)
            if confirmation:
                self._enrolling(principal, session)
            else:
                self._enrolled(db, principal)
            try:
                credential_id = unb64(proof["id"])
                if b64(credential_id) not in challenge["payload"]["credential_ids"]:
                    raise ValueError()
                handle = proof["response"].get("userHandle")
                if (
                    handle is not None
                    and unb64(handle) != UUID(str(principal["principal_id"])).bytes
                ):
                    raise ValueError()
                credentials = self._credentials(db, principal["principal_id"])
                credential = next(
                    c for c in credentials if bytes(c["credential_id"]) == credential_id
                )
                if not confirmation and credential["confirmed_at"] is None:
                    raise ValueError()
                result = verify_authentication_response(
                    credential=proof,
                    expected_challenge=unb64(challenge["payload"]["nonce"]),
                    expected_rp_id=self.settings.rp_id,
                    expected_origin=self.settings.origin,
                    credential_public_key=bytes(credential["public_key"]),
                    credential_current_sign_count=credential["sign_count"],
                    require_user_verification=True,
                )
                if result.credential_device_type != CredentialDeviceType.SINGLE_DEVICE:
                    raise ValueError()
            except Exception:
                raise StaffError("invalid_staff_proof") from None
            now = self.clock()
            if challenge["expires_at"] <= now or session["expires_at"] <= now:
                raise StaffError("staff_challenge_invalid")
            db.execute(
                "UPDATE catalog_staff.credentials SET sign_count=%s WHERE credential_id=%s",
                (result.new_sign_count, credential_id),
            )
            if confirmation:
                db.execute(
                    "UPDATE catalog_staff.credentials SET confirmed_at=%s WHERE credential_id=%s AND confirmed_at IS NULL",
                    (now, credential_id),
                )
                credentials = self._credentials(db, principal["principal_id"])
                if len(credentials) == 2 and all(
                    c["confirmed_at"] is not None for c in credentials
                ):
                    db.execute(
                        "UPDATE catalog_staff.principals SET state='active' WHERE principal_id=%s AND state='enrolling'",
                        (principal["principal_id"],),
                    )
                    audit(db, principal["principal_id"], "enrollment_completed", now)
                audit(db, principal["principal_id"], "credential_confirmed", now)
            else:
                # Conservative freshness: a held assertion cannot extend the
                # five-minute window beyond its server-issued challenge.
                uv_at = challenge["created_at"]
                db.execute(
                    "UPDATE catalog_staff.sessions SET uv_at=%s,uv_credential_id=%s WHERE session_digest=%s",
                    (uv_at, credential_id, session["session_digest"]),
                )
                audit(db, principal["principal_id"], "uv_verified", now)
        return (
            {"confirmed": True}
            if confirmation
            else {"uv_expires_at": uv_at + timedelta(minutes=5)}
        )

    @contextmanager
    def authorized(self, session_token, workspace):
        """Hold this context THROUGH the protected operation; never cache its result.

        Lock ordering for integration: staff principal/session, then core workspace.
        This is an authorization hook, not a substitute for core tenant isolation.
        """
        with self.repo.transaction() as db:
            yield self.authorize_in_transaction(db, session_token, workspace)

    @staticmethod
    def _identity(principal, session, workspace=None):
        return StaffIdentity(
            str(principal["principal_id"]),
            principal["display_name"],
            principal["issuer"],
            principal["subject"],
            workspace,
            session["uv_at"],
            principal["role"],
            principal["state"],
            session["session_digest"],
            session["expires_at"],
        )

    @contextmanager
    def require_session(self, session_token):
        """OIDC-only session details for enrollment/status, NOT reviewer authority."""
        with self.repo.transaction() as db:
            principal, session = self._session(db, session_token)
            yield self._identity(principal, session)

    def _fresh_uv(self, db, principal, session):
        credentials = self._enrolled(db, principal)
        if (
            session["uv_at"] is None
            or not timedelta(0)
            <= self.clock() - session["uv_at"]
            <= timedelta(minutes=5)
            or not any(
                bytes(c["credential_id"]) == bytes(session["uv_credential_id"])
                for c in credentials
            )
        ):
            raise StaffError("fresh_staff_uv_required", 403)

    def _assigned(self, db, principal, session, workspace):
        workspace = str(UUID(str(workspace)))
        self._fresh_uv(db, principal, session)
        db.execute(
            "SELECT 1 FROM catalog_staff.assignments WHERE principal_id=%s AND workspace_id=%s AND active",
            (principal["principal_id"], workspace),
        )
        if not db.fetchone():
            raise StaffError("staff_assignment_required", 403)
        return self._identity(principal, session, workspace)

    def authorize_in_transaction(self, cur, session_token, workspace):
        """Call before the core workspace lock; all locks live until caller commit."""
        principal, session = self._session(cur, session_token)
        return self._assigned(cur, principal, session, workspace)

    def validate_session_reference(
        self, cur, staff_session_ref, *, principal_id, workspace_id
    ):
        """Server-only hook for a trusted core staff_session_links record.

        A reference is not a browser credential. Never accept it as a login token.
        Verify the core cookie/link first, then call inside that SAME transaction.
        """
        principal, session = self._session_reference(cur, staff_session_ref)
        if str(principal["principal_id"]) != str(UUID(str(principal_id))):
            raise StaffError()
        return self._assigned(cur, principal, session, workspace_id)

    def authorize_reviewer_digest_in_transaction(
        self, db, staff_session_digest, workspace
    ):
        """Core link preflight: no nested transaction and no raw staff token.

        Caller MUST compare returned principal_id with the current core membership
        after acquiring the workspace lock. The reference comes from a server-owned
        staff_session_links row, never directly from a client request.
        """
        principal, session = self._session_reference(db, staff_session_digest)
        return self._assigned(db, principal, session, workspace)

    def authorize_operator_in_transaction(self, cur, session_token, action):
        if action not in ("intake_list", "intake_approve"):
            raise StaffError("staff_operator_action_denied", 403)
        principal, session = self._session(cur, session_token)
        self._fresh_uv(cur, principal, session)
        if principal["role"] != "operator":
            raise StaffError("staff_operator_required", 403)
        return self._identity(principal, session)

    @contextmanager
    def require_operator(self, session_token, action="intake_list"):
        with self.repo.transaction() as db:
            yield self.authorize_operator_in_transaction(db, session_token, action)

    def csrf(self, session_token):
        return self.settings.digest("csrf", session_token)

    def list_workspaces(self, session_token, *, workspace_guard=None):
        """Assigned IDs only; core guard must check journal and current case row.

        Guard(db, workspace_id) returns strictly True (visible) or False (deleted,
        unavailable case). Exceptions/invalid values fail the entire operation.
        Principal/session are locked before any guard's core workspace locks.
        """
        with self.repo.transaction() as db:
            principal, session = self._session(db, session_token)
            self._fresh_uv(db, principal, session)
            if not callable(workspace_guard):
                raise StaffError("staff_workspace_list_unavailable", 503)
            db.execute(
                """SELECT workspace_id FROM catalog_staff.assignments
                WHERE principal_id=%s AND active ORDER BY workspace_id LIMIT 1001""",
                (principal["principal_id"],),
            )
            assignments = db.fetchall()
            if len(assignments) > 1000:
                raise StaffError("staff_workspace_list_unavailable", 503)
            visible = []
            for row in assignments:
                workspace = str(row["workspace_id"])
                allowed = workspace_guard(db, workspace)
                if type(allowed) is not bool:
                    raise StaffError("staff_workspace_list_unavailable", 503)
                if allowed:
                    visible.append(workspace)
            return {"workspace_ids": visible}

    def logout(self, session_token):
        with self.repo.transaction() as db:
            principal, session = self._session(db, session_token)
            db.execute(
                "UPDATE catalog_staff.sessions SET revoked_at=%s WHERE session_digest=%s",
                (self.clock(), session["session_digest"]),
            )
            audit(db, principal["principal_id"], "session_revoked", self.clock())
