# Pricing Routing Publish Log

Published: September 10, 2026, approximately 09:07 UTC (11:07 Europe/Stockholm).
Authorization: owner requested production after review of the isolated draft.
Method: Cloudflare Pages direct upload to existing project `spacemusic`, branch
`main`. No Git commit, push, repository replacement or backend deploy.

## Versions

- Source and rollback: `tmp/calculator-review-v2-20260909`.
- Previous production: https://3654f780.spacemusic-a6n.pages.dev.
- Candidate and current release: `tmp/pricing-routing-release-20260910`.
- Preview: https://4fa0530e.spacemusic-a6n.pages.dev, branch
  `codex/pricing-routing-20260910`.
- Production: https://a74ea86c.spacemusic-a6n.pages.dev.
- Production deployment ID: `a74ea86c-06fc-4c74-a53d-5db6453907ec`.
- Public resource: https://spacemusic.io/pricing.md.

## Exact Changes

`_headers`: append an exact `/pricing.md` canonical Link response header pointing
to `https://spacemusic.io/pricing.md`. `_redirects`: append the exact permanent
redirect `/pricing.md/ /pricing.md 301`. Preserve the existing llms.txt rules.

All 333 public files and all 139 sitemap URLs are unchanged byte-for-byte.
Cloudflare reported zero new content uploads for both preview and production.
There is no new pricing page, Markdown HTML wrapper, paid offering, design,
form behavior, internal-link edit, sitemap edit or private source document.
`/pricing` and `/pricing/` retain their previous fallback behavior; their wider
routing behavior was explicitly outside this approved change.

## Verification

Before publishing, the source snapshot matched all 333 public production files
and the account/project/production branch were verified. The fresh guarded
build preserved all public files and changed only the approved hosting rules.

Hosted preview passed 21 pricing-routing cases, existing llms.txt checks, all
333 public file comparisons and all 33 Apply-navigation cases. Noindex headers
were confirmed on the homepage, pricing resource, Apply and calculator.

Production passed:

- 24 targeted pricing cases: GET/HEAD, query variants, exact slash redirect,
  query retention, four user-agent strings, nine unaffected paths and three
  HTTPS/non-www normalization cases.
- The existing llms.txt canonical and routing regression suite.
- All 333 public HTTP file comparisons, zero mismatches.
- All 139 sitemap URL status, applicable HTML canonical and robots checks.
  The dedicated pricing test covers the non-HTML canonical that the generic
  checker skips. Production has not inherited preview noindex.
- All 33 Apply-navigation cases, zero browser errors, no retired form mounted,
  no test submissions. Includes mobile menu, back/forward, query/hash retention,
  required-field validation and the no-JavaScript destination.

Browser results: `tmp/pricing-routing-qa-20260910/preview-apply/results.json`
and `tmp/pricing-routing-qa-20260910/production-apply/results.json`.
Analytics were blocked during the browser checks. No leads or conversions were
generated. Previous full form-response and performance suites were not rerun
because no public asset changed; their old results are not new measurements.

## Rollback and Measurement Limits

If a routing regression is established, redeploy the complete immediate
predecessor `tmp/calculator-review-v2-20260909` to `spacemusic` / `main`, retaining
its `_headers` and `_redirects`, then verify public URLs and Apply again.

This is a technical response-header/routing correction. No Search Console
inspection, Google-selected canonical, new traffic baseline, ranking gain,
link-equity percentage or conversion improvement was measured in this release.
The earlier search baseline remains in `marketing/calculator-review/PUBLISH-LOG.md`;
do not attribute later movement to this small change without comparable evidence.
