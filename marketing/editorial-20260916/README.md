# Editorial blog release

Approved and published September 16, 2026, approximately 12:20 UTC.
Production: https://55284dbb.spacemusic-a6n.pages.dev.
Public blog: https://spacemusic.io/blog/.
Owner authorization: "The blog is approved". See `PUBLISH-LOG.md`.

Source: `tmp/wordmark-preview-v1-20260916`, the verified previous production
artifact in `marketing/RELEASE.md`, not an older redesign preview.
Candidate: `tmp/editorial-preview-v5-20260916`.
Manifest: `manifest-v5.json` records source hashes and versioned module mappings.

Verified preview: https://b5189220.spacemusic-a6n.pages.dev/blog/
Article example:
https://b5189220.spacemusic-a6n.pages.dev/blog/music-catalog-sale-documents-checklist/
Cloudflare project `spacemusic`, preview branch `editorial-20260916`.

## Scope

- Resources at `/blog/` becomes a text-led editorial index with five existing
  topic groups. All existing text, destinations and section anchors remain.
- All 14 blog articles use Inter, clearer title hierarchy, restrained dividers,
  a readable body measure, native collapsible contents and responsive layouts.
- Remove 57 rendered decorative image instances from the six legacy articles:
  hero photos, stock author portraits and repeated related/popular thumbnails.
  No fake replacement portraits, decorative generated imagery or new libraries.
- Move legacy sidebar widgets below the article. Related reading becomes text
  rows, with the original excerpts and links retained rather than clamped.
- Flag unverified legacy attribution; preserve original bios inside a clearly
  labelled disclosure. See `CONTENT-REVIEW.md` for outstanding corrections.
- Disable the inert legacy article-sidebar newsletter form with an explicit
  unavailable notice. The shared footer remains unchanged and was not audited
  as a newsletter integration in this package.
- Preserve keyboard-scrollable modern article tables, prevent labels breaking
  mid-word and keep overflow inside the table rather than the mobile page.
- Handle unavailable localStorage in the legacy cookie-banner component and
  preserve incoming fragment navigation instead of forcing the article top.

## Preservation and tests

`node scripts/test-editorial.mjs` checks all source-file hashes, all 139 HTML
heads, non-blog DOM equality, article body/heading/link preservation, native
contents, newsletter behavior, authored datasets, Resources SSR/runtime parity,
module syntax/import bundling and the complete internal-link graph.
Article body HTML, including existing table accessibility attributes, is intact.
The six legacy and eight authored templates are changed in both server HTML
and versioned client modules. Existing assets remain available for cached pages.

All 141 sitemap URLs, metadata, JSON-LD, canonical/robots settings, hosting
rules, logo, shared navigation/footer and standalone Apply assets are preserved.
The two pre-existing unlinked operational pages remain unchanged:
`/data/conversion-intelligence/` and `/data/space-market-index/`.

Scenario/tracking/intake suite: all 13 tests passed; no real application or
newsletter submission was sent. Browser QA covered all 14 client-rendered
articles at 381 CSS px, without horizontal page overflow, rendered photos or
console errors. Both TOC implementations support Enter-to-toggle and native
fragment links; the modern backlink returns to the Resources article section.
Desktop and narrow/tablet layouts were visually inspected.

Final v5 verification: 2,063 preservation/link checks pass; independent
read-only review reports no outstanding code findings. All 12 article table
wrappers retain their original accessibility attributes and body HTML.
Keyboard focus and ArrowRight scrolling were confirmed (scrollLeft 0 to 50).
Resources-to-Apply browser navigation opens the approved standalone guided
review page; no form was started or submitted.

Hosted checks pass: all 544 public files byte-match the candidate; all 141
sitemap addresses return HTTP 200 with preview noindex, the correct production
canonicals and no noindex baked into the HTML. Plain-text canonical headers
remain intact. `_headers` and `_redirects` were uploaded and checked through
their effects, not served as public files. The new stylesheet is 17,483 bytes
uncompressed and 2,674 bytes under local gzip; this is not a network timing test.
V1-v4 were intermediate artifacts, not production releases; use v5 only.

## Boundaries

This is not a content fact-check. Original legacy bylines and social-share
image metadata are retained and explicitly flagged for editorial correction.
No ranking, AI-citation, conversion or speed improvement is claimed.
The fresh three-run homepage mobile LCP comparison passed before publication:
2851 ms baseline median versus 2701 ms candidate. No regression exceeding both
10% and 250ms. See `PERFORMANCE.md` for individual reports and lab limitations.
The scoped stylesheet adds one request on non-blog pages to support SPA
navigation; their markup and appearance are otherwise unchanged.

No Worker, API, DNS, Typeform, Resend, database, payment or private catalog data
changes are part of this artifact. Unrelated worktree changes remain untouched.

## Publication

The owner approved this preview and the complete candidate was deployed to
`main`. Production was rechecked against the source hashes before publishing;
all 544 public candidate files and 141 sitemap routes were verified live after
release. Retain the full previous production artifact as immediate rollback:
`tmp/wordmark-preview-v1-20260916`, deployment
https://6984da7b.spacemusic-a6n.pages.dev, including `_headers` and `_redirects`.

Use the existing recorded Search Console baseline only as historical context;
no fresh search/lead retrieval was performed for this design task. Future
comparisons should use equal complete periods and identical filters, with
conversions reported separately from search metrics.
