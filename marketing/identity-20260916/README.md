# SPACE wordmark and navigation release

Owner approved production deployment on September 16, 2026 ("approved and delpoy").
Candidate: `tmp/wordmark-preview-v1-20260916`.
Immutable preview: https://83918285.spacemusic-a6n.pages.dev/.
Manifest: `manifest-v1.json`. Final publication evidence belongs in `PUBLISH-LOG.md`.

## Scope

Custom monochrome vector SPACE lettering replaces the grid icon/wordmark in
136 marketing headers, 138 footers and the standalone Apply header. A cut in
the A gives the mark its own detail without effects or external font requests.
Desktop width is 140px; below 768px it is 122px. The home link retains its
accessible name and a 44px-high target. The SVG is decorative inside that link;
real SPACE text remains available to assistive technology and without CSS.
Reduced-motion preferences are respected. Favicons and schema logos are unchanged.

The candidate includes the separately tested internal-link cleanup from
`marketing/internal-links-20260916/manifest.json`, not the unapproved guide rewrite.
It restores Resources at `/blog/`, repairs 93 nonexistent-route links, replaces
274 placeholder social anchors with decorative icons, and aligns site navigation.
No article body, existing heading, metadata, offer, form question or receiver is
changed by the wordmark layer. No backend, DNS, email or payment deployment.

## Verification

- `node scripts/test-wordmark.mjs`: 2,919 assertions; all 139 HTML documents are identical to the link candidate after reversing only declared brand and asset-version changes. All old non-HTML files are byte-identical.
- `node scripts/test-internal-links.mjs marketing/internal-links-20260916/manifest.json`: 6,918 assertions; titles, descriptions, canonical URLs, JSON-LD, paragraphs, forms and prior sitemap URLs preserved.
- Full active entry graph bundles successfully; changed modules are versioned and old assets retained.
- Audit: 6,660 internal links, no missing destination/fragment, placeholder or noncanonical link. All public marketing pages reachable within three clicks; the two pre-existing operational dashboard exceptions remain unchanged.
- Existing scenario, attribution and Typeform intake suite: 13 passing tests. Receiver tests are simulated, not production leads.
- Preview: all 532 public files byte-match; all 141 sitemap URLs return 200 with production canonicals and preview-only noindex; all 18 added redirect variants return their intended 301 destinations.
- Browser: new logo renders in the homepage, Resources, Sell and standalone Apply. Desktop 1440px and 1060px, mobile 390px and tablet 820px checked; no horizontal overflow. Mobile menu opens, Escape closes and restores focus. Actual content viewport excludes the scrollbar.
- Independent read-only code review: no findings. No application or newsletter was submitted.

Mobile lab comparisons, production checks and rollback details are recorded in
`PUBLISH-LOG.md`. This does not claim a ranking, lead-quality or conversion effect.

## Reproduce

```sh
node scripts/build-wordmark-preview.mjs NEW_OUTPUT NEW_MANIFEST
node scripts/test-wordmark.mjs NEW_MANIFEST
node --test marketing/funnel/scenario.test.mjs marketing/funnel/tracking.test.mjs marketing/typeform-intake/intake.test.mjs
```

The builder reads the approved internal-link manifest. It must use a fresh
output directory and does not mutate its source. Retain the complete previous
production artifact `tmp/buyer-intent-v2-20260916`, including `_headers` and
`_redirects`, for rollback to Cloudflare Pages project `spacemusic`, branch `main`.
Never substitute an old design preview or overwrite the separate Typeform Worker.
