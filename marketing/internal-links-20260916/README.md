# Internal linking cleanup

Status: published September 16, 2026, approximately 10:54 UTC, as part of the
approved wordmark release https://6984da7b.spacemusic-a6n.pages.dev.
Public Resources: https://spacemusic.io/blog/.
Final production artifact: `tmp/wordmark-preview-v1-20260916`.
See `../identity-20260916/PUBLISH-LOG.md` for current live verification and
the fresh three-run mobile performance comparison. The evidence below describes
the internal-link layer before the separate logo update.

Verified immutable preview: https://d5cefefb.spacemusic-a6n.pages.dev/blog/

Preview alias: https://internal-links-20260916.spacemusic-a6n.pages.dev/blog/

Source of truth: `tmp/buyer-intent-v2-20260916`, the verified production release
https://02276b90.spacemusic-a6n.pages.dev. All 446 public files were compared
with https://spacemusic.io before work began and matched. The unapproved
selling-guide rewrite is NOT included.

## Observations and results

| Static HTML audit | Before | Preview |
| --- | ---: | ---: |
| HTML pages | 138 | 139 |
| Sitemap addresses | 140 | 141 |
| Internal links to nonexistent routes | 93 | 0 |
| Placeholder anchors | 274 | 0 |
| Missing fragment targets | 0 | 0 |
| Sitemap HTML pages unreachable from home | 19 | 2 operational exceptions |
| Maximum reachable HTML page depth | 4 | 3 |

The 93 missing-route links were not necessarily HTTP 404s: the host served the
homepage fallback for tested nonexistent paths. Counting HTTP 200 responses
alone would have missed the problem. `before.json` and `after.json` include
the complete route graph, incoming links, page depth and individual findings.

The two exceptions are `/data/conversion-intelligence/` and
`/data/space-market-index/`. They are existing operational dashboard shells,
not useful public navigation destinations. Their URLs, content, metadata and
sitemap entries remain unchanged. This does not make them private. Any access
restriction, removal or indexing-policy change needs a separate decision.

## Site architecture

Primary navigation stays limited to How It Works, Sell, Calculator, Resources,
and Request a free catalog review. The focused standalone Apply header stays
unchanged.

| Destination | Job | Next level |
| --- | --- | --- |
| `/how-it-works/` | Explain the review process | Apply and supporting guides |
| `/sell/` | Browse catalog genres | Existing genre pages |
| `/calculator/` | Model a hypothetical sale scenario | Review and valuation guidance |
| `/blog/` | Find guides, articles and reference material | Six guides, fourteen articles, tools and reference pages |
| `/for/` | Find guidance for an owner or creator situation | Eight existing persona pages |
| `/compare/` | Compare buyers and deal structures | Existing comparison pages |
| `/glossary/` | Explain music-rights terms | Existing glossary entries |
| `/streaming-rates/` | Find platform royalty guidance | Seven platform pages |
| `/apply/` | Request the existing free review | Unchanged guided Typeform/explicit short-form alternative |

Resources is a real server-delivered page and client route at the previously
missing `/blog/` address. It uses the approved quiet design. No article is
removed, renamed or rewritten. Earlier articles are labelled as previously
published material, not newly verified evidence. The existing case study and
market report have NOT been fact-checked by this navigation project.

Header and footer link groups come from `navigation.mjs`. The footer surfaces
the existing topic hubs rather than listing every page. Article topic labels
now lead to relevant existing guidance instead of nonfunctional query filters.
Back-to-articles links return to the Resources article section.

This follows Google's recommendation to use crawlable `<a href>` links with
useful, descriptive anchor text and contextual destinations:
https://developers.google.com/search/docs/crawling-indexing/links-crawlable.
Three-click depth is a usability target here, not a Google ranking guarantee.

## Destination repairs

| Old route | Destination |
| --- | --- |
| `/guides/partial-rights-explained` | `/compare/partial-sale-vs-full-sale/` |
| `/guides/music-catalog-tax-guide` | `/guides/how-to-sell-music-rights/#tax-implications` |
| `/streaming-rates/spotify` | `/streaming-rates/spotify-2026/` |
| `/streaming-rates/apple-music` | `/streaming-rates/apple-music-2026/` |
| `/streaming-rates/youtube-music` | `/streaming-rates/youtube-music-2026/` |
| `/streaming-rates/amazon-music` | `/streaming-rates/amazon-music-2026/` |
| `/streaming-rates/tidal` | `/streaming-rates/tidal-2026/` |
| `/streaming-rates/deezer` | `/streaming-rates/deezer-2026/` |
| `/streaming-rates/soundcloud` | `/streaming-rates/soundcloud-2026/` |

Each old path, with and without a trailing slash, receives an exact 301.
Links point straight to the destination rather than relying on the redirect.
Known public links use canonical slash conventions. External links, email
links and unknown routes are not guessed or silently rewritten to home.
Unconfigured social icons are decorative instead of fake clickable `#` links.

## Safeguards and validation

- All 140 existing sitemap addresses are retained in their original order; only `/blog/` is added.
- Existing titles, metadata, canonicals, structured data, H1/H2 headings, every paragraph and forms are compared with production fixtures.
- Both server HTML and the active client module graph are updated. Original assets remain available and all changed modules have new versioned names.
- The application module, original receiver, Typeform configuration, Worker, backend, DNS and email settings are unchanged.
- `/blog/` is added to the existing public-path attribution allowlist. No new analytics event or personal-data field is added.
- Native navigation is retained for Apply, text documents and fragment links; post-mount fragment restoration handles the legacy app's loading fallback.
- Mobile and tablet navigation accommodates the fourth item. Escape closes it and returns focus to the menu button.
- The preservation suite passes 6,918 assertions, parses 62 active modules and bundles the full entry graph without writing a replacement production bundle.
- All 135 existing marketing headers and the new Resources header share the same navigation in server HTML and the client. Apply and the two operational dashboards retain their existing header treatment.
- Resources uses managed JSON-LD so schemas do not duplicate or leak into other pages after client navigation; its Open Graph type is `website` in both render paths.
- The 13 existing scenario, tracking and Typeform intake tests pass. Simulated receiver tests do not send leads.
- The static audit checks all 6,660 internal links, destination files and fragment IDs. It finds zero link issues and the two documented reachability exceptions.
- Independent read-only review found three issues in earlier candidates (legacy headers, schema ownership, Open Graph type). All were fixed; the targeted recheck reports no remaining findings.

Browser checks cover Resources desktop/mobile, 390px menu fit, 820px tablet
navigation, Escape/focus, article return links, the tax-section jump, all seven
calculator platform links, Spotify navigation, and the standalone Apply screen.
The final candidate also passes Resources-to-Sell schema cleanup and in-app
browser back/forward checks. The final Chrome recheck was interrupted by its
connection closing; the earlier responsive checks used the same CSS and menu
behavior. The temporary viewport reset was attempted but the connection was
already unavailable.
No application or newsletter was submitted. This is not a full interactive
journey test of every page, a conversion audit or an indexing/ranking result.

Hosted verification on the immutable preview passes all 141 sitemap addresses:
HTTP 200, production canonical URLs and preview-only noindex headers. Both
text-document MIME/canonical headers pass. All 490 public files match the local
release byte-for-byte. All 18 alias variants return the intended 301 location.
Production was separately rechecked against all 446 baseline public files and
still matches. Hosting control files are not publicly downloadable, so their
effects were checked via response behavior rather than byte comparison.

## Reproduce

Use a new output directory for every build:

```sh
node scripts/build-internal-links.mjs tmp/buyer-intent-v2-20260916 tmp/internal-links-release-20260916 marketing/internal-links-20260916/manifest.json
node scripts/test-internal-links.mjs marketing/internal-links-20260916/manifest.json
node scripts/audit-internal-links.mjs tmp/internal-links-release-20260916 marketing/internal-links-20260916/after.json
node scripts/check-growth-preview.mjs https://d5cefefb.spacemusic-a6n.pages.dev 141
```

## Release decision

The owner subsequently approved deployment ("approved and delpoy"). The layer
was published together with the new wordmark. Its rollback snapshot is
the complete `tmp/buyer-intent-v2-20260916` directory, including `_headers` and
`_redirects`. Do not use an old design preview or the unapproved guide draft.

The combined preview and production were checked for byte parity, sitemap
coverage, canonical/robots behavior and exact redirects. Public destinations
were opened. Preview noindex remains at the preview hosting layer only.

No ranking gain, AI-visibility improvement or conversion lift is claimed.
The existing Search Console baseline remains in
`marketing/buyer-intent-20260916/RELEASE-BASELINE.md`. Record the actual publish
date and use equal complete reporting periods and the same page,
query, country and device filters. The final candidate's fresh three-run mobile
LCP comparison passed: 2701 ms median before and after. Reports and final live
verification are recorded in `../identity-20260916/PUBLISH-LOG.md`.
