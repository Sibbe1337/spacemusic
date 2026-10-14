# Calculator clarity: published September 9, 2026

Prepared September 9, 2026 after approval of the first calculator package.
The owner subsequently approved the final preview. The identical snapshot is
now published at https://spacemusic.io/calculator/.

Final preview: https://4dc7fbad.spacemusic-a6n.pages.dev/calculator/

Cloudflare Pages project: `spacemusic`.
Preview branch: `codex/calculator-review-20260909`, not `main`.
Verified release: `tmp/calculator-review-v2-20260909`.
Baseline: `tmp/journey-v4-20260907`, the September 8 verified release.
Production: https://3654f780.spacemusic-a6n.pages.dev.
Immediate rollback: `tmp/journey-v4-20260907`, https://6c66c5dd.spacemusic-a6n.pages.dev.

## Approved scope

- Replace the calculator headline's implied value promise with the seller's question.
- Explain that the calculation is hypothetical, not a market multiple or SPACE offer.
- Explain beside the multiple field that no multiple is needed to apply for an individual review.
- Add the clearly hypothetical $1,000 x 12 x 4 x 50% = $24,000 example and distinguish it from closing proceeds.
- Add one contextual link to the existing seller document checklist and one to the current offer/payment policy.
- Preserve the current design, questions, calculation, tracking, form receiver and other content.

The review approved [research package A and link edits 1 and 3](../research/2026-09-08/APPROVAL-AND-MEASUREMENT.md).
The valuation-guide edits, Royalty Exchange comparison, three workflow drafts,
other internal links, outreach and video are **not implemented** by this preview.

## What is preserved

The release retains all 299 prior public files plus `_headers` and `_redirects`.
It adds 34 versioned modules, for 333 public files. Existing assets remain
byte-identical; cached clients can still load them. Only the calculator has
changed content. Other HTML documents and module importers change version
references only. The complete Apply directory is byte-identical.

All 139 sitemap URLs, titles, descriptions, canonical tags, robots metadata,
structured data, fonts and stylesheets are preserved. The calculator keeps all
existing sections and FAQ subjects. Its H1 and approved explanatory paragraphs
are deliberately updated, so this is not a claim that every SEO-relevant word
is identical. Search-ranking outcomes cannot be guaranteed.

The Cloudflare preview returns `X-Robots-Tag: noindex` while retaining the
production canonical. This is preview-only hosting behavior: no production
noindex directive was added. The 299 public predecessor files were checked
against production immediately before publication, with no mismatches. After
publication all 333 live files match the approved snapshot.

## Implementation

Editable source: `marketing/funnel/Calculator.jsx`.

The new guarded builder compiles that source and resolves its shared-component
imports against the current calculator, not the original pre-journey Navbar and
Footer. It versions the changed calculator and all reachable importers using one
fingerprint for the existing cyclic module graph. It never overwrites old assets.
Only the calculator is prerendered, so the served HTML and client view agree.

The shared prerender helper now avoids appending a second copy of its existing
calculator no-JavaScript notice. This is a build-time idempotence correction,
not a change to the form or application runtime.

Rebuild into a fresh output directory, never over an existing release:

```sh
node scripts/build-calculator-review-release.mjs tmp/journey-v4-20260907 FRESH_OUTPUT FRESH_QA/module-map.json
node scripts/prerender-funnel-page.mjs FRESH_OUTPUT /calculator/
node scripts/check-calculator-review-release.mjs FRESH_QA/module-map.json
```

The baseline is deliberately pinned. If production changes later, rebase this
preview on that newer verified release instead of deploying the stale snapshot.
Do not deploy the repository root, the unpopulated `web` gitlink, or a prior
design preview. Research and QA files are not copied into the public snapshot.

## Verification

Evidence directory: `tmp/calculator-clarity-qa/`, final-run records under `v2/`.

Completed checks:

- Static release guard: all 139 sitemap URLs retained; metadata checked across 137 HTML sitemap pages; only approved calculator content changed; Apply and all old assets byte-identical; two new contextual links, no duplicated Apply actions.
- 47 calculation assertions: valid cases, empty/invalid inputs, zero, percentage boundaries and receipt deductions.
- Tracking privacy, attribution, deduplication, preview exclusion and failure isolation tests.
- Seven intercepted Formspree response cases: success, pending duplicate, errors, retry, missing/throwing analytics and blocked storage. No real receiver submission.
- Real Plausible-script interception test: one calculator pageview and one Apply pageview; expected safe events; no analytics events sent to Plausible.
- All 33 Apply-navigation checks on the Cloudflare preview, including the existing marketplace redirect, query/hash preservation, mobile, keyboard and no-JavaScript links. No retired form mounted or prefetched; no real submissions.
- All 333 preview public files match the candidate snapshot. Preview responds with noindex. All 299 production public files still match the prior production snapshot.

- Focused browser check passed at 320, 390, 768, 1024 and 1440 px: approved copy, no fabricated blank result, working checklist/policy links by keyboard, review without a multiple, and no-JavaScript content. Final results: `v2/preview/browser/results.json`.
- The full journey suite also passed at all five widths, including mobile-menu focus, unchanged form questions, policy links preserving input, confirmation focus and one intercepted submission. No real application was sent.

Do not infer received applications or qualified leads from mocked tests.

### Mobile performance

Lighthouse 13.4.1, installed Chrome headless, the existing mobile configuration,
three sequential runs before and three after, without other browser test runs
during measurement. Analytics event transmission was blocked.

| Page | Baseline median LCP | Preview median LCP | Change |
| --- | ---: | ---: | ---: |
| Calculator | 6,452.94 ms | 6,452.73 ms | -0.21 ms, effectively unchanged |

All six final-comparison runs scored 61/100. Reports are in `before/` and `v2/after/`. The agreed
regression threshold, a deterioration exceeding both 10% and 250 ms, passes.
The existing approximately 6.45-second lab LCP remains poor; this copy-only
package does not claim to solve performance or measure real-user Core Web Vitals.

### Test-harness corrections

The first new static importer check missed Vite's `assets/...` string prefix
when reversing version names; the production modules themselves were correct.
The check now resolves all observed literal prefixes and verifies the remaining
importer code exactly. It does not waive importer or SEO assertions.

The first focused browser check read required inputs after the server-rendered
Apply heading appeared but before the form mounted. It now waits for the real
form, as the existing navigation tests do. No Apply code was changed to pass it.

### Independent review and final wording

An independent code reviewer found no defects in the bounded first candidate.
The final candidate makes one additional text clarification: the multiple helper
names the `Request a free catalog review` button instead of saying it is below,
because desktop places it alongside the input card. A compiled-code comparison
confirmed this is the only change beyond version references between the two
calculator modules. Final static, performance and all five sequential preview
suites passed again; logs and timestamps are in `v2/preview/checks.json`.
The first preview remains available at `a3afdfa1.spacemusic-a6n.pages.dev` but is
not the final approval target.

The reviewer did not independently test a screen reader, CDN behavior or real
receiver delivery. Automated browser/byte checks cover the deployed preview;
real inbox delivery and lead quality are deliberately not claimed.

Re-run the final hosted checks sequentially with:

```sh
node scripts/check-calculator-review-preview.mjs https://4dc7fbad.spacemusic-a6n.pages.dev tmp/calculator-review-v2-20260909 tmp/calculator-clarity-qa/v2/preview
```

## Publication gate

The owner approved the preview and publication was completed September 9.
Authentication, baseline integrity and exact preview bytes were rechecked first.
The snapshot was deployed unchanged to `spacemusic` / `main`. The predecessor
is preserved, and `marketing/RELEASE.md` now points to the new verified release.

All five hosted verification suites passed again on production. Evidence:
`tmp/calculator-clarity-qa/v2/production/checks.json`, with per-suite logs,
screenshots and 33 Apply-navigation results beside it. The focused test uses
explicit production mode and rejects an HTTP or meta noindex directive.
The site-wide SEO check also passed for all 139 sitemap URLs, and the existing
plaintext/canonical-header routing checks passed. No real test application or
analytics conversion was transmitted.

See [publication log and follow-up dates](PUBLISH-LOG.md). Approval was limited
to this calculator package; the remaining research proposals stay drafts.

No outreach was sent, no video recorded, no customer information collected,
no qualified-lead count inferred and no ranking uplift claimed.
