# Historical Catalog Review foundation

> Preserved from the earlier README on 2026-09-28. Start with the
> [current portal guide](README.md); implementation-gap statements below describe
> an earlier checkpoint, not an assessment of today's entire codebase.

The document-pilot implementation now supersedes the original test foundation.
See [current implementation and verification](PILOT-VERIFICATION.md) and
[approved pilot operating decisions](PILOT-OPERATIONS.md). These are the current
entry points. Production is still closed; passing synthetic tests is not a
customer-launch approval. No cloud resources or public website were changed.

## Historical Test Foundation

The sections below describe the earlier 362-test baseline only. Statements about
missing modules or test-only restrictions are historical, not the current code.

September 18, 2026. The owner approved the phase 1 design in this task.
The phase 2A core now has a connected customer/reviewer UI and document workflow,
exercised against real disposable PostgreSQL. It is not a public deployment or
a complete phase 2. Distribution is explicitly deferred; payments stay disabled.
See [operating decisions](DEPLOYMENT-PROPOSAL.md) and [phase 2B checks](QA-2B.md).

## Implemented

- One workspace and explicit owner membership per intake source/form/response.
  Replays are idempotent; changed payloads at the same source reference fail.
  A second application from the same address remains a separate application.
- Application, invitation, outbox and minimal audit event commit atomically.
  Only allowlisted public landing paths are retained; no analytics integration.
- Runtime database role is separate from the migration owner. Workspace tables
  use forced row-level security plus explicit current-membership checks. Every
  operation creates a fresh scoped transaction. Startup rejects superuser,
  BYPASSRLS, table ownership, missing RLS, TRUNCATE and mutable snapshot/audit
  configurations covered by the checks in `database.py`.
- Fifteen-minute invitation links require explicit POST consumption. Database
  rows contain keyed digests, not usable links. A sender reconstructs the same
  bounded-lifetime link for retries with a distinct server signing key.
- Session exchange is single-use and atomic under concurrency. Sessions last
  at most one hour; reauthentication replaces this membership's earlier sessions.
  Host-only Secure/HttpOnly cookies, origin checks, CSRF, hashed peer rate limits,
  no query-bearing requests and no-store/noindex apply to the test API only.
- Assigned reviewers must have a server-recorded MFA session, cannot mutate
  owner drafts, and lose access when membership is revoked. There is no reviewer
  login/provisioning endpoint; a real verified identity/MFA adapter is still due.
- Optimistic revisions prevent stale saves. Submitted snapshots are immutable
  to the runtime role. Retries reuse a request ID; missing evidence and unknown
  rights remain explicit. Submission is not ownership verification or an offer.
- Private document lifecycle contracts: immutable object keys, size/type
  prefilter, quarantine, fenced scanning leases, digest/size checks before reading
  and at download, scoped references and three-attempt scanner retry cap.
  A clean scanner result means accepted for review, not genuine or verified.
- Invitation outbox has leases, stale-completion protection, stable idempotency
  keys, expiry and a five-attempt cap. Provider acceptance is not inbox delivery.
  A crash after remote acceptance can cause a retry; exactly-once delivery depends
  on the future provider's verified idempotency contract, not this database alone.
- Deletion requests durably stop workspace access and pending jobs. They do NOT
  erase objects, snapshots or backups; the response explicitly says erasure is
  incomplete. Replayed original intake does not recreate the workspace.
- Unknown database commit acknowledgements are distinguished from confirmed
  rollback. An uncertain upload commit must not trigger deletion of its blob.
  Blocking database calls in async HTTP handlers run outside the event loop.
- Connected `/workspace/` UI in `services/catalog_review_ui` reuses the approved
  typography and layout. Explicit invitation consumption, saved draft revisions,
  immutable submissions and assigned-reviewer questions/replies reach the API.
  No browser storage or analytics; expiration/logout clear private screen state.
- Questions and replies are separate immutable, workspace-scoped records with
  idempotency and current-role/MFA checks. Answers never rewrite a submission.
- Expired/consumed-invitation recovery queues a replacement only for the existing owner
  email. Its public response does not reveal matches or return a login token.
  Mail delivery remains unconnected; a queued invitation is not a delivered one.
- Optional test upload/download routes accept an injected private store. They
  enforce bounded streams, timeouts, concurrency, tenant authorization and stable
  upload IDs. Submitted workspaces permit exact upload replay, not new uploads.
  Downloads are attachments; quarantined documents cannot be downloaded.
- EU-endpoint R2 and Unix-socket ClamAV adapters have offline transport tests.
  No bucket/daemon was configured or contacted. AV alone is not parser security.

## Explicit boundaries

`Settings` permits only mode `test` with `https://review.test`. There is no
global app, launch command, deployment config or route on spacemusic.io.
Both input validation and the initial SQL schema require `example.com` recipients.
Only tests contain fixture mail/storage/scanner adapters and reviewer injection.

`ingest()` is a trusted internal function, NOT a verified public webhook. There
is no Typeform forwarding connection or endpoint. Phase 5 must authenticate the
upstream source before it can construct this input. This does not replace today's
intake, notifications or recipient configuration.

Document endpoints are disabled by default and only mounted when a store is
explicitly injected into the test app. The real browser test uses an in-memory
object fixture and a synthetic scanner, not cloud storage or malware detection.
Do not expose upload until quarantine policy, real private AV and bounded
PDF/CSV/XLSX parsing are verified in the approved deployment environment.
An exhausted/unavailable scanner leaves the document inaccessible in quarantine;
an operator recovery path remains to be built. No user-supplied URL is fetched.

Mail jobs are not handed to Resend or Gmail. Links target a reserved test hostname,
and the invitation landing UI is test-only. A worker already inside
an external send call cannot retract that email on revocation; its link becomes
unusable. Production dispatch must recheck cancellation and reconcile outcomes.

No Too Lost client secret is read, stored or used. No OAuth callback, token
exchange, provider import, valuation, payments or paid report is implemented.
The original design preview remains unchanged and synthetic. The separate
connected UI also displays a synthetic-only notice; it is not a live customer
portal. No user is asked to enter real data into either.

## Run verification

From the repository root:

```sh
python3 -m pytest tests/catalog_review -q
python3 -m ruff check services/catalog_review tests/catalog_review --select E4,E7,E9,F,I
node --test services/catalog_review_preview/*.test.mjs
node --test services/catalog_review_ui/*.test.mjs
node --test marketing/funnel/scenario.test.mjs marketing/funnel/tracking.test.mjs marketing/typeform-intake/intake.test.mjs
```

Tests require the existing Python dependencies FastAPI, Pydantic 2, psycopg2,
httpx and pytest, plus local `initdb` and `pg_ctl`. They do not install anything
or read a real `DATABASE_URL`. They start an isolated PostgreSQL cluster below
`/tmp`, accessible only through its private Unix socket with TCP disabled, and
stop/remove it on completion. Synthetic databases are created per test.
`schema.sql` and `grants.sql` are applied only there, not to any existing database.

The inspected local tools are Python 3.9.6 and PostgreSQL 14.18. Reusing them
for isolated tests is not approval of a production version or dependency set.
Choose and pin supported, patched runtime/dependency versions for staging.

## Next implementation gates

1. EU storage and the SEK 2,000/month planning ceiling are approved; vendor
   selection, processor coverage, complete quote, responsibility and provisioning
   are not. Choose managed PostgreSQL, private storage, secrets and workers after
   those gates. No paid resource was created by this tranche.
2. Build verified identity, named reviewer MFA/provisioning, renewal/logout UX,
   delivery/recovery and revocation administration. UI/API binding now has a real
   database/browser test, but staff MFA identities are still injected fixtures.
3. Add private immutable storage, short-lived authorized download, bounded
   streaming, quarantine scanning/parsing and an orphan reconciler. Never expire
   uncertain-commit objects blindly; check durable document references first.
4. Add key-version rotation and managed secret delivery, migrations, bounded
   production pools, redacted operational telemetry, edge limits and cost caps.
   RLS scopes are server-selected and are not protection against a compromised
   database credential that can execute arbitrary SQL.
5. Approve category-specific retention, implement complete erasure and an
   authoritative deletion/revocation journal outside database backups. Restore
   must reconcile that journal before permitting sessions/jobs. No managed
   database/object backup restore or erasure drill is claimed by this tranche.
6. Complete the remaining independent security, operational and accessibility
   review before phase 2 acceptance. Then proceed to the provider adapter and
   separately authorized sandbox tests, not directly to production.

## Review basis

- Approved project plan: `docs/toolost-launch-plan-20260917.md`.
- [PostgreSQL row security](https://www.postgresql.org/docs/14/ddl-rowsecurity.html):
  the owner/superuser bypass caveat informs the separate runtime role and tests.
- [OWASP token recovery guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html):
  bounded, single-use secrets and rate limiting inform invitation handling.
- [OWASP file upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html):
  layered checks/private storage inform quarantine; an extension or scan result
  alone is not complete upload security.

These references guide implementation; they are not a certification of this code.
