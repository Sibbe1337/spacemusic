# Verification: brokerage preparation increment

25 September 2026. Local synthetic acceptance, not production certification.

## Automated results

| Scope | Passed | Skipped | Notes |
| --- | ---: | ---: | --- |
| `tests/catalog_review` | 1,144 | 118 | Includes 33 new dealflow integration/contract tests |
| `services/catalog_review_ui/*.test.mjs` | 175 | 2 | Includes new workflow tests and portal entry gating |
| Existing Jev experiment tests | 54 | 0 | Synthetic/offline tests only, no new live model call |
| Existing funnel and Typeform intake tests | 13 | 0 | Scenario entry contains its own 47 assertions |

The Python suite ran in a fresh temporary Python 3.12 environment with the
existing staff test requirements, boto3 and cbor2. System Python lacked staff
dependencies and could not collect the full suite; this was resolved using that
isolated environment rather than modifying global packages.

Skipped backend checks require Linux parser containment, the explicitly enabled
PG17 smoke environment or the dedicated two-container IPC topology. Two existing
browser-test entries are opt-in and were skipped by the Node suite. This run is
not evidence of a built production container or a live cloud restore.

New tests cover source/revision binding, per-case authorization, staff MFA,
cross-case isolation, append-only permissions, concurrent request deduplication,
zero revenue, currency/period limitations, expired or changed mandates, changed
evidence, owner decisions, selected documents and populated-table erasure while
preserving another case. UI checks include exact retry identity, malformed
acknowledgements, uncertain writes across refresh, validation errors, consent,
revocation, session expiry, page suspension, late callbacks and logout.

## Independent review

A separate read-only reviewer checked the backend and UI. The UI review found
logout cancellation and discarded unresolved request identity. Both were fixed,
then tested with delayed responses, repeated logout, cleanup and refresh. Final
bounded re-review reported no remaining P1/P2 findings in that scope. This is
not a comprehensive penetration test or legal review.

## Browser acceptance

Using the local disposable PostgreSQL-backed fixture:

- Saved human checks with source references, obtained a matching fictional
  buyer and prepared a versioned presentation with an explicitly selected file.
- Changed to the owner view, inspected the exact text and document fingerprint,
  approved it, verified the reviewer still had no delivery capability, then
  revoked the approval and observed the revoked state.
- Checked desktop layout and 390/320-pixel mobile overrides. A navigation overflow
  at 320 was found and fixed; final checks had matching scroll/client widths.
- Opened the evidence disclosure with Enter and tabbed into its status selector.
- Verified the isolated preview's Catalog workspace handoff clearly explains
  that it is not real customer access. Reset temporary viewport overrides.

No actual screen-reader session, external mail, Jev processing, public links,
commercial terms, payments or real customer records were used. The server was
restarted after QA to leave a clean fictional case for user review.

## Preserved / not deployed

Marketing source comparison before and after:

```text
398 files
SHA-256: 8a8ff5800730f64f227ed11aae2d9aaf788f32df514f4ad48366d698912607ca
```

The comparison includes relative names and file bytes, excluding node_modules,
.wrangler, build and dist. No marketing file changed. This is preservation
evidence, not a guarantee about future search rankings.

No production deployment, secret change, DNS change or customer-data migration
was performed. Delivery, payment, buyer subscriptions and real Jev processing
remain off/not implemented. Growth recommendations remain drafts in
`docs/dealflow-growth-pilot-20260925.md`. Existing legal/operator, privacy,
infrastructure and restore gates still apply before any real customer rollout.
