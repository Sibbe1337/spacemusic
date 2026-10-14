# Too Lost isolated offline integration

This package does not mount routes, apply migrations, read environment secrets,
start jobs, or provide a network transport. `Config.enabled` defaults to false.
Even enabled instances reject transports without an explicit `offline = True`
contract. Only tests provide a synthetic transport. This marker is an injection
contract, not an egress firewall; the coordinator must keep external egress closed.
The document pilot does not import or depend on this package.

## Coordinator interface

Install the declared encryption dependency in the application's isolated runtime.
Do not substitute a fake encryption implementation. Apply `schema.sql` explicitly
after the shared catalog-review schema, as a migration owner, to a disposable
database for this tranche. No deployed-data migration is supplied or performed.
The normal runtime role must remain non-owner, non-superuser and NOBYPASSRLS.
Startup checks require forced RLS and immutable fact/page privileges.

```python
from services.catalog_review.providers.adapter import ReadOnlyAdapter
from services.catalog_review.providers.contracts import Config
from services.catalog_review.providers.crypto import TokenVault
from services.catalog_review.providers.repository import (
    Repository,
    ReviewSessionAuthority,
)
from services.catalog_review.providers.service import TooLostService

config = Config()  # Disabled. Never load previous credentials implicitly.
repository = Repository(
    review.db,
    ReviewSessionAuthority(review),
    config,
    review.clock,
    workspace_guard=review._active,
)
vault = TokenVault(injected_versioned_keys, injected_active_key_id)
provider = TooLostService(repository, vault, ReadOnlyAdapter(config, offline_transport))
```

`workspace_guard(cursor, workspace)` is REQUIRED and must lock the workspace and
check the independent deletion journal, failing closed on journal unavailability.
The existing `review._active` is the coordinator bridge; `ReviewSessionAuthority`
also reuses the core's owner/session authorization, rather than accepting caller-
asserted identities. A database-only status predicate is not a valid substitute.
Every owner operation, worker step, pre-request guard and commit rechecks this
boundary. Quota reservation precedes the final pre-request check. An already
dispatched request cannot be recalled; its late result cannot commit after a
tombstone, membership loss, disconnect or lost lease. Local credential invalidation
is deliberately allowed after a tombstone; it never activates a workspace.

Public coordinator methods (all HTTP mutation authorization remains the host's job):

| Method | Result / responsibility |
| --- | --- |
| `start_oauth(session)` | One-use state + encrypted PKCE verifier; returns authorization URL only. |
| `callback(session, state=..., callback_uri=..., code=... / error=...)` | Current initiating session, workspace, principal, environment, client and exact callback required. Returns pending account ID, not tokens. |
| `confirm_account(session, connection_id, account_id)` | Explicit account confirmation, safely repeatable. No email matching or SPACE login creation. |
| `start_import(session, connection_id, request_id, release_ids=())` | Durable idempotent job; changed body under the same UUID conflicts. Empty selection imports catalog metadata only. |
| `import_status(session, run_id)` | Local status only; never triggers provider calls. |
| `snapshot(session, run_id)` | Only completed retrievals; pinned fact version, decimal strings, blocked financial conclusions. No sum, FX, valuation or rights inference. |
| `refresh(session, connection_id)` | Coordinated expiry-driven refresh; returns status/version only. |
| `rewrap_credentials(session, connection_id)` | Re-encrypts the current token envelope with the injected active key. Keep old keys until pending OAuth envelopes and backups no longer require them. |
| `disconnect(session, connection_id)` | Fences jobs and erases credentials even with feature disabled. Does not claim remote revocation or complete erasure. |
| `step_import(workspace, run_id)` | INTERNAL worker entry, one page per call; scheduler supplies identifiers, never a stored browser token. |

Worker consent survives logout, but not current owner membership loss, connection
generation changes or external deletion. There is no scheduler or queue credential
provisioning in this package. The host must not expose `step_import` as a public
unauthenticated endpoint. Register per-process/fleet feature gates in the host;
no worker loop is started here.

## Routing and credentials

Use private origins only: sandbox/staging `https://review-staging.spacemusic.io`,
production `https://review.spacemusic.io`. Callback path is exactly
`/api/integrations/toolost/callback`. The old marketing-origin callback is rejected;
there is no forwarding/redirect bridge. Re-register and verify these callbacks
before any sandbox work. Rotate/reissue the old client secret first; keep client
secrets, encryption keys, databases and provider accounts separated by environment.

The host must isolate the GET callback from the portal's no-query rule; reject
duplicate/oversized parameters and invalid code/error combinations before calling
the service, redact query strings at ingress, and send a clean private-origin
redirect with no-store/no-referrer headers. Retain host-only Secure/HttpOnly cookies
and exact-origin + CSRF mutation checks. Reject sibling-origin API requests marked
`same-site`, as well as `cross-site`, except narrow navigation/callback routes.
Do not add CORS access for marketing, embed analytics, or return token envelopes.

OAuth POSTs are single-attempt. Unknown code-exchange outcomes consume the state;
unknown rotating-refresh outcomes invalidate the connection rather than retrying
the old token. An expired refresh lease also requires reconnect, since a previous
worker may have committed a refresh remotely. Fresh connection generations and
token versions fence all delayed writes. AES-256-GCM uses fresh 96-bit nonces and
AAD containing purpose, workspace, connection, environment, generation, version
and account/principal context; PKCE additionally binds state/session/callback/client.

## Import and storage contract

`toolost_connections` and `toolost_oauth_attempts` contain only encrypted reusable
credentials/verifiers. `toolost_import_runs` stores request fingerprint, selection,
account, manifest, generation, lease, counters and coverage. `toolost_import_pages`
and `toolost_source_facts` are append-only under runtime grants and workspace RLS.
Each successful page and its next checkpoint share one commit. A worker crash or
unknown database commit acknowledgement is reconciled from the checkpoint, not by
blindly restarting the job. New import UUIDs create new source versions; nothing
overwrites submitted or previous facts. There is no raw-response archive.

Release lists use `page`/`perPage`; optional account sales lists use `page`/`per_page`.
Both are bounded to 100 per request. The worker imports catalog pages and, for an
explicit selection, one nonpaginated release overview per selected ID. Track and
account-level endpoints exist in the read allowlist but are not automatically
imported. Returned external URLs are discarded and never fetched.

Pagination totals/cardinality and duplicate IDs/pages are checked. An unstable
offset-paginated provider cannot be turned into a point-in-time snapshot by this
client; completion means the bounded retrieval finished, not verified historical
completeness. Selected IDs must occur in the retrieved catalog; their sales ID
mapping remains unverified and is disclosed in every financial coverage record.

Amounts are decoded directly from JSON into Decimal, stored as SQL numeric and
serialized as decimal strings. Precision is not rounded; negatives and repeated
dated entries remain separate evidence. Missing amounts/dates stay null. Currency,
period meaning and gross/net basis remain unknown even if an unverified response
offers similarly named fields. SQL constraints prevent enabling those semantics
in this tranche. `conclusions_allowed` is always false, including for a completed
import. Do not sum API and uploaded statements, alternate breakdowns or currencies.

Default local safety limits: 10 MiB/response, 100 total pages, 10,000 total records,
100 selected releases, 500 total outbound calls/job (including refresh), a
30-minute job deadline and a 120-second lease. Requests carry 5-second connect and
30-second total deadlines; streamed bytes and elapsed time are checked here. A
future real transport must enforce blocking I/O deadlines and close response
bodies on all exits; injected synchronous calls cannot be forcibly interrupted by
this package. These local limits are not provider guarantees or approved volumes.

`toolost_quota` serializes the configured developer pool across workspaces/processes.
Local defaults are 30 calls/minute and 5,000/month; every attempted call is reserved
conservatively. Configure the SAME pool identifier for all apps sharing credentials.
Header observations can only lower remaining allowance. Provider exhaustion is
sticky until operator reconciliation; a local UTC month rollover does not erase
provider exhaustion. Other apps outside this repository require coordinator-wide
accounting. No paid-tier activation or overage is automated. 429 honors Retry-After,
transient GET failures retry in later scheduler steps at most three attempts, and
401 permits one coordinated refresh/replay. The scheduler should add jitter when
dispatching eligible jobs. Permission/schema failures stop the import.

## Erasure participant

Register `ProviderErasureParticipant()` in core
`erase_workspace(..., extensions=(participant, ...))` BEFORE core table deletion.
Core verifies the durable external tombstone and owns the transaction. Explicitly
apply `erasure-grants.sql` to a separately provisioned `review_erasure` role with
the core's scoped workspace grants. Never apply these DELETE grants to runtime.
The participant rejects unscoped, table-owner, superuser/BYPASSRLS or insufficiently
privileged callers. It fences connections/jobs and deletes facts, pages, runs,
OAuth attempts and connections in FK order. All changes roll back with the core
transaction. It is idempotent and never changes source-identity keys, clears the
external journal or reactivates a workspace. Pool quota counters contain no
workspace/provider identity and are retained. Remote revocation is NOT implemented.
Retention policy, database backup expiry and journal replay remain core duties.

## Evidence and release gates

Primary reference: https://developer.toolost.com/docs/api
OAuth guide: https://developer.toolost.com/docs
Local supplied registration/questions: `../../catalog_review_preview/TOO-LOST-QUESTIONS.md`
Local governing plan: `../../../docs/toolost-launch-plan-20260917.md`

The endpoint reference uses read:profile/read:releases/read:sales; the guide uses
different catalog/earnings names. Only the former minimal scopes are requested.
This adapter intentionally requires an explicit exact granted scope string, Bearer
token type, positive expires_in and a refresh token in each token response. Real
provider omission/rotation behavior and confidential-client-plus-PKCE form auth
must be confirmed before changing this strict offline contract. Refresh expiry is
not inferred. Sandbox OAuth URLs are supplied registration material, not a verified
exchange. Official OpenAPI export, catalog/sales mapping, currency, amount basis,
earning/import dates, correction rules, completeness and remote revocation remain
unverified. No sample value fills these gaps.

Before any external operation: independent provider use-case/bulk/retention/processor
approval; callback registration; fresh managed secrets; approved EU portal storage;
identity/session and HTTP boundary integration; real transport deadline/streaming
review; quota ownership; scheduler and erasure extension registration. Production
requires separate approval after authorized sandbox functional verification. No
provider load, penetration or security testing is authorized by these local tests.
None of these provider gates blocks the separate document-first pilot.

## Local verification

Tests are `tests/catalog_review/test_toolost.py` and `test_toolost_adapter.py`.
They apply this schema explicitly to fresh socket-only PostgreSQL databases, use
the unprivileged runtime role and fake provider transports, and forbid Python
network sockets. Crypto tests exercise real AES-GCM. No real provider, old secret,
OAuth browser journey or managed-key service is contacted. Tested using Python
3.11 with already-installed cryptography and a cached psycopg2 wheel extracted to
a temporary test dependency directory, without package downloads. Dependencies
must also be available in whichever interpreter the coordinator uses for its suite.
