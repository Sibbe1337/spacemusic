# Existing Comparison Refreshes

## Primary Wave: September 7, 2026

Page: https://spacemusic.io/compare/space-vs-primary-wave/

The supplied "Primary Wave Alternatives for Independent Artists With Smaller
Catalogs" draft was consolidated into this existing comparison, not published
as another overlapping blog post. Its URL, title, H1, description, canonical,
robots metadata and sharing metadata are preserved.

Editable content: `space-vs-primary-wave.json` in this directory.
Source notes: `marketing/competitors/catalog-funding.yaml` and
`competitor-profiles/primary-wave.md`.

### Editorial Changes

- Removed unverified celebrity transaction values and categorical exclusions
  of all small or independent catalogs. Primary Wave's services page also
  describes contemporary creators, not only legacy acquisitions.
- Removed the draft's unsupported $2,000 SPACE threshold and promised 3x-10x
  valuation range. Duetti's separately attributed public criteria are included.
- Distinguished initial review from payment, and free application/listing
  terms from an unqualified promise of zero transaction costs.
- Replaced universal creative-control and future-work guarantees with specific
  questions about rights, term, exclusions, and continuing responsibilities.
- Distinguished Limbo's funding products, Royalty Exchange's auction and
  historically described non-auction formats, and beatBread's limited revenue
  purchases from conventional loans or full catalog buyouts.
- Added a small-catalog preparation checklist and contextual links to the
  four relevant existing guides. The comparison discloses SPACE's interest
  and does not claim private-offer testing or a highest-paying buyer.

### Release Method

Verified baseline: `tmp/llms-refresh-20260907` (219 files, all matched live).
Candidate: `tmp/primary-wave-refined-20260907` (222 files).

Build and prerender checks:

```sh
node scripts/build-primary-wave-comparison.mjs tmp/llms-refresh-20260907 NEW_OUTPUT
PLAYWRIGHT_MODULE=/Users/emilsoujeh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs node scripts/test-primary-wave-comparison.mjs tmp/llms-refresh-20260907 NEW_OUTPUT
```

Use a fresh output directory. This is an explicitly guarded patch of the
verified marketing snapshot, not a rebuild from the root/backend repository.
The missing marketing source project must not be replaced with an old build.

Three versioned modules provide the data overlay, conditional comparison
renderer enhancements, and new entry. Old assets remain available for cached
clients. The original data module remains a dependency; its only other named
consumer, RelatedContent, reads comparison slugs, which are unchanged.
The other five comparison records are tested for deep equality.

The target now uses native expandable FAQs so the full answers are present
and accessible without JavaScript. The FAQ schema matches all seven answers.
Only this comparison receives the additional sections and scrollable-table
enhancement. No seller, admin, backend, forms, redirects or analytics changes
are part of this release.

### Local Verification

- All 134 other HTML pages are byte-identical after normalizing the versioned
  entry reference. Their content and metadata have not changed.
- All other original non-HTML files are byte-identical, including sitemap,
  robots, llms.txt, pricing.md, social images and original assets.
- All 137 sitemap URLs remain present; no URL was added or removed.
- Desktop and 390px/320px mobile checks pass, including table scrolling.
- All seven FAQ answers work with and without JavaScript.
- Nineteen existing routes and 22 internal link destinations pass.
- Client navigation into the comparison, onward to the lump-sum guide and
  to the application route passes. No form was submitted.
- No JavaScript errors or failed local assets were observed.

Evidence: `tmp/primary-wave-comparison-preview/checks.json` and screenshots.

Existing issue outside this content release: `/apply/` has a static H1 of
"We buy your music catalog." while its unchanged client-rendered application
module uses "Tell us about your catalog." The navigation test checks the
existing client behavior, not a newly introduced heading. Investigate the
broader static/client application consistency separately; this release does
not change either implementation.

Subsequently fixed by the dedicated 2026-09-07 navigation release. See
`marketing/application-route/README.md`; internal application links now load
the existing standalone `/apply/` page rather than the old SPA form.

### Production Verification

Published to the `spacemusic` Cloudflare Pages project on branch `main`:
https://2d196107.spacemusic-a6n.pages.dev

Baseline created by this release (see `marketing/blog/README.md` for the
subsequent lump-sum income update): `tmp/primary-wave-refined-20260907`.
The previous release remains available
at https://0228269f.spacemusic-a6n.pages.dev and in
`tmp/llms-refresh-20260907` for a controlled rollback if needed.

- All 222 production files match the release byte-for-byte.
- The production SEO checker passes all 137 sitemap URLs, canonical and
  robots checks. Existing routes were not added, removed, or redirected.
- Googlebot and Twitterbot receive HTTP 200, full updated HTML and FAQs,
  with no noindex response header.
- Live mobile checks pass for the eight-row table, seven FAQs, canonical,
  no page-wide overflow and navigation to the existing application.
- No forms were submitted. The live browser reported no JavaScript errors.

Production screenshot: `tmp/primary-wave-comparison-preview/mobile-live.png`.
These are technical regression checks, not a guarantee of search rankings.
