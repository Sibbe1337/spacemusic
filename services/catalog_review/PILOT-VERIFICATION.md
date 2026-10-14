# Document Pilot Implementation and Verification

September 18, 2026. Implementation by a coordinator and six specialized agents.
This is not production sign-off. The previous baseline was 362 backend, 50 UI
and 61 regression tests.

## Implemented

- Separate signed Typeform reception with encrypted durable receipts, stable
  source deduplication, manual Formspree receipt entry and atomic admission.
  Five lifetime pilot slots; deletion does not silently allow unlimited rollout.
- Named preapproved Google issuer/subject identities, signed verified Workspace
  domain/email, PKCE/nonce, application-verified user-presence/verification and
  two supervised authenticators. Google login alone is never sufficient.
- Operator intake UI, reviewer assignment checks and staff-to-case context.
  Assigned-case visibility and every subsequent request consult current staff
  authorization. Assignment/recovery are separate supervised administration.
- Host-only cookies, CSRF and exact origins, including rejection of sibling
  spacemusic.io API origins. Private routes have noindex/no-store headers and
  no analytics. Only exact invitation/OIDC navigations and signed webhook ingress
  receive narrow exceptions.
- Immutable submissions and question-bound document supplements. Unpublished
  files stay owner-only; retries bind IDs, bytes, scope and reply content. The
  original submission is never changed. 25 MiB/file and 40 documents/case.
- EU-endpoint R2 transport, quarantine, private ClamAV and resource-bounded
  PDF/CSV/XLSX parser. The parser has no network in its separate Linux container.
- Paris TEM transport with durable queued/uncertain/accepted/delivered/bounced
  outcomes. Unknown provider acceptance does not cause automatic resending.
- Ninety-day meaningful-activity policy, 14-day notice, explicit continued
  interest and owner-only export, including the admitted receipt, contact,
  saved review records and portal mail status. Document bytes are downloaded
  separately; upstream form/mail accounts remain a separate request scope.
  Reads, repeated requests and background jobs
  do not reset the clock; the deletion job rechecks activity versions under lock.
- Replicated external source/workspace deletion records. Partial journal writes
  block access and source replay and can be reconciled. Prefix-based live-object
  and actual backup-version erasure includes objects with no database row.
- Separate erasure role and subsystem participants. Database backup expiry and
  external Typeform/Formspree/mail deletion are explicitly separate outcomes.
- Versioned migrations, bounded connection pools, private TLS configuration,
  independent deployment generations and fail-closed launch/restore guards.
- Read-only Too Lost provider modules, encrypted tokens, simulator import
  checkpoints and unknown-financial-semantics blockers. Not mounted, scheduled
  or enabled in the document pilot.
- Approved SPACE/Inter customer and staff interfaces, with synthetic staging
  copy separate from customer-facing production copy.

## Verification Scope

Executed checkpoint on September 18:

| Check | Result | Boundary |
| --- | --- | --- |
| Backend/integration suite, with PG17 smoke opted in | 1,112 passed; 117 host-inapplicable tests skipped | Disposable PostgreSQL, synthetic provider transports; three dependency deprecation warnings |
| Customer/staff UI with browser tests enabled | 150 passed, no skips | Real Chrome and virtual authenticators, mocked API responses |
| Original preview and public funnel regressions | 61 passed | Existing Apply/Typeform/scenario/tracking regression suite |
| Linux document/parser suite | 198 passed, one topology test skipped | Dedicated synthetic Linux test image, not the production recipe |
| Networked worker to networkless parser topology | 41 passed | Separate two-container run covers the topology skipped elsewhere |
| Static/import lint | Passed | Core, providers, identity, operations and tests |

Counts include overlapping/parameterized tests; do not sum them as independent
security guarantees. The 117 host skips are Linux-only parser tests and the
dedicated topology test, covered in their separate Linux runs. The PG17 smoke
ran against local PostgreSQL 17.9; native fixture tests use PostgreSQL 14.18.
Production image builds/full lock installation and live ClamAV signature/daemon
verification remain unverified. No cloud/provider functional success is claimed.

Reproduction for the two host suites:

```sh
REVIEW_RUN_PG17_SMOKE=1 python -m pytest tests/catalog_review -q
CATALOG_UI_BROWSER_TEST=1 node --test services/catalog_review_ui/*.test.mjs
```

The host suite uses disposable PostgreSQL and real cryptographic signatures for
synthetic Google JWT/WebAuthn proofs. A composed routing test covers signed
intake, durable deduplication, manual admission, passkeys, assigned-case access,
revocation and blocked sibling origins. It sends no real customer email.

The browser journey covers owner upload, immutable submission, a reviewer
document request, question-scoped upload, attachment publication and exact retry
after a lost response. PostgreSQL is real; storage/AV/mail are synthetic in that
journey. Desktop/mobile and keyboard checks do not constitute a screen-reader
or production accessibility certification.

A real local pg_dump/restore drill proves that the external journal blocks old
sessions, invitations, document reads, scan jobs, mail jobs and replayed intake.
Additional regressions cover source-only partial replication, restore before
intake, orphan live objects and already-erased database rows. These tests do not
prove actual cloud backup version expiry, provider durability or IAM settings.

The bounded parser was exercised in local Linux containers with synthetic files.
The networkless-parser/networked-worker topology was tested separately. It was
not connected to any customer's files or a live cloud scanner service.

## Independent Review

Review identified two release-blocking deletion issues: relying on surviving
document rows missed orphan objects, and workspace-first partial tombstones
could prevent retry before durable source suppression existed. Prefix inventory,
source-first replication, dual-identity access checks and reconciliation tests
were added.

Final bounded re-review also closed the staff-list RLS scope mismatch, the
Google callback's cross-site staff-shell redirect rejection, missing guarded
retention-mail methods and backup TLS verification. The reviewers reported no
remaining P1/P2 in those checked paths. This is not a full production security
audit. Final integration also checks production/staff UI asset packaging and
dedicated staff-assignment erasure grants.

## Remaining Launch Gates

No cloud infrastructure, DNS, supplier order, live API keys, customer invitations
or public website changes were made. Legal name/organization number, operator,
supervised recovery authority, vendor/DPA/residency approval and an itemized final
quote remain external blockers. Existing services are not an EU-only funnel.
The owner confirmed they will provide the company/operator details later;
no placeholders have been treated as approval or used to open invitations.

Real deployment composition/collectors, mounted-secret delivery, live private
storage/IAM, staff enrollment, TEM delivery, AV updates, alarms, backup pruning
and cloud restore/rollback must be verified in the chosen staging topology.
Default startup must stay closed if any adapter, current probe or restore
evidence is missing. A green test fixture is not valid deployment evidence.

There is still implementation work, not only missing credentials: the concrete
`runtime.build_dependencies` bootstrap, real health/restore collectors, bounded
worker scheduling and complete seven-day backup automation are not finished.
Worker deployment therefore deliberately stops instead of running a simulator.
See the explicit [engineering handoff](deployment/REMAINING-INTEGRATION.md).
This repository must not be presented as ready to admit real customers yet.

Too Lost requires a rotated secret, portal callback registration, verified
sandbox results and independent production approval. Document pilot work must
not wait for it. No payment, distribution or automatic valuation is enabled.

## Public-Site Preservation

The path/content baselines from the prior work match this implementation's
checks. The measurement walks depth-first, sorting entries per directory with
JavaScript localeCompare, and hashes each relative path followed by its bytes.

| Directory | Files | SHA-256 aggregate |
| --- | --- | --- |
| marketing | 2171 | fd8e0d8d9b7e3ce899f651716bae9134e6360282033a0dad5b0e235921b48c21 |
| tmp/editorial-preview-v5-20260916 | 546 | a9e7d0c3d391b83ffd5c2808be4cfa3de049ca5deadb6001c217d8230628f364 |
| services/spacemusic/portal | 30 | f6e8c0c56b3dc3fb8b22eb4bf821f88207ac0910beeaddda2410405b5f4227b6 |

All 141 sitemap destinations and current Apply receivers are preserved. This is
a local preservation check, not a crawl of production or a ranking guarantee.
Unrelated worktree changes were neither reverted nor committed.
