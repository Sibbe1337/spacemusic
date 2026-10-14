# Isolated staff identity

Cryptographic verification, a PostgreSQL repository and an opt-in Google HTTP
transport. No credentials, Google account access, public endpoint or implicit
identity provider is configured. No changes to core/security/http or core schemas.

## Dependencies and database

- Python >=3.10 (tested with 3.12.10). `requirements.txt` pins PyJWT 2.14.0,
  webauthn 2.8.0, cryptography 50.0.1, psycopg2-binary 2.9.13, FastAPI 0.141.1
  Starlette 1.6.0 and httpx 0.27.2. Merge these into the operations image's reviewed lockfile;
  the existing Python 3.9 environment cannot run this tranche.
- Local test interpreter: `/tmp/space-catalog-staff-venv/bin/python`.
  Runtime requirements retain httpx 0.27.2 for the existing core tests'
  `AsyncClient(app=...)` calls. Staff tests use real disposable PostgreSQL and
  synthetic RSA/ES256 keys and HTTPX MockTransport, never real accounts or provider calls.
- Apply `schema.sql` separately as migration owner to the SAME database as core
  when using the same-transaction hooks. It creates only `catalog_staff` objects.
  Create `catalog_staff_runtime` with no superuser/BYPASSRLS/CREATEROLE/CREATEDB,
  schema ownership or admin membership; then apply `grants.sql`. A core runtime
  role needs these runtime privileges to call the shared-cursor hooks. Never
  give that role the administration DSN. Runtime startup checks unsafe grants.
  `staff.grants.runtime_grants_sql('review_runtime')` renders those exact grants
  with a quoted role identifier for separately approved operator execution; it
  never connects, executes, switches roles or grants ownership.
- Production uses `StaffRepository(database=shared_pooled_database)`, whose
  `transaction()` supplies the bounded, TLS-configured pool/restore barrier and
  RealDictCursor. Constructor privilege checks and all staff operations use that
  provider. `StaffRepository(dsn)` is the isolated-test fresh-connection option;
  do not use it as the production TLS/pooling implementation.
- This is a global identity registry, not workspace RLS. Core continues to own
  tenant RLS and membership checks. References and assignments are not client
  authorization by themselves. A compromised SQL credential remains privileged.

## Configuration and OIDC transport contract

`StaffSettings(client_id, origin, rp_id, generation, digest_key)` has no usable
defaults. Exact allowed pairs are `https://review.test` / `review.test`,
`https://review.spacemusic.io` / `review.spacemusic.io`, and
`https://review-staging.spacemusic.io` / `review-staging.spacemusic.io`.
Use separate client IDs, keys, registries and generation UUIDs per environment.
`generation` comes from non-restored operational configuration. Changing it
invalidates sessions, challenges and enrollment permits, NOT assignments or
enrolled keys. Replay external revocations before opening a restored database.

Construct `GoogleOIDCVerifier(client_id, key_provider, clock)` with a trusted
provider returning `JwksSnapshot(keys, fetched_at, expires_at)`. No JWKS provider
means closed. Snapshot lifetime is bounded to 24h and unknown/duplicate key IDs,
stale keys, untrusted key URLs and non-RS256 algorithms fail closed. Only Google's
documented issuers are accepted; the legacy spelling is canonicalized AFTER
signature verification. Claims enforce audience, authorized party, subject,
nonce, integer times and expiration. Signed `email_verified` must be boolean true
and `hd` must equal the approved `spacemusic.io` workspace. Email/hd are admission
requirements, never identity keys or auto-provisioning. `amr`/`acr` grant no MFA.

`GoogleOIDCTransport` implements `exchange_code(code=..., code_verifier=...,
redirect_uri=...) -> ID token` and `jwks_snapshot() -> JwksSnapshot`. It is disabled
by default. The main production factory owns explicit approved enable/configuration:

```python
transport = GoogleOIDCTransport(
    settings,
    enabled=approved_enable,
    client_secret_path=independent_mounted_secret_path,
)
verifier = GoogleOIDCVerifier(settings.client_id, transport.jwks_snapshot)
service = StaffService(
    StaffRepository(database=shared_pooled_database),
    settings,
    oidc_verifier=verifier if approved_enable else None,
    exchange_code=transport.exchange_code if approved_enable else None,
)
# Application lifespan shutdown: transport.close()
```

The secret is a separate regular-file mount with owner-only permissions (0400 or
0600), absolute path, no symlink, 16..2048 printable ASCII bytes plus an optional
newline. It is read for each exchange, so atomic mount replacement rotates it;
it is never loaded from environment or shared Typeform/Resend/main-site settings.
Supply separate credentials per environment; independent credential provenance is
an operator obligation, not something file permissions can prove. No secret or
network access occurs while disabled. `http_transport=` is solely a MockTransport
test seam; production omits it and must never substitute a fake adapter.

Only `https://oauth2.googleapis.com/token` (POST) and
`https://www.googleapis.com/oauth2/v3/certs` (GET) are reachable. No discovery,
redirects, proxies, ambient certificate/proxy settings or token-selected key URLs.
TLS verification stays enabled. Limits: four connections, two keepalives, 1s pool
wait and 3s connect/read/write inactivity timeouts, 64KiB uncompressed JSON bodies,
duplicate-member rejection, 16KiB ID tokens. A 12s cumulative budget is checked
between stream chunks/GET attempts; it is not a hard cancellation timer for OS DNS
or an in-progress synchronous socket operation. Apply process/egress supervision
and ingress concurrency limits as well; do not run this on the async event loop.

JWKS GET has at most two attempts for network failures/429/selected 5xx. Token POST
has exactly one attempt, including connection failures/timeouts/5xx. State is
consumed BEFORE exchange: unknown outcomes require a new sign-in, never retry the
old code or return unverified identity. No access/refresh tokens are retained.
JWKS cache refresh is process-local/single-flight with bounded 1s lock wait;
Cache-Control max-age, Age and Date limit freshness, with 5m fallback and a 24h
hard cap tracked with both wall and monotonic clocks. No stale-on-error or
no-cache/no-store reuse; malformed/uncacheable keys fail closed. Unknown signing
key IDs fail closed until normal cache expiry; no attacker-triggered refresh loop.
There is no endpoint accepting a browser-supplied ID token. Scopes: `openid email`.

## Enrollment and recovery

`StaffAdministration` is a separate trusted, supervised control-plane interface,
never a browser endpoint. `preapprove(issuer, subject, display_name,
supervision_reference, role='reviewer')` binds exact Google issuer/subject to a
named principal. `role='operator'` or `set_role(...)` needs explicit approval;
Google claims cannot create that role. Role changes revoke existing sessions.

Issue separate short-lived single-use permits with
`approve_enrollment(principal, 'primary'|'backup', supervision_reference=...)`.
OIDC-only sessions may call `begin_enrollment` / `complete_enrollment` but have no
review authority. Registration requires UP+UV, exact RP/origin and ES256. Two
distinct canonical public keys are required; synced/backup-eligible credentials
are rejected. Each key needs a separate signed assertion via
`begin_uv(token, confirm_credential=id)` / `complete_uv(..., confirmation=True)`.
Only then is enrollment active. Confirmation does NOT grant fresh session UV;
complete a normal assertion before accessing cases or intake.

Human supervision must establish independent primary/backup devices and identity.
No trusted hardware attestation allowlist is implemented: signatures prove key
possession and signed UP/UV flags, not a hardware provenance guarantee.
`suspend` stops all access. Lost-device recovery uses supervised
`reset_enrollment`: revokes all sessions, old keys, permits and assignments,
requires TWO new keys and separately renewed assignments. No email recovery,
Google-MFA assumption, recovery code or self-service reset bypass exists.
Supervision references are audit references, not automated proof of supervision.
Case assignment is a MANUAL supervised operator/control-plane path through
`StaffAdministration.assign(...)`, not a shipped browser assignment UI. The
operator must verify the named principal and current non-deleted case against the
deletion journal/current database before granting, and coordinate with the same
deletion/restore fence. Do not reassign erased case IDs. The HTTP runtime cannot
insert/update assignments; it only reads them during fresh authorization.

## Integration hooks

- `begin_oidc()` -> authorization_url + private browser_binding + state.
  `complete_oidc(state=..., browser_binding=..., code=...)` -> raw opaque session
  cookie value. States/challenges commit consumption BEFORE verification, including
  failure; clients restart instead of replaying a failed ceremony.
- `begin_enrollment(token, permit)` and `begin_uv(token, confirm_credential=None)`
  return `{challenge_id, publicKey}` suitable for browser WebAuthn. Completion
  accepts the browser's JSON credential. All ceremonies are session-bound,
  expiring and single-use; counters and signatures are verified by webauthn.
- `require_session(token)` is an OIDC-only context for status/enrollment, NOT
  authorization. It exposes principal_id, role/state, uv_at, expires_at and
  session_reference. Only the opaque cookie is a browser credential; the digest
  reference must never be accepted as login. Database stores no raw session/JWT.
- `authorized(token, workspace)` is a context manager covering the WHOLE protected
  action, with current assignment, enrolled keys and UV <=5m. UV timestamp is
  conservatively the challenge's issuance time, so held responses add no freshness.
- `authorize_in_transaction(db, token, workspace)` does the same using an existing
  RealDictCursor, with no nested transaction. All hooks lock staff principal then
  session, BEFORE core workspace locks. Core must still check current membership
  and reviewer permissions after locking its workspace.
- `authorize_reviewer_digest_in_transaction(db, staff_session_digest, workspace)`
  validates a SERVER-OWNED `staff_session_links` reference and returns identity.
  Compare its principal_id to the core membership. Use on EVERY linked portal
  operation, never store/rely on a permanent `mfa=true`. `validate_session_reference`
  additionally accepts explicit principal_id/workspace_id keyword arguments.
- `require_operator(token, action='intake_list')` is a context manager;
  `authorize_operator_in_transaction(db, token, action)` locks/checks the same
  records in the caller's transaction. Only `intake_list` and `intake_approve`
  are allowed. No workspace assignment is needed, but active operator role,
  complete enrollment and fresh UV remain mandatory.
- `StaffAdministration.assign(principal, workspace, active=..., supervision_reference=...)`
  grants/revokes a named assignment under the same principal-first lock.
- `list_workspaces(token, workspace_guard=...)` returns `{"workspace_ids": [...]}`.
  Current active principal/session, two confirmed keys and fresh UV are mandatory;
  both reviewers and operators may list only their own active assigned IDs.
  The synchronous `workspace_guard(db, workspace_id) -> bool` runs in that same
  principal-first transaction. It MUST check the external erasure journal/restore
  barrier AND current core case row, returning False for a deleted/missing case.
  Missing guard, exceptions or non-boolean results fail the entire request, never
  return a partial list. No customer details are exposed before review context.
  IDs are sorted before guard/workspace locks; more than 1000 assignments fails
  closed rather than silently truncating. Core owns tenant/search_path setup.

## Case erasure

Register `StaffErasureParticipant()` with the coordinator's privileged erasure
worker. `erase_in_transaction(db, workspace)` deletes only that case's rows from
`catalog_staff.assignments`, including revoked assignments. It is idempotent and
uses the caller's existing transaction, no commit/connection or nested transaction.
Call only after the durable external deletion record and normal case fencing;
replay it before restored data is reopened. It retains global principals, keys
and identity audit, which follow separate staff-identity retention policy.

`staff.grants.erasure_grants_sql(erasure_worker_role)` renders the separate
`erasure-grants.sql`: schema USAGE, SELECT(workspace_id), DELETE on assignments
only. Apply as migration administrator to a dedicated non-HTTP erasure role.
No principal/key/audit mutation is granted. Runtime grants remain unchanged, and
`StaffRepository` startup explicitly rejects a runtime with assignment DELETE.

## Optional HTTP router

`staff.http.create_staff_router(service, establish_context=None, workspace_guard=None)` returns an
APIRouter, not an app. It uses separate host-only Secure/HttpOnly/SameSite=Lax
`__Host-space_staff` and `__Host-space_staff_oidc` cookies, exact Host/HTTPS/Origin,
per-session CSRF, no-store, no-referrer and bounded JSON bodies. No shared CORS.

- POST `/api/staff/oidc/start` with `{}` and exact Origin. Browser binding stays
  in its HttpOnly cookie. This bootstrap POST is the only CSRF-token exception.
- GET `/api/staff/oidc/callback`: the ONLY query-bearing, cross-site navigation
  exception. Main middleware must narrowly exempt this exact path AND method,
  leaving the router's checks in place. Reject duplicate/unrecognized query keys;
  permit code/state and Google's bounded scope/authuser/prompt/iss metadata or
  error/state. Proxy/server access logs MUST redact this callback query entirely.
  Callback sets staff cookie, clears binding and redirects to `/staff/`.
- GET `/api/staff/session` returns public status and a CSRF token (no digest).
  All subsequent mutations need exact Origin plus `X-CSRF-Token`.
- GET `/api/staff/workspaces` returns exactly `{"workspace_ids": ["uuid", ...]}`
  after fresh UV and the guard described above. No operator-only role gate and no
  customer fields; no query parameters/pagination, no mutation or CSRF header needed.
- POST `/enrollment/options` `{permit}`; POST `/enrollment/verify`
  `{challenge_id,credential}`; POST `/assertion/options` `{}` or
  `{confirm_credential}`; POST `/assertion/verify`
  `{challenge_id,credential,confirmation?}`. All paths use `/api/staff` prefix.
- DELETE `/api/staff/session` revokes and clears the cookie.
- POST `/api/staff/workspaces/{workspace}/context` with `{}` is closed unless
  coordinator injects `establish_context(db, identity) -> Response`. It runs AFTER
  current staff authorization in the SAME transaction. Main sets tenant context,
  locks/checks core membership, mints its portal session and writes its digest link,
  then returns its secure-cookie Response. The supplied cursor uses pg_catalog
  search_path: qualify core tables or explicitly set its search_path locally.
  No raw staff token is provided to or stored by this hook.

Main must map StaffError from non-router hooks to sanitized errors. Async callers
must offload the ENTIRE synchronous transaction/context, not separate pieces.

## Remaining gates

Coordinator owns UI, main middleware exceptions, portal link minting, intake
endpoints, production transport/guard wiring and role provisioning. HTTP requests need
edge/global rate and concurrency limits. Expired challenge/PKCE payload cleanup
and identity/audit retention need an approved privileged maintenance job. Provider
secret delivery/rotation, egress supervision, hardware supervision procedures, real
browser/device ceremonies, external revocation-journal replay and restore drills
remain launch gates. No bool-only MFA fallback or fake production adapter exists.

Library/API basis: [Google OIDC](https://developers.google.com/identity/openid-connect/openid-connect),
[PyJWT verification](https://pyjwt.readthedocs.io/en/stable/api.html),
[WebAuthn registration](https://duo-labs.github.io/py_webauthn/registration.html),
[WebAuthn authentication](https://duo-labs.github.io/py_webauthn/authentication.html),
[HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/),
[HTTPX environment isolation](https://www.python-httpx.org/environment_variables/).
