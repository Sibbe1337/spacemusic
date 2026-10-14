# Catalog Review Conversion Preview

Status: preview only, September 17, 2026. Production is unchanged.

Preview: https://fa09e20b.spacemusic-a6n.pages.dev/

Review pages:
- https://fa09e20b.spacemusic-a6n.pages.dev/calculator/
- https://fa09e20b.spacemusic-a6n.pages.dev/sell/#label-or-catalog-owner
- https://fa09e20b.spacemusic-a6n.pages.dev/

## Baseline and artifact

Production remains https://55284dbb.spacemusic-a6n.pages.dev, publicly served at
https://spacemusic.io/. All 544 baseline public files were compared with live
production before implementation, with no differences. The immutable source is
`tmp/editorial-preview-v5-20260916`, as recorded in `marketing/RELEASE.md`.

Candidate: `tmp/conversion-preview-v3-20260917`.
Manifest: `marketing/conversion-20260917/manifest-v3.json`.
Revision: `281a5a73031a`.
Cloudflare Pages project: `spacemusic`; preview branch: `conversion-20260917`.
The earlier v1/v2 artifacts are superseded, not production candidates.

## Scope

The goal is to help existing visitors understand their next step, not to launch
another product or promise increased traffic.

- Homepage: move the existing artist/label explanation earlier and add links to
  the corresponding seller-page sections. Retain the original genre directory.
- Sell: add distinct artist/producer and independent-label paths, concrete
  preparation guidance, and links to existing supporting content. Clarify that
  a catalog purchase review is not a loan or grant application.
- Calculator: add a direct free-review action before the inputs. Move the full
  existing explanation out of the narrow result column without removing text.
  Add a short explanation of the review process beside the result.

Existing H1s, titles, descriptions, canonical tags, structured data, text and
links are retained. The complete sitemap still contains the same 141 URLs.
Apply, receiver settings, intake logic, tracking logic, pricing, Workers, email,
payments and backend are unchanged. No new lead fields or financial promises.

Server HTML and client-rendered content are updated together. A scoped 1,359-byte
gzipped stylesheet is added to marketing pages for client-navigation parity.
There are no new font, image or third-party requests. Previous assets remain in
the artifact; changed module references are versioned.

## Verification

- Preservation/build suite: 2,181 checks passed across 139 HTML pages, including
  all metadata, old text/link retention, Apply bytes, unchanged non-target DOM,
  calculator state/math, module compilation and the exact sitemap.
- Link audit: 6,665 internal links; zero link issues. Two pre-existing operational
  data-page orphans are unchanged: `/data/conversion-intelligence/` and
  `/data/space-market-index/`.
- Existing scenario/tracking/intake suites: all 13 tests passed, including 47
  arithmetic/boundary assertions, simulated failures, retries, duplicate clicks,
  attribution privacy and blocked analytics. No production form was submitted.
- All 581 candidate public files exactly match the immutable preview deployment.
- All 141 preview sitemap URLs return 200, retain production canonicals where
  HTML, and receive the hosting-level preview noindex header. No preview noindex
  was inserted into candidate HTML or production configuration.
- Six post-deployment production spot checks are byte-identical to the baseline:
  homepage, Sell, Calculator, Apply, sitemap and robots.
- Browser checks: desktop and 390/320px mobile widths, keyboard links and visible
  focus, homepage-to-label deep link, correct Apply handoff, client navigation
  and canonical updates, calculator invalid/empty/zero/share boundary states.
  1,000 x 12 x 4 x 50% renders $24,000.00. Derived-income scenario also checked.
  No horizontal overflow on checked layouts; no browser errors recorded.
- Server HTML preservation was checked directly. This is not a claim that the
  interactive calculator operates without JavaScript.

Reports: `test-results.json` and `live-checks.json` in this directory.

## Copy evidence

These first-party sources describe the existing offer and process; they do not
prove commercial outcomes or independent valuation accuracy:
- https://spacemusic.io/pricing.md
- https://spacemusic.io/apply/
- https://spacemusic.io/how-it-works/
- https://spacemusic.io/blog/music-catalog-sale-documents-checklist/
- https://spacemusic.io/compare/partial-sale-vs-full-sale/
- https://spacemusic.io/blog/independent-record-label-funding-options/

## Release gates and limitations

Owner approval is still required before production promotion. Before publishing,
recheck the production baseline, repeat preservation/live tests, and run three
comparable mobile performance tests on baseline and candidate. Investigate a
median LCP regression exceeding both 10% and 250 ms. No fresh three-run LCP
comparison was performed in this preview task, and small CSS size is not proof
of unchanged real-user performance.

Use only the complete candidate artifact for a later approved release. Preserve
the current complete production artifact for rollback. Do not deploy the
unrelated dirty backend/admin working tree or modify the Typeform Worker.

This task does not resolve pre-existing redirect/soft-404 findings, legacy
commercial-claim/author corrections, or the operational data-page orphans. It
does not establish higher rankings or more qualified leads. No new paid report,
brokerage fee, funding product, multilingual page, or acquisition claim is launched.

After an approved release, compare equal complete 28-day periods using consistent
page, query, country and device filters. Report actual received applications and
manually qualified applications separately; do not treat analytics events as
verified leads or infer conversion improvement from these interface changes.

## Reproduce checks

```sh
node scripts/test-conversion-preview.mjs marketing/conversion-20260917/manifest-v3.json
node --test marketing/funnel/scenario.test.mjs marketing/funnel/tracking.test.mjs marketing/typeform-intake/intake.test.mjs
node scripts/verify-release-files.mjs tmp/conversion-preview-v3-20260917 https://fa09e20b.spacemusic-a6n.pages.dev
node scripts/check-conversion-preview-live.mjs https://fa09e20b.spacemusic-a6n.pages.dev marketing/conversion-20260917/manifest-v3.json
```

The live checker deliberately requires a preview host and an unchanged production
baseline. It must not be reused as a production-promotion check after publication.
