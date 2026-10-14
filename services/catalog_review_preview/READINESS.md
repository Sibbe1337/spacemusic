# Implementation gates and data boundaries

Updated September 18, 2026. Scope: first implementation tranche of the approved
September 17 launch plan. These are decisions to resolve, not compliance claims.

## Delivery status

| Phase | Current status | Remaining gate |
| --- | --- | --- |
| 0: mandate/contracts | Repository baseline checked; use-case questions and data map documented. Owner approved EU storage and a SEK 2,000/month new-infrastructure planning ceiling on September 18. | Provider confirmation, legal identity, specific vendors/processor coverage, provisioning approval and retention choices remain open. |
| 1: design | Owner approved the interactive design on September 18, 2026. Existing local model/server/DOM tests and browser checks recorded. | Real assistive-technology and cross-browser review remain before launch. |
| 2: production foundations | Phase 2A core plus a separate connected test UI, reviewer questions/replies, recovery and optional document endpoints. Real database/browser tests, offline R2/ClamAV adapters; original preview unchanged. | Approved infrastructure, verified identity/MFA, mail delivery, managed keys/storage, real scanning and bounded parsers, complete erasure/restore drills and production security review. |
| 3: provider adapter | Only a design fixture contract and state machine exist, not an API adapter. | Versioned official OpenAPI export, endpoint semantics and reviewed OAuth/token implementation. |
| 4: sandbox | Owner supplied app registration and sandbox endpoints on September 18; not connected or tested. | Secure credential configuration, implemented callback and provider-approved low-volume functional tests. |
| 5: intake integration | Current production receiver/notifier unchanged. | Separate forwarding outbox, trusted ingest, replay tests, reconciliation and fallback-source coverage. |
| 6-7: production | Not released. | Explicit pilot approval, legal/operational readiness and verified live functionality. |
| 8: paid report | Disabled/not implemented. | Separate commercial permission, delivery economics, merchant/tax/terms, payment tests and owner approval. |

## Proposed data map, not activated

| Data | Purpose | Proposed access/storage | Required decision |
| --- | --- | --- | --- |
| Source form ID + response reference | Idempotent application creation and reconciliation | Server-only application record; no analytics | Typeform Responses access and short-form adapter verification |
| Contact details | Verify access and send an invitation | Approved private database and approved mail processor | Legal entity, lawful basis, customer notice, delivery/retention terms |
| Workspace membership | Bind owner and assigned reviewer to an application | Authorization boundary on every object and job | Identity provider, MFA for staff, revocation and support rules |
| OAuth transaction | Bind authorization to session/environment/workspace | Short-lived server record; no callback query logging | Implement and verify supplied sandbox URLs/callback; expiry and single-use handling |
| Provider tokens | Perform approved read-only requests | Managed-key encryption; never client storage or logs | Production secret store, rotation, revocation and incident procedure |
| Provider identity | Confirm the intended account | Minimum provider ID and account label | Actual scopes and approved field allowlist; no email-only linkage |
| Releases and reported periods | Prepare a source-backed review | Workspace-scoped normalized records and bounded snapshots | Import volume, bulk/history allowance, data semantics and retention |
| Rights and evidence | Human rights/income review | Private object store, quarantine, scanning, bounded parser | DPA/region, file policy, scan provider, reviewer roles and deletion |
| Submitted version | Preserve the package reviewed | Versioned private snapshot, with documented retention | Allowed retention on disconnect and provider revocation |
| Report, later | Standalone customer readiness deliverable | Private versioned output for the authorized catalog owner | Explicit paid-purpose authorization, permitted calculations and recipients |
| Minimal audit/job records | Restore work, investigate access and incidents | Access-controlled, time-bounded operational store | Retention by category and restore/deletion reconciliation |

No category is sent to Plausible, public previews, AI model training or other
buyers by default. Source statements and alternative API breakdowns are not
added on top of one another. Missing currency and gross/net semantics block
monetary interpretation until clarified.

## Sandbox registration supplied September 18

The following is transcribed from the owner's Developer Portal excerpt, not an
independently verified login, token exchange or API response.

| Field | Supplied value |
| --- | --- |
| Application | SPACE Catalog Review |
| Environment / status | Sandbox / development |
| Client ID (public identifier) | `a2c5ed0a-ab4b-4f9f-9f0c-dc7eea570a08` |
| Registered callback | `https://spacemusic.io/api/integrations/toolost/callback` |
| API base | `https://api-sandbox.toolost.com/v1` |
| Authorization endpoint | `https://sandbox.toolost.com/oauth/authorize` |
| Token endpoint | `https://sandbox.toolost.com/oauth/token` |
| Connected users | None shown in the supplied excerpt |

The app-level allowlist includes `read:catalog`, `read:profile`,
`read:preferences`, `write:preferences`, `read:sales`, `write:releases`,
`read:releases`, `read:analytics`, `read:earnings` and `read:audience`.
The initial integration should request only `read:profile read:releases read:sales`,
subject to endpoint verification. App-level allowed scopes are not evidence of
an individual user's consent or a token's granted scopes. Reject missing
required grants; do not automatically request the broader allowlist.

The client secret pasted in the conversation is deliberately not copied into
this repository or used. Rotate it before configuration and place its replacement
in the approved server-side secret store, not chat, preview assets or logs.

The callback is registered but not implemented by this prototype. Do not start
OAuth until a reviewed server implementation can validate state, PKCE, session,
workspace, environment and single-use expiry. These supplied details do not
authorize production activation, paid reports or new testing categories. No
OAuth exchange, provider request, permission change or deployment was performed
as part of this registration update.

## Unresolved provider details

1. Token-level granted scopes and behavior when requesting only the three
   required read scopes; no token has been issued or inspected here.
2. Currency, gross/net basis, reporting versus earning/payment periods,
   correction policy, history availability and selected-release allocation.
3. Official OpenAPI export path/version and a safely retained specification
   checksum before an API adapter is generated or treated as verified.
4. Token expiry, rotation and revocation behavior; pagination/filter semantics.
5. Approved bulk volume, refresh frequency, retention and downstream processors.
6. Whether a separately paid, manually reviewed readiness report is approved.

## Proposed phase 2 sequence

Design approval is recorded. The first implementation slice adds transactional
intake/invitation/outbox, membership + database isolation, test-only session API,
revision-controlled drafts, immutable submissions and document lifecycle
contracts. See `services/catalog_review/README.md` for implemented boundaries
and remaining work. It does not complete phase 2 or approve hosting/production.

1. Choose isolated hosting, managed database, private storage, queue and secret
   store within the approved EU requirement and SEK 2,000/month planning ceiling.
   Vendor selection, full quote and provisioning still need approval; see
   `services/catalog_review/DEPLOYMENT-PROPOSAL.md`. Distribution is deferred.
2. Record authentication/session and membership contracts; define named staff
   roles and MFA. Production entrypoint must exclude every fixture/test route.
3. Implement transactional application + invitation outbox with fake transports
   in staging, independent from current Typeform/Resend notifier availability.
4. Implement private evidence quarantine/scanning and permissioned downloads;
   complete two-workspace authorization and upload failure tests.
5. Implement restore/deletion drills and incident runbook; have another reviewer
   review the production boundary before any real personal data is imported.

Do not turn the current loopback static preview into a production server.
Do not enable the old seller API's valuation, offer, signature or payout routes.

## Public-site preservation baseline

Recorded before this tranche using a deterministic traversal of file paths and
contents, including existing untracked files. The repo already contained many
unrelated edits; none were reverted, committed or deployed here.

| Directory | Files | SHA-256 aggregate |
| --- | --- | --- |
| marketing | 2171 | `4bbd10d9f461a41e520906aba24b2d6e6c487612d6cdea7e64558714a4a57e80` |
| tmp/editorial-preview-v5-20260916 | 546 | `e421ebad5f5ddc018a88b46e46d5990a2c131f1a1807be9ea89aa98496fba4ce` |
| services/spacemusic/portal | 30 | `4c57280fea9059e4eb58c6b5a724952d008ef3ae50281bf82679de416f98107c` |

The release marker identifies production `55284dbb` with 141 sitemap URLs.
This tranche does not publish the pending conversion preview `fa09e20b`, add
portal routes to the public sitemap or load any new scripts on marketing pages.

No fresh Google crawl, ranking, conversion lift, production LCP or live API
correctness is claimed by unchanged source bytes or local test results.
