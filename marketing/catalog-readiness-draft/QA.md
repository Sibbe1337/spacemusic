# Draft package quality review

9 September 2026. Local concept only. No release, checkout, customer contact or
real catalog evidence was involved.

## Completed checks

| Area | Result | Evidence |
| --- | --- | --- |
| Illustrative calculations | 11 unit tests pass. Includes 216-row reconciliation, missing versus zero months, adjustments, duplicate references, currency/period validation, percent bounds, scenario share applied once, cent rounding and all break-even states. | `model.test.mjs` |
| Browser layout | Four pages at 320, 390, 768, 1024 and 1440 px. No horizontal page overflow or browser errors. | `qa/browser-results.json`; desktop/mobile screenshots |
| Accessibility automation | Eight axe-core 4.10.3 scans, at 390 and 1440 px across four pages. No violations or incomplete results in the selected WCAG 2 A/AA, WCAG 2.1 AA and best-practice checks. | `qa/browser-results.json` |
| Interaction | Keyboard skip link, FAQ expansion and sample navigation; live owner-cost updates, invalid/empty inputs, negative contribution and unreachable break-even tested. | `check-browser.mjs` |
| Without JavaScript | Offer, full report, sources and initial economic comparison remain readable. The owner view explicitly says edited fields do not recalculate without JS. | `qa/browser-results.json` |
| Reduced motion | Reveal animation disabled; no essential information depends on motion. | `qa/browser-results.json` |
| Privacy and local serving | No remote runtime requests, cookies, localStorage or sessionStorage. No customer/payment form or file input. POST returns 405; traversal probes 404; server binds only loopback and sets noindex. | `qa/browser-results.json`; `serve.mjs` |
| Local links | 36 same-origin link checks passed, including report PDF, evidence CSVs and anchors. | `qa/browser-results.json` |
| Public references | All 12 public destinations returned HTTP 200, including one redirected Konsumentverket URL. This is route verification, not full endorsement of each page. | `qa/package-results.json` |
| PDF | Four tagged A4 pages, four embedded static Inter instances, synthetic labels on every page, no input fields, no local/test-server URI annotations. Text, table layout, page breaks and public links checked. | `check-pdf.py`; `qa/verified-pdf-1.png` through `qa/verified-pdf-4.png` |
| Production isolation | All 333 live public files still match the previously approved release `tmp/calculator-review-v2-20260909`; zero mismatches. All 139 sitemap addresses retained. | `qa/package-results.json` |
| Independent source review | Two findings raised, fixed and subsequently confirmed resolved; all 11 model tests also passed under reviewer verification. | Summary below |

## Issues caught and corrected

The initial PDF spilled a footer onto a fifth page. Print layout now fits the
four designed sheets. Static Inter instances replaced variable-font PDF output
to reduce embedding complexity and remove font warnings. The web design still
uses the owner's requested local Inter font.

The final local-link cleanup briefly exposed the hidden skip-link text in print,
introducing a blank page. Cleanup is now scoped to report content, preserving
the hidden navigation element. A print-visibility assertion and the four-page
PDF check confirm the corrected export.

The first cost display exposed a floating-point half-cent discrepancy. Each
modeled monetary line now rounds to cents, and the displayed total reconciles.
The README and assertions use the same rounded values.

The independent reviewer caught an impossible break-even being labeled as zero
minutes, and English shared content inheriting the Swedish page language. The
model/UI now distinguish unreachable, exact zero-budget and zero-hourly-cost
cases. Shared English elements explicitly declare their language. Regression
tests cover both fixes; the reviewer confirmed resolution.

Automated accessibility checks caught an unnamed price-region landmark, a
disclosure outside landmarks and the sample's skipped heading level. Semantic
regions and a logical heading hierarchy were corrected, without hiding content.

A test initially used a text locator that excludes `noscript` descendants. The
actual notice rendered correctly; the test now directly checks the visible
`noscript > p` and its text. It does not waive the no-JavaScript requirement.

## What these checks do not establish

- Not a complete WCAG or PDF/UA certification; no live screen-reader user session or physical iPhone/Safari test was performed.
- No production performance, ranking or conversion improvement is claimed. This is a separate local concept.
- No real Stripe payment, refund, webhook, receipt, bank payout or customer inbox delivery was tested. PAYMENTS.md retains the unexecuted test matrix.
- No legal opinion, VAT determination, privacy compliance approval, reviewer qualification or secure customer-storage capability is established.
- The synthetic CSV arithmetic is not an importer for arbitrary real royalty statements. Format review and human reconciliation remain prerequisites.
- No willingness to pay, paid order, real report delivery time, qualified lead or positive business margin was measured.

## Final artifacts and regeneration

The local preview is under `preview/`. The final PDF is
`output/pdf/space-catalog-readiness-sample.pdf`; matching synthetic evidence is
in `output/pdf/space-catalog-readiness-evidence/`. The downloaded preview PDF is
byte-identical. `qa/package-results.json` records the current PDF SHA-256 and
byte count. Re-run package verification after regenerating the PDF.

The generated artifacts contain no actual customer data. Keep future real
reports and populated pilot registers out of the repo and outside this preview.
