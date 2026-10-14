# Homepage Social Preview

## Current Production Baseline

The subsequent homepage loading release is live at
https://bf29e6f0.spacemusic-a6n.pages.dev. Start future deployments from
`tmp/home-fonts-preload-20260907` (239 public files plus `_headers` and
`_redirects`). It preserves the social metadata fixes below and only changes
homepage resource loading. Details: `marketing/performance/README.md`.

## Latest Release: Metadata Lifecycle

Published on 2026-09-07 to the `main` production branch of Cloudflare Pages
project `spacemusic`: https://d32bc49f.spacemusic-a6n.pages.dev

Baseline immediately after this release: `tmp/homepage-social-metadata-20260907`.
It contains 231 files: 229 public assets and the two Cloudflare hosting
configuration files `_headers` and `_redirects`. Both configuration files
must be retained in future releases. This release starts from the verified
`tmp/llms-routing-20260907` snapshot; all 227 prior public files matched
production before the change.

The supplied September 3 audit no longer described the live site. The image
already existed, with one description and one of each Twitter tag in both
raw and rendered HTML. The two theme-color tags have mutually exclusive
light/dark media queries and are intentional, not duplicate values for the
same condition. No new image or unsupported "cash in days" copy was added.

Browser tests reproduced two narrower lifecycle defects:

- The homepage omitted the SEO component's `type` prop, inheriting its
  `article` default after rendering despite `website` in the raw HTML.
- The five optional image metadata tags existed only in static homepage
  HTML. Article-to-home client navigation lost them when article Helmet
  metadata unmounted.

The guarded builder sets `type: "website"` only on the homepage and gives
its existing image type, dimensions and alt descriptions to React Helmet,
following the existing article template. The initial HTML marks these five
tags as Helmet-owned to prevent duplicate tags on first render. The shared
SEO component and article types are unchanged.

Only two new content-addressed runtime files were added. The 134 HTML files
using the entry script now reference its new version; homepage HTML also
has the five ownership attributes. All page bodies, titles, descriptions,
canonical URLs, image bytes, schema, robots, sitemap, text resources and
hosting rules remain unchanged. Every previous runtime asset is retained
for clients with cached pages. All HTML is verified byte-identical after
normalizing only the new entry reference and the five ownership attributes.

Commands:

```sh
node scripts/build-homepage-og-type-release.mjs VERIFIED_SOURCE FRESH_OUTPUT
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node scripts/check-homepage-social.mjs [ORIGIN]
node scripts/verify-release-files.mjs FRESH_OUTPUT [ORIGIN]
node scripts/check-llms-routing.mjs [ORIGIN]
node scripts/check-production-seo.mjs
```

The browser test failed on production before the change and passes locally
and on production after it. Checks cover raw and rendered metadata, one
applicable theme color per color scheme, 390px mobile, article-to-home
navigation and browser back/forward, unchanged article metadata, no page
errors, PNG dimensions/MIME, and three sharing-bot user-agent strings.
All 229 public production files match the release byte-for-byte. All 137
sitemap URLs pass the existing canonical/robots checks. The llms.txt GET,
HEAD, query, slash and host-redirect checks also pass. Four negative builder
tests reject overwriting the source, nested output, existing releases and
extra arguments without modifying the source or release.

These are HTTP/browser smoke tests, not external Facebook, X or LinkedIn
cache refreshes or evidence of actual crawler visits. The supplied claim of
a 5-10 point AI-visibility improvement is not substantiated by these checks.

The type-only intermediate `tmp/homepage-og-type-20260907` was not deployed
and must not be used as a production baseline. Rollback baseline, if needed:
`tmp/llms-routing-20260907`, https://cc97c4cf.spacemusic-a6n.pages.dev.

References checked 2026-09-07:

- https://ogp.me/
- https://html.spec.whatwg.org/multipage/semantics.html#meta-theme-color

## Original Image Release

`space-catalog-v1.png` is the Open Graph and Twitter sharing image for
https://spacemusic.io/. It was created with the built-in imagegen tool on
2026-09-07, then copied unchanged into this directory.

The reference release is Cloudflare Pages deployment
`4b543c5c-7649-4bfc-8c3f-1735ce8cdee1`. Its 194 deployed files were compared
byte-for-byte against `/tmp/spacemusic-apply-unified.YP7hR5` before preparing
the update. The production marketing frontend source is not populated in
the repository's `web` directory, so this change uses the verified static
release and a reproducible, guarded transformation.

Run `node scripts/apply-homepage-social-preview.mjs SOURCE OUTPUT` against
that release, using a new output directory. This adds the image metadata
to the homepage HTML and the image prop to its existing SEO component.
New content-addressed JavaScript filenames avoid serving a cached old
homepage module. Other pages only receive the new entry-script reference;
their content, metadata and canonical URLs are preserved. Original assets
remain available to clients loading a previously cached page.

The optional image dimensions and alt text follow https://ogp.me/.

## Published Release

Published to the `main` production branch of Cloudflare Pages project
`spacemusic` on 2026-09-07:
https://74de3d36.spacemusic-a6n.pages.dev

The generated PNG is 1730 x 909 pixels (approximately 1.90:1), 1,174,697
bytes. Metadata uses its actual dimensions; no cropping or resizing was
applied. The public asset is https://spacemusic.io/social/space-catalog-v1.png.

Verification passed:

- All 197 production files match the prepared release byte-for-byte.
- All 132 sitemap URLs pass the existing production SEO check.
- Page bodies, canonical URLs, robots.txt, sitemap.xml and GEO files are
  preserved; other HTML changes only update the entry-script reference.
- Browser checks pass after hydration and navigation from home to sell and
  back, with one image/card tag each and no JavaScript page errors.
- Requests using Twitterbot and Facebook crawler user agents receive the
  image metadata in the initial HTML; the PNG returns 200 with image/png.

## Generation Prompt

Create one final production Open Graph social sharing card for SPACE at
spacemusic.io, a direct buyer of revenue-generating independent music
catalogs. This is a flat 2D brand typography asset, not a website mockup or
screenshot. Canvas MUST have a wide 1200 by 630 pixel layout, aspect ratio
1.90476:1, full bleed. Visual identity: warm pale cream background #F8F3EC,
ink #1A1A1A, strong clean blue #2A74FF. Swiss editorial typography, modern
Inter-like sans serif, clear hierarchy, generous whitespace, restrained
design, crisp rasterized vector-quality text. Match this existing SPACE
brand mark if using one: a tiny 3 by 3 grid of rounded squares with varying
opacity, next to the word SPACE. Place small brand wordmark SPACE at upper
left. Main very large left-aligned headline in two lines, exactly: 'Sell
your' on line 1 and 'music catalog.' on line 2, black first line, blue
second line. Under it a single compact support line exactly 'One direct
buyer. One clear offer.' At bottom left small readable text exactly 'Free
evaluation. No obligation.' At bottom right small readable text exactly
'spacemusic.io'. Leave at least 64px outer safe margins for all text at this
target resolution. A restrained abstract rhythm or record groove motif may
appear only on the far right, blue and cream, not competing with the text.
No gradients, no 3D, no shadows, no pill buttons, no card UI, no dashboards,
no people, no stock photos, no Lovable icon, no extra claims or unprovided
text. All English spelling must be exact. Export as a single landscape PNG
suited for a large social link preview.
