# Canonical Application Navigation

## Diagnosis

Reproduced on production on 2026-09-07:

- A direct request to `/apply/` serves the current standalone seller application
  from `apply/index.html` and `apply/assets/index-1Mu13qxd.js`.
- The marketing SPA still mapped `/apply` to `ApplicationForm-DRjdd2L1.js`.
  React Router intercepted internal links and showed the older nine-question
  form without making a document request. A trailing slash in the DOM href
  alone did not fix the route.
- The old behavior was also documented in `marketing/comparisons/README.md`.

## Narrow Fix

`CanonicalApplication.mjs` replaces only the marketing route's lazy component.
It performs a document navigation to `/apply/`, retaining the query string and
hash. `location.replace` replaces the already-pushed marketing route, so Back
returns to the referring page without a redirect loop.

The standalone application's HTML, JavaScript, CSS, form endpoint and all
business behavior are unchanged. No leads are submitted by the checks.

The guarded builder versions the route bridge and the entry module, then changes
only the entry script reference in 134 marketing HTML files. All body bytes,
titles, descriptions, canonical URLs, schema, styles, prior assets, sitemap,
robots, AI text resources and hosting rules remain unchanged. Old assets remain
available for cached pages. An already-open old page needs a refresh.

The unchanged navbar still prefetches the retired component on hover. The
regression test distinguishes this harmless import from mounting the component;
it verifies that the old form never renders, even briefly. Removing that
prefetch requires a separate dependency-graph rebuild, not rewriting immutable
asset URLs in this narrowly scoped hotfix.

## Build and Verify

Source: `tmp/home-fonts-preload-20260907`, verified byte-for-byte against all
239 public production files before building.

Candidate: `tmp/apply-navigation-20260907`, 241 public files plus `_headers`
and `_redirects`.

Preview: https://4f79ee6b.spacemusic-a6n.pages.dev

Published to production on 2026-09-07, project `spacemusic`, branch `main`:
https://6b4a9ca6.spacemusic-a6n.pages.dev

Current release and rollback guidance: `marketing/RELEASE.md`.

Production verification passed: all 33 navigation cases, all 241 public files
byte-identical to the release, all 137 sitemap URLs with canonical/robots checks,
homepage social metadata before/after rendering, and AI-resource routing tests.
Browser errors: zero. Test application submissions: zero.

```sh
node scripts/build-apply-navigation-release.mjs VERIFIED_SOURCE FRESH_OUTPUT
node scripts/verify-release-files.mjs RELEASE_DIRECTORY ORIGIN
node scripts/check-apply-navigation.mjs ORIGIN OUTPUT_DIRECTORY
node scripts/check-homepage-social.mjs ORIGIN
node scripts/check-llms-routing.mjs ORIGIN
node scripts/check-production-seo.mjs
```

Browser scripts need `PLAYWRIGHT_MODULE` pointing to an installed Playwright
module and Chrome available. The routing test fails against the old production
release and passes locally, on the preview and on production after the fix.
It covers 33 cases: navigation and
calls to action on seven page types, browser back/forward, query/hash retention,
the existing marketplace redirect, direct slash/non-slash entry, mobile menu,
required fields, and no-JavaScript links.

## Pending Design Work

`tmp/clarity-preview-*` and their release candidates were built before this fix.
They are unfinished, are not production releases, and must not be deployed as
they stand. Rebuild that design from the newest verified production release to
retain this routing fix. Do not mix the visual redesign into this hotfix.
