# Phase 1 verification

Verified September 17-18, 2026. Local design prototype only; no provider
requests, production leads, emails, uploads, payments or deployment.

## Automated checks

- 48/48 preview checks pass: 31 state/amount/persistence checks, 7 HTTP boundary
  checks and 10 DOM interaction checks using the actual UI event handlers.
- 13/13 existing scenario/tracking/intake tests pass. The scenario script also
  reports 47 arithmetic/boundary assertions. These are the current repository
  tests, not a rerun of the obsolete historical 33-navigation browser script.
- UI module syntax check passes. No runtime dependency was installed.
- HTTP tests use only a temporary loopback server. Intake tests use simulated
  receivers and SDKs; no test lead is sent to Typeform or Formspree.

Covered cases include: unknown/invalid percentages, unknown currency, empty
history versus true zero, negative adjustment, duplicate months, duplicate
submission, wrong-account cancellation, declined permission, stale import
callbacks, partial import resume, expiry, tampered storage, blocked storage,
missing documents, immutable snapshots and separate deletion requests.

DOM tests additionally verify actual save/submission failure and retry,
preserved field values, disabled percentage for unknown ownership, no real file
input, error focus, attachment focus, help behavior and a completed memory-only
journey. DOM tests do not prove layout, live OAuth or server authentication.

## Browser observations

Checked in the Codex in-app browser against http://127.0.0.1:4197/:

- Complete simulated provider journey through coverage, two selected releases,
  unknown ownership, sample evidence, explicit scope confirmation, submission,
  reviewer question and sample reply. Reply and snapshot survived reload.
- Manual source route with a selected release, shared 50% rights, save failure,
  session expiry, preserved draft and retry. Missing evidence remained visible
  in the summary instead of being treated as verified.
- Wrong-account recovery did not start an import. Declined permission left the
  document alternative available.
- Interrupted import retained its checkpoint across reload; resume completed
  with 8 of 12 sample months. Disconnect and deletion request stayed separate.
- Empty catalog showed no inferred zero total and continued through sample
  documents. Unknown currency blocked totals while retaining raw source values,
  including the negative adjustment.
- Summary checked at widths 320, 390, 768 and 1440. Document widths were below
  viewport width at all four sizes (no page-level horizontal overflow).
- Visual inspection of desktop invitation, mobile invitation and 320px summary.
  Expanded source table also fit the 320px viewport without page overflow.
- Keyboard Tab/arrow selection of source, Enter continuation and Space release
  selection worked. Step/error focus and form labels inspected in accessibility
  output; attachment-focus preservation also has a DOM regression test.
- Browser console returned no captured errors or warnings on the checked route.

No real Safari/Firefox, VoiceOver, OS high-contrast mode or actual 200% browser
zoom run was performed. Reduced-motion and forced-colors styles are implemented
but not a verified WCAG conformance claim. Not every screen was captured at
every breakpoint; this is a design-gate check, not final production acceptance.

## Issues found and corrected

1. A null percentage incorrectly passed for declared known ownership. It now
   fails; deliberately unknown ownership still remains valid and non-numeric.
2. Unknown ownership disabled a field whose absent form value could throw.
   Null-safe extraction and a real DOM regression now cover this path.
3. Changing sources could retain prior selection/rights answers. A fresh source
   clears that context with a visible warning; completed submissions stay locked.
4. Old callbacks after disconnect and submitted-state navigation are guarded.
5. Save announcements were stale after success. They now reflect the actual
   local outcome, without claiming server persistence or delivery.
6. Partial history no longer gets a completed-stage checkmark. Missing-period
   ranges and empty-history totals reflect the displayed synthetic coverage.
7. Mobile header actions have readable labels and minimum hit targets; the
   document control retains keyboard focus when its Add/Remove state changes.

## Preservation

Recomputed aggregate hashes match the three pre-work baselines in READINESS.md
exactly: marketing (2171 files), the published artifact (546 files including
hosting controls), and the previous local portal (30 files).

Therefore this tranche changed none of the baseline content, release marker,
141 sitemap URLs, Apply assets, Typeform notifier or existing local portal.
No hosting publication, live route/robots change or marketing script insertion
was performed. No new before/after LCP, live crawl or ranking result is claimed.

## Remaining launch gates

The implementation was self-reviewed against the approved plan. A separate
independent code/security review has not been performed in this tranche and is
still required before a production pilot. No production security claim follows
from this synthetic prototype.

Owner design approval was subsequently received September 18, 2026. Provider,
legal, processor, hosting, retention and budget decisions in READINESS.md remain
open. The next test-only backend slice is documented in `services/catalog_review/`.
Authentication, tenant isolation, durable jobs, managed secrets, file scanning,
real intake forwarding and restore/deletion drills still require implementation.

The local server remains running for owner review. Only this new preview
directory and its decision/test documents were added by this implementation.
