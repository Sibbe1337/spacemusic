# Editorial blog production release

Owner authorization: September 16, 2026, "The blog is approved".
Approved preview: https://b5189220.spacemusic-a6n.pages.dev/blog/.
Published approximately 12:20 UTC to Cloudflare Pages project `spacemusic`,
production branch `main`.

- Complete artifact: `tmp/editorial-preview-v5-20260916`.
- Immutable production: https://55284dbb.spacemusic-a6n.pages.dev.
- Public blog: https://spacemusic.io/blog/.
- Manifest: `marketing/editorial-20260916/manifest-v5.json`.
- Immediate rollback: `tmp/wordmark-preview-v1-20260916`, immutable deployment https://6984da7b.spacemusic-a6n.pages.dev.

## Scope and preservation

The approved Resources index and all 14 article layouts are published. Text-led
presentation replaces visible stock imagery; six legacy articles carry an
explicit unverified-contributor disclosure. Their content is not represented as
fact-checked. No fabricated replacement authors or testimonials were added.

All 141 sitemap URLs, article text/headings/links, metadata, canonicals, robots,
JSON-LD, hosting rules, shared identity and standalone Apply remain. Existing
assets are retained for cached pages. Non-blog markup/layout is unchanged,
apart from the scoped stylesheet reference and versioned client imports.
No multilingual pages, SEO research recommendations, backend, Worker, DNS,
Typeform settings, email or payment changes were deployed.

## Fresh checks

- `node scripts/test-editorial.mjs`: PASS, 2,063 preservation/link assertions, 14 articles, 6 legacy templates, 57 rendered decorative images removed; no internal-link issues. The two pre-existing operational orphan pages are unchanged.
- Scenario/tracking/intake suite: PASS, 13 tests, including simulated success/failure, retries, duplicate prevention and blocked analytics/storage. No real form, newsletter or customer email was submitted.
- Starting production: all 532 public files matched the wordmark source. Eight transient fetch failures on the first pass were individually retried and byte-matched; there were no content mismatches.
- Approved preview: all 544 public files byte-matched the candidate immediately before publication.
- Live production: all 544 public files byte-match the candidate after publication, zero mismatches.
- Live SEO: all 141 sitemap URLs return 200 and pass canonical/robots checks, with no preview noindex. `robots.txt` points to the production sitemap.
- `pricing.md`: 24 routing/MIME/canonical/content checks passed against this artifact. Existing llms.txt routing, MIME, canonical headers and text checks also passed.
- Hosting control files `_headers` and `_redirects` were uploaded with the complete artifact and checked through response behavior, not downloaded as public files.

The documented preview browser matrix remains applicable because the deployed
files are identical: all 14 articles at narrow width, table keyboard scrolling,
native contents, no visible stock photos and correct Apply handoff. Fresh
pre-release inspection also confirmed the approved index, desktop document
checklist and its responsive layout at a 390px viewport setting.

Post-release browser inspection confirmed the public Resources index, an old
lo-fi article with the visible unverified-contributor disclosure and no stock
hero, and the document checklist. The live article review CTA opens the approved
standalone Typeform-start/short-form-fallback Apply page; neither form was
started. The checklist's backlink returns to `/blog/#articles`. No console
errors were captured in this live browser check. The temporary mobile viewport
was reset. This is a scoped live smoke test, not a fresh rerun of every prior
browser case.

## Performance gate

Six fresh PageSpeed Insights homepage mobile reports, matching displayed device,
throttling and Lighthouse/browser versions. Median LCP **2851 ms before versus
2701 ms candidate**. The regression gate is not triggered. See `PERFORMANCE.md`
for all runs, report links and outliers. No real-user speed gain or article
performance benchmark is claimed. The pre-existing contrast warning remains.

## Search baseline and follow-up

Same-day authenticated research baseline:
`marketing/multilingual-research-20260916/GSC-BASELINE.md`.
June 16-September 13, 2026, 90 complete days; domain property, Web, all countries,
devices and appearances, no page/query filter: 152 clicks, 8,831 impressions,
1.7% CTR and average position 14. This release reuses that recorded baseline;
it did not fetch an additional Search Console report or claim blog-specific
query performance from sitewide totals.

Exclude release day. Compare September 17-October 14 against August 20-September
16, retrieving complete pre-period data when available. Optional 56-day windows:
September 17-November 11 versus July 23-September 16. Use identical explicit
page/query/country/device filters and split brand/non-brand. Report blog pages
separately, and report verified submissions/manual qualification independently
from search traffic. Multiple September 16 releases overlap, so later changes
cannot be causally assigned to the blog design alone. No conversion, ranking
or AI-citation effect is verified and no automatic follow-up was scheduled.

## Rollback and remaining editorial work

Redeploy the complete wordmark snapshot to project `spacemusic`, branch `main`,
including both hosting control files. Do not change Typeform responses or the
separate notification Worker. No git-wide reset, unrelated build or old design
preview is part of rollback.

`CONTENT-REVIEW.md` still records unresolved authorship, case-study evidence
and legacy factual claims. Existing social-share image metadata is retained.
The design approval is not approval to invent authors, evidence, local service
availability or translated claims. Those corrections require a scoped review.
