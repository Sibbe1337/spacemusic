"""Core and staff share a real database, with real signed synthetic passkey proofs."""

import hashlib
import json
import secrets
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from conftest import owner_cursor, sign_in
from cryptography.hazmat.primitives.asymmetric import rsa
from test_staff_identity import enrolled, step_up

from services.catalog_review.encryption import EnvelopeCipher, EnvelopeUnavailable
from services.catalog_review.staff import (
    GoogleOIDCVerifier,
    JwksSnapshot,
    StaffAdministration,
    StaffRepository,
    StaffService,
    StaffSettings,
)
from services.catalog_review.staff.config import GOOGLE_ISSUER, StaffError, b64


@pytest.fixture
def connected_staff(backend):
    with owner_cursor(backend) as db:
        db.execute(Path("services/catalog_review/staff/schema.sql").read_text())
        db.execute(
            Path("services/catalog_review/staff/grants.sql")
            .read_text()
            .replace("catalog_staff_runtime", "review_runtime")
        )
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = StaffSettings(
        "synthetic.apps.googleusercontent.com",
        "https://review.test",
        "review.test",
        str(uuid4()),
        secrets.token_bytes(32),
    )
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="synthetic-google-key", alg="RS256", use="sig")
    snapshot = JwksSnapshot(
        (jwk,), backend.clock(), backend.clock() + timedelta(hours=2)
    )
    verifier = GoogleOIDCVerifier(settings.client_id, lambda: snapshot, backend.clock)
    codes = {}

    def exchange(**kwargs):
        token, expected = codes.pop(kwargs["code"])
        assert (
            b64(hashlib.sha256(kwargs["code_verifier"].encode()).digest()) == expected
        )
        return token

    service = StaffService(
        StaffRepository(backend.test_runtime_dsn),
        settings,
        oidc_verifier=verifier,
        exchange_code=exchange,
        clock=backend.clock,
    )
    admin = StaffAdministration(backend.test_owner_dsn, settings, backend.clock)
    principal = admin.preapprove(
        issuer=GOOGLE_ISSUER,
        subject="preapproved-google-subject",
        display_name="Synthetic operator",
        supervision_reference="independent-test",
    )
    backend.staff_authorizer = service.authorize_reviewer_digest_in_transaction
    return SimpleNamespace(
        service=service,
        settings=settings,
        admin=admin,
        principal=principal,
        clock=backend.clock,
        codes=codes,
        signing_key=key,
    )


def test_real_staff_logout_revokes_linked_portal_context(backend, connected_staff):
    staff = connected_staff
    workspace, owner, _ = sign_in(backend)
    session, keys = enrolled(staff)
    staff.admin.assign(
        staff.principal, workspace, active=True, supervision_reference="assigned-test"
    )
    step_up(staff, session, keys[0])
    with backend.db.transaction() as db:
        identity = staff.service.authorize_in_transaction(db, session, workspace)
        portal = backend.establish_reviewer_context(db, identity)
    assert backend.view(portal)["role"] == "reviewer"
    staff.service.logout(session)
    with pytest.raises(StaffError):
        backend.view(portal)
    assert backend.view(owner)["role"] == "owner"


def test_assignment_revocation_blocks_current_context(backend, connected_staff):
    staff = connected_staff
    workspace, _, _ = sign_in(backend)
    session, keys = enrolled(staff)
    step_up(staff, session, keys[0])
    staff.admin.assign(
        staff.principal, workspace, active=True, supervision_reference="assigned-test"
    )
    with backend.db.transaction() as db:
        portal = backend.establish_reviewer_context(
            db, staff.service.authorize_in_transaction(db, session, workspace)
        )
    staff.admin.assign(
        staff.principal, workspace, active=False, supervision_reference="revoked-test"
    )
    with pytest.raises(StaffError):
        backend.view(portal)


def test_intake_envelope_rotation_binding_and_tampering():
    first, second = secrets.token_bytes(32), secrets.token_bytes(32)
    original = EnvelopeCipher({"one": first}, "one").seal(
        b'{"email":"synthetic@example.com"}', aad=b"intake-1"
    )
    rotated = EnvelopeCipher({"one": first, "two": second}, "two")
    assert rotated.open(original, aad=b"intake-1").startswith(b'{"email"')
    updated = rotated.rewrap(original, aad=b"intake-1")
    assert EnvelopeCipher({"two": second}, "two").open(updated, aad=b"intake-1")
    for value, binding in (
        (original, b"intake-2"),
        (original[:-4] + b"oops", b"intake-1"),
    ):
        with pytest.raises(EnvelopeUnavailable):
            rotated.open(value, aad=binding)
