import hashlib
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import cbor2
import httpx
import jwt
import psycopg2
import pytest
from conftest import Clock
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient
from psycopg2 import sql

from services.catalog_review.staff import (
    GoogleOIDCTransport,
    GoogleOIDCVerifier,
    JwksSnapshot,
    StaffAdministration,
    StaffErasureParticipant,
    StaffError,
    StaffRepository,
    StaffService,
    StaffSettings,
)
from services.catalog_review.staff.config import GOOGLE_ISSUER, b64, unb64
from services.catalog_review.staff.grants import erasure_grants_sql, runtime_grants_sql
from services.catalog_review.staff.http import (
    OIDC_COOKIE,
    SESSION_COOKIE,
    create_staff_router,
)
from services.catalog_review.staff.repository import transaction
from services.catalog_review.staff.transport import JWKS_ENDPOINT, TOKEN_ENDPOINT


class Authenticator:
    """Synthetic authenticator emitting real CBOR/ES256 proofs, never an MFA bool."""

    def __init__(self, key=None):
        self.key = key or ec.generate_private_key(ec.SECP256R1())
        self.identifier = secrets.token_bytes(32)
        self.count = 0

    def client(self, options, origin, kind, **changes):
        data = {
            "type": kind,
            "challenge": options["publicKey"]["challenge"],
            "origin": origin,
            "crossOrigin": False,
            **changes,
        }
        return json.dumps(data, separators=(",", ":")).encode()

    def registration(
        self,
        options,
        settings,
        *,
        flags=0x45,
        origin=None,
        rp_id=None,
        **client_changes,
    ):
        numbers = self.key.public_key().public_numbers()
        cose = cbor2.dumps(
            {1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32), -3: numbers.y.to_bytes(32)}
        )
        data = (
            hashlib.sha256((rp_id or settings.rp_id).encode()).digest()
            + bytes([flags])
            + self.count.to_bytes(4)
        )
        data += bytes(16) + len(self.identifier).to_bytes(2) + self.identifier + cose
        client = self.client(
            options, origin or settings.origin, "webauthn.create", **client_changes
        )
        return {
            "id": b64(self.identifier),
            "rawId": b64(self.identifier),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client),
                "attestationObject": b64(
                    cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": data})
                ),
            },
        }

    def assertion(
        self,
        options,
        settings,
        *,
        principal=None,
        flags=0x05,
        origin=None,
        rp_id=None,
        count=None,
        **client_changes,
    ):
        self.count = self.count + 1 if count is None else count
        data = (
            hashlib.sha256((rp_id or settings.rp_id).encode()).digest()
            + bytes([flags])
            + self.count.to_bytes(4)
        )
        client = self.client(
            options, origin or settings.origin, "webauthn.get", **client_changes
        )
        signature = self.key.sign(
            data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256())
        )
        return {
            "id": b64(self.identifier),
            "rawId": b64(self.identifier),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client),
                "authenticatorData": b64(data),
                "signature": b64(signature),
                "userHandle": b64(UUID(principal).bytes) if principal else None,
            },
        }


@pytest.fixture(scope="session")
def staff_cluster(cluster):
    with transaction(cluster) as db:
        db.execute(
            "CREATE ROLE catalog_staff_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB"
        )
    return cluster


@pytest.fixture(scope="session")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def staff(staff_cluster, signing_key):
    name = "staff_" + uuid4().hex
    with closing(psycopg2.connect(staff_cluster)) as connection:
        connection.autocommit = True
        with connection.cursor() as db:
            db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        owner_dsn = staff_cluster.replace("dbname=postgres", "dbname=" + name)
        runtime_dsn = owner_dsn.replace(
            "user=review_migration", "user=catalog_staff_runtime"
        )
        with transaction(owner_dsn) as db:
            for file in ("schema.sql", "grants.sql"):
                db.execute((Path("services/catalog_review/staff") / file).read_text())
        clock = Clock()
        settings = StaffSettings(
            "synthetic-client.apps.googleusercontent.com",
            "https://review.test",
            "review.test",
            str(uuid4()),
            secrets.token_bytes(32),
        )
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
        jwk.update(kid="synthetic-google-key", alg="RS256", use="sig")
        snapshot = JwksSnapshot((jwk,), clock(), clock() + timedelta(hours=2))
        verifier = GoogleOIDCVerifier(settings.client_id, lambda: snapshot, clock)
        code_tokens = {}

        def exchange(**kwargs):
            token, expected_pkce = code_tokens.pop(kwargs["code"])
            assert kwargs["redirect_uri"] == settings.redirect_uri
            assert (
                b64(hashlib.sha256(kwargs["code_verifier"].encode()).digest())
                == expected_pkce
            )
            return token

        repo = StaffRepository(runtime_dsn)
        service = StaffService(
            repo, settings, oidc_verifier=verifier, exchange_code=exchange, clock=clock
        )
        admin = StaffAdministration(owner_dsn, settings, clock)
        principal = admin.preapprove(
            issuer=GOOGLE_ISSUER,
            subject="preapproved-google-subject",
            display_name="Synthetic Reviewer",
            supervision_reference="supervised-staff-approval-1",
        )
        harness = SimpleNamespace(
            service=service,
            admin=admin,
            repo=repo,
            clock=clock,
            settings=settings,
            owner_dsn=owner_dsn,
            runtime_dsn=runtime_dsn,
            principal=principal,
            codes=code_tokens,
            signing_key=signing_key,
            verifier=verifier,
            snapshot=snapshot,
        )
        try:
            yield harness
        finally:
            with connection.cursor() as db:
                db.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def prepare_oidc(staff, changes=None, *, key=None, headers=None):
    start = staff.service.begin_oidc()
    query = parse_qs(urlsplit(start["authorization_url"]).query)
    claims = {
        "iss": GOOGLE_ISSUER,
        "sub": "preapproved-google-subject",
        "aud": staff.settings.client_id,
        "iat": int(staff.clock().timestamp()),
        "exp": int(staff.clock().timestamp()) + 3600,
        "nonce": query["nonce"][0],
        "email": "staff-fixture@spacemusic.io",
        "email_verified": True,
        "hd": "spacemusic.io",
        **(changes or {}),
    }
    claims = {k: v for k, v in claims.items() if v is not None}
    token = jwt.encode(
        claims,
        key or staff.signing_key,
        algorithm="RS256",
        headers={"kid": "synthetic-google-key", **(headers or {})},
    )
    code = secrets.token_urlsafe(32)
    staff.codes[code] = (token, query["code_challenge"][0])
    return start, code, token


def login(staff, **changes):
    start, code, _ = prepare_oidc(staff, changes)
    return staff.service.complete_oidc(
        state=start["state"], browser_binding=start["browser_binding"], code=code
    )


def register(staff, token, slot, authenticator=None):
    authenticator = authenticator or Authenticator()
    permit = staff.admin.approve_enrollment(
        staff.principal, slot, supervision_reference="supervised-" + slot
    )
    options = staff.service.begin_enrollment(token, permit)
    result = staff.service.complete_enrollment(
        token,
        options["challenge_id"],
        authenticator.registration(options, staff.settings),
    )
    return authenticator, result


def confirm(staff, token, authenticator):
    options = staff.service.begin_uv(
        token, confirm_credential=b64(authenticator.identifier)
    )
    response = authenticator.assertion(
        options, staff.settings, principal=staff.principal
    )
    staff.service.complete_uv(
        token, options["challenge_id"], response, confirmation=True
    )


def enrolled(staff):
    token = login(staff)
    keys = []
    for slot in ("primary", "backup"):
        authenticator, _ = register(staff, token, slot)
        confirm(staff, token, authenticator)
        keys.append(authenticator)
    return token, keys


def step_up(staff, token, authenticator):
    options = staff.service.begin_uv(token)
    return staff.service.complete_uv(
        token,
        options["challenge_id"],
        authenticator.assertion(options, staff.settings, principal=staff.principal),
    )


def assigned(staff):
    token, keys = enrolled(staff)
    workspace = str(uuid4())
    staff.admin.assign(
        staff.principal,
        workspace,
        active=True,
        supervision_reference="case-assignment-1",
    )
    step_up(staff, token, keys[0])
    return token, keys, workspace


def test_default_closed_and_exact_environment(staff):
    with pytest.raises(ValueError):
        StaffSettings().validate()
    for changes in (
        {"origin": "http://review.test"},
        {"rp_id": "spacemusic.io"},
        {"origin": "https://review.test:443"},
        {"digest_key": b""},
    ):
        with pytest.raises(ValueError):
            replace(staff.settings, **changes).validate()
    with pytest.raises(StaffError, match="unavailable"):
        StaffService(staff.repo, staff.settings).begin_oidc()
    with pytest.raises(StaffError, match="unavailable"):
        GoogleOIDCVerifier(staff.settings.client_id).verify(
            "anything", nonce="n", started_at=staff.clock()
        )


@pytest.mark.parametrize(
    "change",
    [
        {"iss": "https://attacker.test"},
        {"iss": None},
        {"sub": None},
        {"sub": 123},
        {"aud": "other-client"},
        {"aud": ["synthetic-client.apps.googleusercontent.com", "other"]},
        {"azp": "other-client"},
        {"nonce": "wrong"},
        {"nonce": None},
        {"exp": 1},
        {"exp": None},
        {"exp": True},
        {"iat": None},
        {"iat": True},
        {"iat": 9999999999},
        {"nbf": 9999999999},
        {"email": None},
        {"email_verified": False},
        {"email_verified": None},
        {"email_verified": "true"},
        {"hd": None},
        {"hd": "other.example"},
    ],
)
def test_oidc_rejects_signed_bad_claims(staff, change):
    start, code, _ = prepare_oidc(staff, change)
    with pytest.raises(StaffError, match="invalid_google_identity"):
        staff.service.complete_oidc(
            state=start["state"], browser_binding=start["browser_binding"], code=code
        )
    with pytest.raises(StaffError, match="challenge_invalid"):
        staff.service.complete_oidc(
            state=start["state"], browser_binding=start["browser_binding"], code=code
        )


@pytest.mark.parametrize(
    "header",
    [
        {"kid": "unknown"},
        {"jku": "https://attacker.test/keys"},
        {"jwk": {}},
        {"crit": ["x"]},
    ],
)
def test_oidc_untrusted_key_headers(staff, header):
    start, code, _ = prepare_oidc(staff, headers=header)
    with pytest.raises(StaffError):
        staff.service.complete_oidc(
            state=start["state"], browser_binding=start["browser_binding"], code=code
        )


def test_oidc_wrong_signature_and_stale_jwks(staff):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    start, code, _ = prepare_oidc(staff, key=key)
    with pytest.raises(StaffError):
        staff.service.complete_oidc(
            state=start["state"], browser_binding=start["browser_binding"], code=code
        )
    start, code, _ = prepare_oidc(staff)
    staff.verifier.key_provider = lambda: replace(
        staff.snapshot, expires_at=staff.clock()
    )
    with pytest.raises(StaffError):
        staff.service.complete_oidc(
            state=start["state"], browser_binding=start["browser_binding"], code=code
        )


def test_oidc_email_domain_and_amr_do_not_autoprovision(staff):
    with pytest.raises(StaffError):
        login(
            staff,
            sub="not-preapproved",
            email="admin@spacemusic.io",
            email_verified=True,
            hd="spacemusic.io",
            amr=["mfa"],
            acr="high",
        )
    token = login(staff, email="changed-address@example.com", amr=["mfa"])
    with pytest.raises(StaffError, match="enrollment_required"):
        with staff.service.authorized(token, str(uuid4())):
            pytest.fail("OIDC and Google amr must not grant staff access")


def test_oidc_browser_binding_expiry_and_state_replay(staff):
    start, code, _ = prepare_oidc(staff)
    with pytest.raises(StaffError, match="challenge_invalid"):
        staff.service.complete_oidc(
            state=start["state"], browser_binding=secrets.token_urlsafe(32), code=code
        )
    staff.service.complete_oidc(
        state=start["state"], browser_binding=start["browser_binding"], code=code
    )
    with pytest.raises(StaffError, match="challenge_invalid"):
        staff.service.complete_oidc(
            state=start["state"], browser_binding=start["browser_binding"], code=code
        )
    start, code, _ = prepare_oidc(staff)
    staff.clock.advance(300)
    with pytest.raises(StaffError, match="challenge_invalid"):
        staff.service.complete_oidc(
            state=start["state"], browser_binding=start["browser_binding"], code=code
        )


def test_enrollment_needs_supervision_two_distinct_confirmed_keys(staff):
    token = login(staff)
    with pytest.raises(StaffError, match="supervised_enrollment_required"):
        staff.service.begin_enrollment(token, secrets.token_urlsafe(32))
    primary, _ = register(staff, token, "primary")
    backup, _ = register(staff, token, "backup")
    with pytest.raises(StaffError, match="enrollment_required"):
        staff.service.begin_uv(token)
    confirm(staff, token, primary)
    with pytest.raises(StaffError, match="enrollment_required"):
        staff.service.begin_uv(token)
    confirm(staff, token, backup)
    with pytest.raises(StaffError, match="fresh_staff_uv_required"):
        with staff.service.authorized(token, str(uuid4())):
            pytest.fail("Enrollment is not a fresh session assertion")


def test_same_public_key_cannot_be_primary_and_backup(staff):
    token = login(staff)
    primary, _ = register(staff, token, "primary")
    with pytest.raises(StaffError, match="already_registered"):
        register(staff, token, "backup", Authenticator(primary.key))


def test_permit_is_single_use_and_principal_bound(staff):
    token = login(staff)
    other = staff.admin.preapprove(
        issuer=GOOGLE_ISSUER,
        subject="other",
        display_name="Other",
        supervision_reference="human-2",
    )
    other_permit = staff.admin.approve_enrollment(
        other, "primary", supervision_reference="human-2"
    )
    with pytest.raises(StaffError):
        staff.service.begin_enrollment(token, other_permit)
    permit = staff.admin.approve_enrollment(
        staff.principal, "primary", supervision_reference="human-1"
    )
    staff.service.begin_enrollment(token, permit)
    with pytest.raises(StaffError):
        staff.service.begin_enrollment(token, permit)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"flags": 0x41},
        {"flags": 0x44},
        {"flags": 0x4D},
        {"origin": "https://review-staging.spacemusic.io"},
        {"rp_id": "spacemusic.io"},
        {"crossOrigin": True},
        {"topOrigin": "https://review.test"},
        {"challenge": b64(b"wrong")},
    ],
)
def test_registration_requires_uv_presence_rp_origin_and_binding(staff, kwargs):
    token = login(staff)
    permit = staff.admin.approve_enrollment(
        staff.principal, "primary", supervision_reference="human-1"
    )
    options = staff.service.begin_enrollment(token, permit)
    proof = Authenticator().registration(options, staff.settings, **kwargs)
    with pytest.raises(StaffError, match="invalid_staff_proof"):
        staff.service.complete_enrollment(token, options["challenge_id"], proof)
    with pytest.raises(StaffError, match="challenge_invalid"):
        staff.service.complete_enrollment(token, options["challenge_id"], proof)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"flags": 0x01},
        {"flags": 0x04},
        {"flags": 0x0D},
        {"origin": "https://review-staging.spacemusic.io"},
        {"rp_id": "spacemusic.io"},
        {"crossOrigin": True},
        {"challenge": b64(b"wrong")},
        {"principal": str(uuid4())},
    ],
)
def test_assertion_requires_signed_uv_exact_origin_rp_and_user(staff, kwargs):
    token, keys = enrolled(staff)
    options = staff.service.begin_uv(token)
    proof = keys[0].assertion(options, staff.settings, **kwargs)
    with pytest.raises(StaffError, match="invalid_staff_proof"):
        staff.service.complete_uv(token, options["challenge_id"], proof)


def test_tampered_signature_counter_and_challenge_replay(staff):
    token, keys = enrolled(staff)
    options = staff.service.begin_uv(token)
    proof = keys[0].assertion(options, staff.settings)
    correct = json.loads(json.dumps(proof))
    proof["response"]["signature"] = b64(b"invalid signature")
    with pytest.raises(StaffError):
        staff.service.complete_uv(token, options["challenge_id"], proof)
    with pytest.raises(StaffError, match="challenge_invalid"):
        staff.service.complete_uv(token, options["challenge_id"], correct)
    options = staff.service.begin_uv(token)
    proof = keys[0].assertion(options, staff.settings, count=1)
    with pytest.raises(StaffError):
        staff.service.complete_uv(token, options["challenge_id"], proof)


def test_uv_challenge_single_use_under_concurrency(staff):
    token, keys = enrolled(staff)
    options = staff.service.begin_uv(token)
    proof = keys[0].assertion(options, staff.settings)

    def finish(_):
        try:
            staff.service.complete_uv(token, options["challenge_id"], proof)
            return True
        except StaffError:
            return False

    with ThreadPoolExecutor(max_workers=3) as pool:
        assert sum(pool.map(finish, range(3))) == 1


def test_fresh_uv_assignment_revocation_and_expiry(staff):
    token, keys, workspace = assigned(staff)
    with staff.service.authorized(token, workspace) as identity:
        assert identity.principal_id == staff.principal
        assert identity.display_name == "Synthetic Reviewer"
    with pytest.raises(StaffError, match="assignment_required"):
        with staff.service.authorized(token, str(uuid4())):
            pytest.fail("Foreign case")
    staff.clock.advance(300)
    with staff.service.authorized(token, workspace):
        pass
    staff.clock.advance(1)
    with pytest.raises(StaffError, match="fresh_staff_uv_required"):
        with staff.service.authorized(token, workspace):
            pytest.fail("Stale UV")
    step_up(staff, token, keys[1])
    staff.admin.assign(
        staff.principal, workspace, active=False, supervision_reference="case-revoked"
    )
    with pytest.raises(StaffError, match="assignment_required"):
        with staff.service.authorized(token, workspace):
            pytest.fail("Revoked assignment")


def test_suspend_during_ceremony_and_no_email_recovery(staff):
    token, keys, workspace = assigned(staff)
    options = staff.service.begin_uv(token)
    proof = keys[0].assertion(options, staff.settings)
    staff.admin.suspend(staff.principal, supervision_reference="staff-offboarded")
    for action in (
        lambda: staff.service.complete_uv(token, options["challenge_id"], proof),
        lambda: login(
            staff, email="admin@spacemusic.io", hd="spacemusic.io", amr=["mfa"]
        ),
        lambda: staff.admin.approve_enrollment(
            staff.principal, "primary", supervision_reference="not-a-reset"
        ),
    ):
        with pytest.raises(StaffError):
            action()
    with pytest.raises(StaffError):
        with staff.service.authorized(token, workspace):
            pytest.fail("Suspended staff")


def test_supervised_recovery_invalidates_sessions_keys_permits_and_assignments(staff):
    old_token, old_keys, workspace = assigned(staff)
    staff.admin.reset_enrollment(
        staff.principal, supervision_reference="supervised-reproof-recovery-1"
    )
    with pytest.raises(StaffError):
        with staff.service.authorized(old_token, workspace):
            pytest.fail("Old session after recovery")
    token, keys = enrolled(staff)
    options = staff.service.begin_uv(token)
    with pytest.raises(StaffError):
        staff.service.complete_uv(
            token,
            options["challenge_id"],
            old_keys[0].assertion(options, staff.settings),
        )
    step_up(staff, token, keys[1])
    with pytest.raises(StaffError, match="assignment_required"):
        with staff.service.authorized(token, workspace):
            pytest.fail("Recovery cannot recover an assignment automatically")


def test_logout_new_login_and_restore_generation_invalidate_session(staff):
    token, keys, workspace = assigned(staff)
    changed = StaffService(
        staff.repo, replace(staff.settings, generation=str(uuid4())), clock=staff.clock
    )
    with pytest.raises(StaffError):
        with changed.authorized(token, workspace):
            pytest.fail("Restored session")
    next_token = login(staff)
    with pytest.raises(StaffError):
        with staff.service.authorized(token, workspace):
            pytest.fail("Replaced session")
    step_up(staff, next_token, keys[0])
    staff.service.logout(next_token)
    with pytest.raises(StaffError):
        staff.service.begin_uv(next_token)


@pytest.mark.parametrize(
    "grant",
    [
        "GRANT UPDATE(issuer) ON catalog_staff.principals TO catalog_staff_runtime",
        "GRANT INSERT ON catalog_staff.enrollment_permits TO catalog_staff_runtime",
        "GRANT UPDATE(active) ON catalog_staff.assignments TO catalog_staff_runtime",
        "GRANT UPDATE(action) ON catalog_staff.audit TO catalog_staff_runtime",
        "GRANT TRUNCATE ON catalog_staff.sessions TO catalog_staff_runtime",
    ],
)
def test_runtime_misconfiguration_rejected(staff, grant):
    with transaction(staff.owner_dsn) as db:
        db.execute(grant)
    with pytest.raises(RuntimeError):
        StaffRepository(staff.runtime_dsn)


def test_runtime_cannot_supervise_or_recover(staff):
    runtime_admin = StaffAdministration(staff.runtime_dsn, staff.settings, staff.clock)
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        runtime_admin.approve_enrollment(
            staff.principal, "primary", supervision_reference="forged"
        )
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        runtime_admin.reset_enrollment(staff.principal, supervision_reference="forged")


def test_no_raw_session_token_or_google_jwt_persisted(staff):
    start, code, token = prepare_oidc(staff)
    session = staff.service.complete_oidc(
        state=start["state"], browser_binding=start["browser_binding"], code=code
    )
    with transaction(staff.owner_dsn) as db:
        for table in ("sessions", "principals", "audit", "challenges"):
            db.execute(
                "SELECT row_to_json(t) AS data FROM catalog_staff." + table + " t"
            )
            stored = json.dumps(db.fetchall(), default=str)
            assert (
                token not in stored
                and session not in stored
                and start["browser_binding"] not in stored
            )
    assert staff.settings.digest_key.hex() not in repr(staff.settings)


def test_held_assertion_cannot_extend_five_minute_uv_age(staff):
    token, keys, workspace = assigned(staff)
    options = staff.service.begin_uv(token)
    proof = keys[0].assertion(options, staff.settings)
    issued = staff.clock()
    staff.clock.advance(119)
    result = staff.service.complete_uv(token, options["challenge_id"], proof)
    assert result["uv_expires_at"] == issued + timedelta(minutes=5)
    staff.clock.advance(182)
    with pytest.raises(StaffError, match="fresh_staff_uv_required"):
        with staff.service.authorized(token, workspace):
            pytest.fail("A delayed response extended UV freshness")


def test_same_key_with_different_cbor_encoding_still_rejected(staff):
    token = login(staff)
    primary, _ = register(staff, token, "primary")
    backup = Authenticator(primary.key)
    permit = staff.admin.approve_enrollment(
        staff.principal, "backup", supervision_reference="second-device"
    )
    options = staff.service.begin_enrollment(token, permit)
    proof = backup.registration(options, staff.settings)
    attestation = cbor2.loads(unb64(proof["response"]["attestationObject"]))
    public_key_offset = 37 + 16 + 2 + len(backup.identifier)
    cose = cbor2.loads(attestation["authData"][public_key_offset:])
    attestation["authData"] = attestation["authData"][:public_key_offset] + cbor2.dumps(
        dict(reversed(list(cose.items())))
    )
    proof["response"]["attestationObject"] = b64(cbor2.dumps(attestation))
    with pytest.raises(StaffError, match="already_registered"):
        staff.service.complete_enrollment(token, options["challenge_id"], proof)


def test_digest_hook_current_assignment_principal_and_generation(staff):
    token, _, workspace = assigned(staff)
    with staff.service.require_session(token) as identity:
        reference = identity.session_reference
        assert reference != token and identity.uv_at is not None
    with staff.repo.transaction() as db:
        result = staff.service.authorize_reviewer_digest_in_transaction(
            db, reference, workspace
        )
        assert result.principal_id == staff.principal
        with pytest.raises(StaffError):
            staff.service.validate_session_reference(
                db, reference, principal_id=str(uuid4()), workspace_id=workspace
            )
    staff.admin.suspend(staff.principal, supervision_reference="offboarding")
    with staff.repo.transaction() as db:
        with pytest.raises(StaffError):
            staff.service.authorize_reviewer_digest_in_transaction(
                db, reference, workspace
            )


def test_only_preapproved_operator_can_authorize_intake(staff):
    token, keys, _ = assigned(staff)
    with pytest.raises(StaffError, match="operator_required"):
        with staff.service.require_operator(token):
            pytest.fail("Reviewer cannot become global operator")
    staff.admin.set_role(
        staff.principal, "operator", supervision_reference="explicit-operator-approval"
    )
    with pytest.raises(StaffError):
        with staff.service.require_operator(token):
            pytest.fail("Role change must revoke old session")
    token = login(staff)
    with pytest.raises(StaffError, match="fresh_staff_uv_required"):
        with staff.service.require_operator(token):
            pytest.fail("Operator still needs WebAuthn")
    step_up(staff, token, keys[1])
    with staff.service.require_operator(token) as identity:
        assert identity.role == "operator" and identity.workspace_id is None
    with staff.repo.transaction() as db:
        identity = staff.service.authorize_operator_in_transaction(
            db, token, "intake_approve"
        )
        assert identity.principal_id == staff.principal
        with pytest.raises(StaffError, match="action_denied"):
            staff.service.authorize_operator_in_transaction(
                db, token, "provision_staff"
            )
    staff.clock.advance(301)
    with pytest.raises(StaffError, match="fresh_staff_uv_required"):
        with staff.service.require_operator(token):
            pytest.fail("Stale operator proof")


def test_revocation_serializes_with_same_transaction_operator_action(staff):
    token, keys, _ = assigned(staff)
    staff.admin.set_role(
        staff.principal, "operator", supervision_reference="explicit-operator-approval"
    )
    token = login(staff)
    step_up(staff, token, keys[0])
    from threading import Event

    started, completed = Event(), Event()

    def revoke():
        started.set()
        staff.admin.suspend(staff.principal, supervision_reference="offboarding")
        completed.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with staff.repo.transaction() as db:
            staff.service.authorize_operator_in_transaction(db, token, "intake_approve")
            task = pool.submit(revoke)
            assert started.wait(1)
            assert not completed.wait(0.1)
        task.result(timeout=2)
    with pytest.raises(StaffError):
        with staff.service.require_operator(token):
            pytest.fail("Revocation was not current")


def test_injected_transaction_provider_and_safe_grant_renderer(staff):
    class BoundedProvider:
        calls = 0

        def transaction(self):
            self.calls += 1
            return transaction(staff.runtime_dsn)

    provider = BoundedProvider()
    repo = StaffRepository(database=provider)
    with repo.transaction() as db:
        db.execute("SELECT current_user AS role")
        assert db.fetchone()["role"] == "catalog_staff_runtime"
    assert provider.calls == 2
    with pytest.raises(ValueError):
        StaffRepository(staff.runtime_dsn, database=provider)
    with pytest.raises(ValueError):
        runtime_grants_sql("runtime; DROP SCHEMA public")
    with transaction(staff.owner_dsn) as db:
        statement = runtime_grants_sql("review_runtime").as_string(db)
        assert 'TO "review_runtime"' in statement
        assert "SET ROLE" not in statement and "GRANT ALL" not in statement


def staff_browser(staff, **kwargs):
    app = FastAPI()
    app.include_router(create_staff_router(staff.service, **kwargs))
    return TestClient(app, base_url=staff.settings.origin)


def http_oidc(staff, browser):
    response = browser.post(
        "/api/staff/oidc/start", json={}, headers={"origin": staff.settings.origin}
    )
    assert response.status_code == 200
    assert set(response.json()) == {"authorization_url"}
    query = parse_qs(urlsplit(response.json()["authorization_url"]).query)
    assert query["scope"] == ["openid email"]
    claims = {
        "iss": GOOGLE_ISSUER,
        "sub": "preapproved-google-subject",
        "aud": staff.settings.client_id,
        "iat": int(staff.clock().timestamp()),
        "exp": int(staff.clock().timestamp()) + 3600,
        "nonce": query["nonce"][0],
        "email": "staff-fixture@spacemusic.io",
        "email_verified": True,
        "hd": "spacemusic.io",
    }
    code = secrets.token_urlsafe(32)
    staff.codes[code] = (
        jwt.encode(
            claims,
            staff.signing_key,
            algorithm="RS256",
            headers={"kid": "synthetic-google-key"},
        ),
        query["code_challenge"][0],
    )
    return query["state"][0], code, response


def test_http_oidc_callback_cookie_csrf_and_logout(staff):
    with staff_browser(staff) as browser:
        assert browser.get("/api/staff/oidc/start").status_code == 405
        assert browser.post("/api/staff/oidc/start", json={}).status_code == 403
        state, code, start = http_oidc(staff, browser)
        for flag in ("HttpOnly", "Secure", "SameSite=lax", "Path=/"):
            assert flag in start.headers["set-cookie"]
        assert "Domain=" not in start.headers["set-cookie"]
        response = browser.get(
            "/api/staff/oidc/callback",
            params={
                "state": state,
                "code": code,
                "scope": "openid email",
                "authuser": "0",
            },
            headers={
                "sec-fetch-site": "cross-site",
                "sec-fetch-mode": "navigate",
                "sec-fetch-dest": "document",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303 and response.headers["location"] == "/staff/"
        assert browser.cookies.get(SESSION_COOKIE)
        assert browser.cookies.get(OIDC_COOKIE) is None
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["cache-control"] == "no-store"
        assert code not in response.text and state not in response.text
        session = browser.get("/api/staff/session")
        assert session.status_code == 200 and session.json()["uv_at"] is None
        assert "session_reference" not in session.json()
        headers = {
            "origin": staff.settings.origin,
            "x-csrf-token": session.json()["csrf"],
        }
        assert (
            browser.delete(
                "/api/staff/session", headers={"origin": staff.settings.origin}
            ).status_code
            == 403
        )
        assert browser.delete("/api/staff/session", headers=headers).status_code == 204
        assert browser.get("/api/staff/session").status_code == 401


@pytest.mark.parametrize(
    "extra",
    [
        {"next": "https://evil.test"},
        {"error": "access_denied"},
        {"iss": "https://evil.test"},
    ],
)
def test_http_callback_query_is_narrow_and_not_reflected(staff, extra):
    with staff_browser(staff) as browser:
        state, code, _ = http_oidc(staff, browser)
        response = browser.get(
            "/api/staff/oidc/callback",
            params={"state": state, "code": code, **extra},
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "evil.test" not in response.text and code not in response.text
        assert browser.cookies.get(SESSION_COOKIE) is None


def test_http_cross_browser_duplicate_state_and_cancel(staff):
    with staff_browser(staff) as first, staff_browser(staff) as second:
        state, code, _ = http_oidc(staff, first)
        response = second.get(
            "/api/staff/oidc/callback",
            params={"state": state, "code": code},
            follow_redirects=False,
        )
        assert response.status_code == 401
        response = first.get(
            "/api/staff/oidc/callback",
            params=[("state", state), ("state", state), ("code", code)],
            follow_redirects=False,
        )
        assert response.status_code == 400
        state, code, _ = http_oidc(staff, first)
        binding = first.cookies.get(OIDC_COOKIE)
        response = first.get(
            "/api/staff/oidc/callback",
            params={"state": state, "error": "access_denied"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        with pytest.raises(StaffError, match="challenge_invalid"):
            staff.service.complete_oidc(state=state, browser_binding=binding, code=code)


def test_http_webauthn_proofs_and_atomic_context_hook(staff):
    token = login(staff)
    workspace = str(uuid4())
    calls = []

    def establish(db, identity):
        assert identity.workspace_id == workspace
        assert identity.principal_id == staff.principal
        assert identity.session_reference != token
        # Same cursor/hook has all current checks and locks; no nested transaction.
        checked = staff.service.authorize_reviewer_digest_in_transaction(
            db, identity.session_reference, workspace
        )
        assert checked == identity
        calls.append(identity)
        return Response(status_code=204)

    with staff_browser(staff, establish_context=establish) as browser:
        browser.cookies.set(SESSION_COOKIE, token)
        headers = {
            "origin": staff.settings.origin,
            "x-csrf-token": staff.service.csrf(token),
        }
        keys = []
        for slot in ("primary", "backup"):
            key = Authenticator()
            permit = staff.admin.approve_enrollment(
                staff.principal, slot, supervision_reference="human-" + slot
            )
            options = browser.post(
                "/api/staff/enrollment/options",
                json={"permit": permit},
                headers=headers,
            )
            assert options.status_code == 200
            options = options.json()
            response = browser.post(
                "/api/staff/enrollment/verify",
                json={
                    "challenge_id": options["challenge_id"],
                    "credential": key.registration(options, staff.settings),
                },
                headers=headers,
            )
            assert (
                response.status_code == 200 and response.json()["confirmation_required"]
            )
            options = browser.post(
                "/api/staff/assertion/options",
                json={"confirm_credential": b64(key.identifier)},
                headers=headers,
            ).json()
            response = browser.post(
                "/api/staff/assertion/verify",
                json={
                    "challenge_id": options["challenge_id"],
                    "credential": key.assertion(options, staff.settings),
                    "confirmation": True,
                },
                headers=headers,
            )
            assert response.status_code == 200
            keys.append(key)
        response = browser.post(
            f"/api/staff/workspaces/{workspace}/context", json={}, headers=headers
        )
        assert response.status_code == 403 and not calls
        staff.admin.assign(
            staff.principal,
            workspace,
            active=True,
            supervision_reference="named-assignment",
        )
        options = browser.post(
            "/api/staff/assertion/options", json={}, headers=headers
        ).json()
        response = browser.post(
            "/api/staff/assertion/verify",
            json={
                "challenge_id": options["challenge_id"],
                "credential": keys[1].assertion(options, staff.settings),
            },
            headers=headers,
        )
        assert response.status_code == 200
        response = browser.post(
            f"/api/staff/workspaces/{workspace}/context", json={}, headers=headers
        )
        assert response.status_code == 204 and len(calls) == 1
        staff.admin.assign(
            staff.principal, workspace, active=False, supervision_reference="revoked"
        )
        response = browser.post(
            f"/api/staff/workspaces/{workspace}/context", json={}, headers=headers
        )
        assert response.status_code == 403 and len(calls) == 1


def test_http_bounds_origins_csrf_and_context_default_closed(staff):
    token, _, workspace = assigned(staff)
    with staff_browser(staff) as browser:
        browser.cookies.set(SESSION_COOKIE, token)
        headers = {
            "origin": staff.settings.origin,
            "x-csrf-token": staff.service.csrf(token),
        }
        assert (
            browser.post(
                f"/api/staff/workspaces/{workspace}/context", json={}, headers=headers
            ).status_code
            == 503
        )
        assert browser.get("/api/staff/session?token=private").status_code == 400
        assert (
            browser.get(
                "/api/staff/session", headers={"host": "spacemusic.io"}
            ).status_code
            == 400
        )
        assert browser.get("http://review.test/api/staff/session").status_code == 400
        assert (
            browser.get(
                "/api/staff/session", headers={"sec-fetch-site": "cross-site"}
            ).status_code
            == 403
        )
        assert (
            browser.post(
                "/api/staff/assertion/options",
                json={},
                headers={**headers, "origin": "https://review-staging.spacemusic.io"},
            ).status_code
            == 403
        )
        assert (
            browser.post(
                "/api/staff/assertion/options",
                content="x" * 65537,
                headers={**headers, "content-type": "application/json"},
            ).status_code
            == 413
        )
        assert (
            browser.post(
                "/api/staff/assertion/options", json={"mfa": True}, headers=headers
            ).status_code
            == 422
        )
        assert (
            browser.post(
                "/api/staff/assertion/options",
                content='{"confirm_credential":null,"confirm_credential":null}',
                headers={**headers, "content-type": "application/json"},
            ).status_code
            == 422
        )


def test_google_real_transport_mock_http_and_signed_claims(staff, tmp_path):
    path = tmp_path / "synthetic-google-secret"
    path.write_text("synthetic-independent-google-secret")
    path.chmod(0o600)
    calls = []

    def handler(request):
        calls.append((request.method, str(request.url)))
        if str(request.url) == TOKEN_ENDPOINT:
            fields = parse_qs(request.content.decode())
            token, expected_pkce = staff.codes.pop(fields["code"][0])
            assert fields["client_secret"] == ["synthetic-independent-google-secret"]
            assert fields["redirect_uri"] == [staff.settings.redirect_uri]
            assert (
                b64(hashlib.sha256(fields["code_verifier"][0].encode()).digest())
                == expected_pkce
            )
            return httpx.Response(200, json={"id_token": token})
        assert str(request.url) == JWKS_ENDPOINT
        # Real time advances on a cold network fetch; fetched_at must not look
        # future-dated just because verification began before the GET.
        staff.clock.advance(seconds=2)
        return httpx.Response(
            200,
            json={"keys": list(staff.snapshot.keys)},
            headers={"cache-control": "max-age=3600"},
        )

    transport = GoogleOIDCTransport(
        staff.settings,
        enabled=True,
        client_secret_path=path,
        http_transport=httpx.MockTransport(handler),
        clock=staff.clock,
    )
    staff.service.exchange_code = transport.exchange_code
    staff.service.oidc_verifier = GoogleOIDCVerifier(
        staff.settings.client_id, transport.jwks_snapshot, staff.clock
    )
    try:
        with staff_browser(staff) as browser:
            state, code, _ = http_oidc(staff, browser)
            response = browser.get(
                "/api/staff/oidc/callback",
                params={"state": state, "code": code},
                follow_redirects=False,
            )
            assert (
                response.status_code == 303
                and response.headers["location"] == "/staff/"
            )
            assert (
                browser.get("/api/staff/session").json()["principal_id"]
                == staff.principal
            )
        assert calls == [("POST", TOKEN_ENDPOINT), ("GET", JWKS_ENDPOINT)]
        # Same real transport/cache must not weaken signed workspace admission.
        for changes in ({"email_verified": False}, {"hd": "wrong.test"}, {"hd": None}):
            start, code, _ = prepare_oidc(staff, changes)
            with pytest.raises(StaffError, match="invalid_google_identity"):
                staff.service.complete_oidc(
                    state=start["state"],
                    browser_binding=start["browser_binding"],
                    code=code,
                )
        assert sum(method == "GET" for method, _ in calls) == 1
    finally:
        transport.close()


def test_google_lost_post_ack_consumes_oidc_state_requires_new_login(staff, tmp_path):
    path = tmp_path / "synthetic-google-secret"
    path.write_text("synthetic-independent-google-secret")
    path.chmod(0o600)
    calls = []

    def lost_ack(request):
        calls.append(request)
        raise httpx.ReadTimeout(
            "response lost after Google consumed code", request=request
        )

    transport = GoogleOIDCTransport(
        staff.settings,
        enabled=True,
        client_secret_path=path,
        http_transport=httpx.MockTransport(lost_ack),
        clock=staff.clock,
    )
    start, code, _ = prepare_oidc(staff)
    staff.service.exchange_code = transport.exchange_code
    try:
        kwargs = dict(
            state=start["state"], browser_binding=start["browser_binding"], code=code
        )
        with pytest.raises(StaffError, match="staff_identity_unavailable"):
            staff.service.complete_oidc(**kwargs)
        with pytest.raises(StaffError, match="challenge_invalid"):
            staff.service.complete_oidc(**kwargs)
        assert len(calls) == 1
        with transaction(staff.owner_dsn) as db:
            db.execute("SELECT count(*) AS n FROM catalog_staff.sessions")
            assert db.fetchone()["n"] == 0
    finally:
        transport.close()


def test_http_assigned_workspaces_reviewer_ids_only_and_deleted_filter(staff):
    token, _, workspace = assigned(staff)
    deleted, inactive, foreign = (str(uuid4()) for _ in range(3))
    staff.admin.assign(
        staff.principal, deleted, active=True, supervision_reference="deleted-case"
    )
    staff.admin.assign(
        staff.principal, inactive, active=False, supervision_reference="revoked-case"
    )
    another = staff.admin.preapprove(
        issuer=GOOGLE_ISSUER,
        subject="another-subject",
        display_name="Other reviewer",
        supervision_reference="supervised-other",
    )
    with transaction(staff.owner_dsn) as db:
        db.execute(
            "INSERT INTO catalog_staff.assignments(principal_id,workspace_id,active) VALUES(%s,%s,true)",
            (another, foreign),
        )
    calls = []

    def guard(db, candidate):
        assert candidate in (workspace, deleted)
        db.execute("SELECT current_user AS role")
        assert db.fetchone()["role"] == "catalog_staff_runtime"
        calls.append(candidate)
        return candidate != deleted

    with staff_browser(staff, workspace_guard=guard) as browser:
        browser.cookies.set(SESSION_COOKIE, token)
        response = browser.get("/api/staff/workspaces")
        assert response.status_code == 200 and response.json() == {
            "workspace_ids": [workspace]
        }
        assert response.headers["cache-control"] == "no-store"
        assert set(calls) == {workspace, deleted}
        calls.clear()
        staff.admin.assign(
            staff.principal, workspace, active=False, supervision_reference="revoked"
        )
        assert browser.get("/api/staff/workspaces").json() == {"workspace_ids": []}
        assert calls == [deleted]


@pytest.mark.parametrize("guard_result", [None, "raise", "truthy"])
def test_http_workspace_list_missing_or_broken_guard_fails_closed(staff, guard_result):
    token, _, _ = assigned(staff)

    def guard(db, workspace):
        if guard_result == "raise":
            raise RuntimeError("journal unavailable, no partial list")
        return 1

    with staff_browser(
        staff, workspace_guard=None if guard_result is None else guard
    ) as browser:
        browser.cookies.set(SESSION_COOKIE, token)
        response = browser.get("/api/staff/workspaces")
        assert response.status_code == 503 and "workspace_ids" not in response.json()


def test_http_workspace_list_requires_current_enrollment_session_and_uv(staff):
    token, keys = enrolled(staff)
    calls = []

    def guard(db, workspace):
        calls.append(workspace)
        return True

    with staff_browser(staff, workspace_guard=guard) as browser:
        assert browser.get("/api/staff/workspaces").status_code == 401
        browser.cookies.set(SESSION_COOKIE, token)
        assert browser.get("/api/staff/workspaces").status_code == 403
        step_up(staff, token, keys[0])
        assert browser.get("/api/staff/workspaces").json() == {"workspace_ids": []}
        staff.clock.advance(seconds=301)
        assert browser.get("/api/staff/workspaces").status_code == 403
        staff.admin.suspend(staff.principal, supervision_reference="offboarded")
        assert browser.get("/api/staff/workspaces").status_code == 401
        assert not calls


def test_staff_erasure_scoped_idempotent_transaction_and_separate_grants(staff):
    _, _, workspace = assigned(staff)
    other_workspace = str(uuid4())
    staff.admin.assign(
        staff.principal,
        other_workspace,
        active=True,
        supervision_reference="other-case",
    )
    participant = StaffErasureParticipant()
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with staff.repo.transaction() as db:
            participant.erase_in_transaction(db, workspace)
    with pytest.raises(RuntimeError):
        with transaction(staff.owner_dsn) as db:
            participant.erase_in_transaction(db, workspace)
            raise RuntimeError("caller rollback")
    role = "staff_erasure_" + uuid4().hex
    with transaction(staff.owner_dsn) as db:
        db.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB"
            ).format(sql.Identifier(role))
        )
        db.execute(erasure_grants_sql(role))
        db.execute(
            "SELECT workspace_id FROM catalog_staff.assignments ORDER BY workspace_id"
        )
        assert {str(row["workspace_id"]) for row in db.fetchall()} == {
            workspace,
            other_workspace,
        }
    erasure_dsn = staff.runtime_dsn.replace("catalog_staff_runtime", role)
    with transaction(erasure_dsn) as db:
        participant.erase_in_transaction(db, workspace)
        participant.erase_in_transaction(db, workspace)
        db.execute("SELECT workspace_id FROM catalog_staff.assignments")
        assert [str(row["workspace_id"]) for row in db.fetchall()] == [other_workspace]
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with transaction(erasure_dsn) as db:
            db.execute("DELETE FROM catalog_staff.principals")
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with transaction(erasure_dsn) as db:
            db.execute("UPDATE catalog_staff.assignments SET active=false")
    with transaction(staff.owner_dsn) as db:
        db.execute("SELECT count(*) AS n FROM catalog_staff.principals")
        assert db.fetchone()["n"] == 1
