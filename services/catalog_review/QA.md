# Phase 2A verification

Date: September 18, 2026. Scope: test-only backend core following owner design
approval, not full phase 2 acceptance or production authorization.

## Executed results

- 72/72 backend tests pass against real disposable PostgreSQL, including the
  HTTP adapter through ASGI. Final run: 5.45 seconds. No skipped tests.
- 48/48 existing design-preview model/server/DOM checks pass unchanged.
- 13/13 existing marketing scenario/tracking/Typeform-intake tests pass.
- Ruff import, undefined/unused symbol and core syntax/error checks pass with
  `--select E4,E7,E9,F,I`; formatting performed only on the new backend/test files.
  This is not a claim that every optional repository-wide lint rule was run clean.
- No packages, hosted resources or production database migrations installed.
  Temporary test clusters use Unix sockets only and are stopped at teardown.

## Important exercised boundaries

Real PostgreSQL tests run as an unprivileged application role distinct from the
migration owner, not as a superuser pretending to test RLS. Cases include:

- Two workspaces sharing an email still have separate memberships/sessions.
  Swapping workspace IDs, foreign document IDs and unscoped SQL does not expose
  another workspace. Cross-workspace INSERT/UPDATE is blocked by the database.
- Missing FORCE/RLS, superuser runtime, audit/snapshot UPDATE/DELETE grants and
  TRUNCATE privileges stop startup. Runtime cannot mutate submitted snapshots.
- Concurrent intake creates one application/invitation/outbox. A forced audit
  failure rolls the entire receipt back; changed-payload replay is rejected.
- Concurrent invitation consumption succeeds once; GET cannot consume a link.
  Expired invitation/session, revoked membership, missing reviewer MFA, missing
  origin/CSRF, cross-site fetch and injected Host all deny access.
- Peer throttling remains enforced after malformed input and ignores untrusted
  forwarding headers. Secrets are absent from persisted invitation/session rows
  and invalid request bodies are not echoed in errors.
- Two concurrent draft writes cannot silently overwrite one another. Duplicate
  submission requests return the same immutable snapshot. Boolean consent is
  explicit; unknown rights stay unknown; missing evidence is not verification.
- Quarantined documents cannot be downloaded/submitted. Wrong tenant, stale scan
  completion, changed file bytes, invalid type/size and scanner unavailability
  fail closed. Three failed scan attempts leave the file in quarantine.
- Lost worker leases cannot overwrite new results. Invitation retries preserve
  their idempotency key/link, stop after five attempts, and distinguish provider
  acceptance from inbox delivery. Consumed invites are not sent by later jobs.
- Deletion request blocks sessions and queued work, but explicitly does not
  claim erasure. Original-intake replay does not create a replacement workspace.
- Production, staging, sandbox and public origins remain disabled. No default
  app, legacy payout/offer API, test-login, mailbox, OAuth callback, file endpoint
  or marketing route is mounted by the HTTP adapter.

## Review and corrections

A separate review agent performed a read-only code/security review. It found:

1. Blob cleanup on an ambiguous database commit could remove committed evidence.
   Fixed with an explicit unknown-outcome exception and no destructive cleanup
   in that path. Regression commits real rows, simulates lost acknowledgement
   and checks that the referenced object remains available.
2. Sync database calls in async handlers could stall unrelated requests. Fixed
   by offloading those calls. Regression delays an invitation exchange while a
   separate request completes on the same event loop.

A follow-up review strengthened the startup checks to cover column-level UPDATE
grants and TRUNCATE on the global deduplication/throttling tables, with four new
misconfiguration cases. The concurrency regression now also requires a successful
exchange response, so a delayed HTTP failure cannot falsely pass the test.

During test bring-up, the test migration connection remained open at teardown,
preventing disposable database removal. Explicit connection closing fixed this;
the final suite passes with cleanup. Earlier running suites with the old fixture
failed teardown and are not the reported passing result.

Repository-wide `git diff --check` still reports pre-existing trailing whitespace
in four unrelated admin UI files. Those files were not changed here. Direct
whitespace checks on the new backend/test files pass.

The independent review is not a penetration test, compliance certification or
full production review. No test traffic was sent to Too Lost, Resend, Typeform,
Gmail, Stripe or a live lead receiver.

## Preservation

Before and after this tranche, directory path/content hashes match exactly:

| Directory | Files | SHA-256 aggregate |
| --- | --- | --- |
| marketing | 2177 | `3e5f081e2135d9a02edb6561ea6122c75ba9d49cbbdaea84a68e0d8f8611f10c` |
| tmp/editorial-preview-v5-20260916 | 546 | `e421ebad5f5ddc018a88b46e46d5990a2c131f1a1807be9ea89aa98496fba4ce` |
| services/spacemusic/portal | 30 | `4c57280fea9059e4eb58c6b5a724952d008ef3ae50281bf82679de416f98107c` |

The marketing directory already contained six additional files versus the
previous phase's baseline when this tranche began. They were preserved; the
published artifact and prior local portal match the earlier hashes too.

The production artifact still contains all 141 sitemap URLs. No production
publish, DNS/header change, Apply edit or preview UI change was performed.
No fresh live crawl, rankings, traffic or LCP improvement is claimed.

## Not yet verified or implemented

No real storage/AV/parser, identity provider/MFA enrollment, provider import,
key rotation, hosting, production dependency audit, inbox delivery or customer
session has been exercised. The approved design has not been wired to this API.
No cloud/object backup restore or complete erasure/revocation-journal drill has
been performed. These remain launch blockers as listed in README.md.
