# Buyer-intent SEO/GEO preview

Prepared September 16, 2026. **Approved and deployed to production** at
https://spacemusic.io/ (immutable deployment https://02276b90.spacemusic-a6n.pages.dev).
See `PUBLISH-LOG.md` and `RELEASE-BASELINE.md` for the promotion checks. The
preview-preparation history below is retained and is not the current release state.

Preview: https://9b4782a6.spacemusic-a6n.pages.dev/

Branch alias: https://codex-buyer-intent-20260916.spacemusic-a6n.pages.dev/

Artifact: `tmp/buyer-intent-v2-20260916`. Manifest: `manifest-v2.json`.

Baseline: approved whole-site preview https://db999946.spacemusic-a6n.pages.dev/,
`tmp/quiet-site-seo-v4-20260916`. All previous design, label article and Duetti
work remains. The earlier buyer-intent v1 preview is superseded because its
listing-card SSR descriptions were stale; use v2 only.

Production remains https://spacemusic.io/ with the verified artifact
`tmp/typeform-intake-release-v3-20260915`. `marketing/RELEASE.md` is unchanged.
No Git commit or push, production deployment, backend change, DNS change,
Typeform change, email or real test lead was made in this batch.

## Review pages

- [Sale versus loan](https://9b4782a6.spacemusic-a6n.pages.dev/compare/catalog-sale-vs-catalog-loan/): corrected unsupported multiples/rates, tax assumptions, risk/control assertions and universal loan recommendation; added advance distinction and label cash-flow workflow.
- [Partial versus full sale](https://9b4782a6.spacemusic-a6n.pages.dev/compare/partial-sale-vs-full-sale/): corrected automatic control/buyback/premium assumptions; defined actual interests, future exclusions and hypothetical retained income.
- [Independent catalog owners](https://9b4782a6.spacemusic-a6n.pages.dev/for/independent-artist-catalog-owner/): direct buyer, all genres, evidence preparation and label-specific scope; no invented customer success, buyer network, loan product or legal-advice promise.
- [Label funding guide](https://9b4782a6.spacemusic-a6n.pages.dev/blog/independent-record-label-funding-options/): retained from the previously approved preview and linked from the refreshed pages.

`STRATEGY.md` contains the business brief, 20 candidate searches in five groups,
current result observations, source URLs, data limits, internal links, fixed
proposed AI prompts and equal-period measurement plan. This is not a complete
sitewide fact-check: the existing selling guide and other legacy persona and
comparison claims remain queued for a separate reviewed batch.

## Exact scope

Three detailed copy refreshes plus 54 other pages receiving only title/summary
references, shared CTA corrections, or the creator directory's all-genre copy.
The manifest logs each actual replacement and source-file hash. The three
detail pages' FAQs now use native details, with answers present in raw HTML,
runtime data and matching FAQ schema. No special AI schema or fake ratings.

The source sitemap is byte-identical: 140 URLs. No new URL, removed route,
redirect, robots change, hosting-policy change, image, font or stylesheet.
`llms.txt` gains a curated decision-resource section while retaining all prior
text. It remains plain text. No ranking or citation uplift is claimed.

Old assets are retained. Seventeen active modules are versioned with revision
`50f4feb4050e`. The complete output has 446 public files and two hosting-control
files. Only this complete snapshot is a candidate for a later approved release.

## Verification completed

- `test-buyer-intent.mjs`: 4,633 checks pass, covering all 138 HTML pages, original file hashes, old assets, all 140 sitemap URLs, preserved styles/links/forms, runtime import graph, detail and listing SSR/client parity, metadata and visible/schema FAQ consistency.
- Scenario/tracking/intake suite: 13 tests pass, including 47 calculator assertions and 11 Typeform/fallback tests. Simulated responses only; no production lead submissions.
- Local browser: all three refreshed routes checked at 390, 768 and 1440 pixels. One H1 each, correct canonical, Inter, no horizontal page overflow. Native FAQ opens with Enter and visible focus. A contextual Apply link opened the approved standalone guided form. No recorded browser errors in the inspected tab.
- Hosted v2: `/compare/` and `/for/` card summaries inspected after hydration. Mobile partial-sale page rechecked at 390 pixels, no overflow, keyboard FAQ works. Hosted loan page opens with the reviewed section headings.
- `check-growth-preview.mjs`: all 140 sitemap endpoints pass HTTP 200, canonical and preview noindex checks; 138 HTML pages, plain-text canonical/MIME headers pass.
- `verify-release-files.mjs`: all 446 public preview files exactly match the local v2 artifact. All 338 production files still exactly match the unchanged production artifact.
- Independent read-only content and code review: one P2 listing-SSR mismatch found in v1, fixed in v2; no remaining material findings in the scoped review. Reviewer independently reran 4,633 checks and bundled all 60 active modules.

No fresh three-run mobile LCP comparison, historical 33-case Apply browser
matrix, current Search Console baseline, Plausible conversion reconciliation
or cross-engine AI visibility scan is claimed. The new tests do not rename
themselves as those older or unperformed checks. Search Console requires login;
Semrush lacks API units. These limits remain explicit release/measurement gates.

## Reproduce

Use a fresh output directory and manifest; the builder fails if output exists.

```sh
MARKED_MODULE=/Users/emilsoujeh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/marked/lib/marked.esm.js node scripts/build-buyer-intent.mjs tmp/quiet-site-seo-v4-20260916 tmp/buyer-intent-review-rebuild marketing/buyer-intent-20260916/rebuild-manifest.json
node scripts/test-buyer-intent.mjs marketing/buyer-intent-20260916/rebuild-manifest.json
node --test marketing/funnel/scenario.test.mjs marketing/funnel/tracking.test.mjs marketing/typeform-intake/intake.test.mjs
node scripts/check-growth-preview.mjs https://9b4782a6.spacemusic-a6n.pages.dev 140
node scripts/verify-release-files.mjs tmp/buyer-intent-v2-20260916 https://9b4782a6.spacemusic-a6n.pages.dev
node scripts/verify-release-files.mjs tmp/typeform-intake-release-v3-20260915 https://spacemusic.io
```

For a preview update, verify Cloudflare identity and use a non-production
`codex/` branch in project `spacemusic`. Do not target `main` without explicit
production approval and the remaining release gates. Preserve the production
artifact above as rollback and check `marketing/RELEASE.md` again immediately
before any future promotion in case another release has occurred.
