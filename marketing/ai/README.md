# AI Resource Index

## Current Production Baseline

The subsequent application-navigation release is now live at
https://6b4a9ca6.spacemusic-a6n.pages.dev. Start future deployments from
`tmp/apply-navigation-20260907` (241 public files plus `_headers` and
`_redirects`), not an older snapshot. It preserves all AI text resources,
both hosting rules below, homepage social metadata and loading improvements.
See `marketing/RELEASE.md` and `marketing/application-route/README.md`.

## Latest Release: Canonical Header and Trailing-Slash Routing

Changed on 2026-09-07. Baseline: `tmp/lump-sum-income-20260907`.
Release: `tmp/llms-routing-20260907`.

The exact `/llms.txt` URL was already HTTP 200, plain UTF-8 text, without an
HTML wrapper. HTTP and www variants already redirected permanently to the
preferred HTTPS/non-www URL. Missing HTML viewport or canonical elements
were not defects in the text document.

The additional variant check reproduced a real routing issue: `/llms.txt/`
returned the homepage HTML with HTTP 200 and a homepage canonical. Query
variants of `/llms.txt` served identical text without a canonical hint.

This release adds two narrowly scoped Cloudflare Pages configuration files:

- `marketing/ai/cloudflare/_redirects`: exact 301 from `/llms.txt/` to
  `/llms.txt`, preventing the homepage fallback for that spelling.
- `marketing/ai/cloudflare/_headers`: `Link` with a canonical target of
  `https://spacemusic.io/llms.txt`, including query-string variants.

All 227 public files are byte-identical to the previous production release.
No content, HTML, runtime modules, metadata, sitemap, robots, forms or
existing host redirects changed. The release directory has 229 files:
227 public assets plus two hosting configuration files. Cloudflare parses
`_headers` and `_redirects`; they are not public asset URLs.

Build and checks:

```sh
node scripts/build-llms-routing-release.mjs VERIFIED_SOURCE FRESH_OUTPUT
node scripts/verify-release-files.mjs FRESH_OUTPUT
node scripts/check-llms-routing.mjs
node scripts/check-production-seo.mjs
```

The builder deliberately refuses an existing routing configuration, source
overwrite, nested output and existing output directories. Merge future
configuration changes explicitly rather than replacing these rules. The
general file verifier excludes only the two known hosting control files
from HTTP byte comparisons; routing/header behavior is tested separately.

Local Cloudflare runtime checks passed for GET/HEAD, query variants,
trailing-slash redirects, four bot user-agent strings, and seven unrelated
routes. All 227 public responses matched the snapshot. Four negative builder
safety checks passed. The original production check failed on the missing
header before the change, as expected.

This is a routing and canonicalization improvement, not evidence of a
5-15% link-equity gain or an E-E-A-T score increase. Domain Rank, referring
domain counts and spam-score claims in the supplied audit were not verified.
No Search Console indexing request was submitted for this text resource.

References checked 2026-09-07:

- https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls
- https://developers.cloudflare.com/pages/configuration/headers/
- https://developers.cloudflare.com/pages/configuration/redirects/

Published production deployment:
https://cc97c4cf.spacemusic-a6n.pages.dev

Production baseline immediately after this routing release (superseded above):
`tmp/llms-routing-20260907` (227 public files and two hosting configuration
files). Keep both configuration files in future releases. The previous
release remains at https://9569948a.spacemusic-a6n.pages.dev and
`tmp/lump-sum-income-20260907` for a controlled rollback if needed.

Post-release verification:

- All 227 public files match the release and prior production byte-for-byte;
  deployment uploaded zero new content assets, only the two configuration files.
- All 137 sitemap URLs pass canonical and robots checks.
- GET and HEAD return HTTP 200, `text/plain; charset=utf-8` and the exact
  canonical Link header for `/llms.txt`, including the tested query variant.
- GET and HEAD for trailing-slash variants return 301 and resolve to the
  unchanged text, not the homepage HTML.
- Existing HTTP and www redirects still resolve directly to the preferred URL.
- Four bot user-agent checks and seven unrelated routes pass. No llms.txt
  canonical header is applied to other checked routes.
- No other file in the release is an exact copy of llms.txt. This is a file
  inventory check, not a claim of discovering every possible external URL.

The temporary local test server was stopped after verification.

## Previous Release: Text Content Refresh

Published on 2026-09-07: https://spacemusic.io/llms.txt

Production deployment: https://0228269f.spacemusic-a6n.pages.dev

Source: `tmp/beatbread-vs-catalog-buyers-20260907` (219 files, verified against production).
Final release: `tmp/llms-refresh-20260907` (219 files).

Only `llms.txt` changed. All 218 other public files, including every HTML
page, runtime asset, sitemap, robots file, offer policy and brand-facts file,
remain byte-identical. Future snapshot-based website releases should start
from this release or a newer verified production snapshot, not an older
article release that contains the previous llms.txt.

## Content Decisions

`llms.txt` is the editable source for a curated site overview, not an HTML
landing page or a replacement sitemap. It contains 26 unique resource links,
preserves all eight previous key links and includes all five newly authored
articles. Every link uses the canonical production address.

The supplied draft had 76 unique links. The claimed
`/guides/partial-rights-explained/` guide returned a homepage-canonical
fallback, so it was not included. Market-index and conversion-intelligence
responses contained loading text rather than substantive static data; they
were not promoted as reliable data references. Older unreviewed comparison
and case-study claims were not amplified. No underlying page was removed.

The summary qualifies the initial-offer estimate as typically 5-7 business
days after relevant information is received, subject to review. Payment
depends on completing the agreement and transfer requirements. Genre
coverage, partial transactions, future works and illustrative valuations
are described without universal acceptance or payment promises.

The file follows the title, summary, background and H2 link-list pattern
described at https://llmstxt.org/. Secondary resources are in `Optional`.
It remains plain Markdown served as `text/plain; charset=utf-8`; HTML title,
viewport and canonical elements were not inserted into a text resource.

This is an information-access improvement, not a claim of increased AI
citations or rankings. Google does not require AI text files for AI Overviews
or AI Mode: https://developers.google.com/search/docs/appearance/ai-features

## Build and Verify

```sh
node scripts/build-llms-release.mjs VERIFIED_SOURCE FRESH_OUTPUT
node scripts/check-production-seo.mjs
```

The builder checks plain Markdown structure, described unique links, the
production origin, canonical destinations and retention of existing key
resources. It rejects output/source overlap, extra arguments and existing
output directories. It copies the source snapshot, replaces only llms.txt,
and verifies identical file inventories and bytes for every other file.

Verification for this release:

- All 219 deployed files match the final release byte-for-byte.
- All 26 resource links return HTTP 200 without redirects; HTML destinations
  have their expected canonical addresses.
- All 137 sitemap URLs pass the production canonical and robots checks;
  the sitemap itself is unchanged.
- Requests using Googlebot, ChatGPT-User and PerplexityBot user agents receive
  the exact updated text with HTTP 200 and no noindex response header. These
  are HTTP smoke tests, not evidence of actual indexing or AI citation.
- Negative tests reject source overwrite, nested output, extra arguments
  and existing-release overwrite without modifying the built release.
