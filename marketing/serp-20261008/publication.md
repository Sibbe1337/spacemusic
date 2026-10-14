# Publication Receipt

- Approval: owner's explicit "publicera" on October 8, 2026.
- Published: October 8, 2026, approximately 07:10 UTC (09:10 Europe/Stockholm).
- Public origin: https://spacemusic.io/.
- Deployment: https://2a01bd95.spacemusic-a6n.pages.dev.
- Target: Cloudflare Pages `spacemusic`, production branch `main`.
- Artifact: `tmp/serp-preview-v3-20261008`, revision `ef3cecf6bba1`.
- Immediate rollback: `tmp/growth-preview-v1-20260930`, https://29e7801c.spacemusic-a6n.pages.dev.

## Published Changes

| Public URL | Change | Live status |
| --- | --- | --- |
| https://spacemusic.io/guides/music-catalog-valuation-2026/ | Answer-first explanation, contextual multiples, review/calculator links, offer comparison and FAQs | Verified |
| https://spacemusic.io/calculator/ | Clear scenario explanation and current application guidance; calculation and events unchanged | Verified |
| https://spacemusic.io/compare/space-vs-royalty-exchange/ | Neutral sourced comparison, historical Direct Listings caveat, related resources and FAQs | Verified |
| https://spacemusic.io/guides/how-to-sell-music-rights/ | Factual corrections, readable explanations and FAQs; ten topic anchors preserved | Verified |
| https://spacemusic.io/blog/independent-record-label-funding-options/ | Answer-first funding-route explanation; distinguish SPACE purchases from loans and advances | Verified |

Sources and scope are recorded in `README.md` and `BRIEF.md`. No new routes,
images, invented case studies, financing products or ranking promises.

## Verification

Before release, provider deployment listing confirmed September 30 deployment
`29e7801c` remained production. All 599 public baseline files matched live byte
for byte. The approved candidate passed 3,061 checks and Jev's gate (374 new
sentences; four source/context exceptions; zero blocking flags).

After release, `verify-release-files.mjs` checked all 639 public files against
spacemusic.io: zero mismatches. `_headers` and `_redirects` are hosting
configuration, not publicly retrievable files; the candidate preserves them
byte for byte and Wrangler reported both uploaded.

`EXPECTED_SITEMAP_URLS=144 node scripts/check-production-seo.mjs` passed:
all 144 destinations, canonical and robots checks clean. No preview noindex
header was applied to the changed public pages.

`check-serp-live.mjs` verified all five pages at 390px and 1440px: static/client
metadata and complete schema parity, no horizontal overflow, keyboard FAQ,
navigation to the existing Apply and its fallback. Calculator example:
1,000 x 12 x 4 x 50% = 24,000. Receipt at
`qa/live-results.json`, timestamp `2026-10-08T07:11:20.284Z`.

No browser errors. No test leads or synthetic analytics were sent; tests
blocked every non-GET request and all non-static destinations. Real production
form submission and email delivery were deliberately not exercised.

The prior complete artifact remains available for rollback using the same
Pages project and `main` branch. No backend, portal, DNS, API key, receiving
address or third-party account configuration changed. No Git commit or push.

## Search Console Baseline And Follow-Up

Source: supplied `spacemusic.io-Performance-on-Search-2026-10-08.zip`.
Search type: Web. Export filter: Last 3 months, no other recorded filters.
Daily chart: July 6 through October 5, 2026 (92 complete dates), 128 clicks,
7,279 impressions, calculated CTR 1.76%. Exact final 90 days (July 8 through
October 5) have 125 clicks and 7,105 impressions; page summaries are still
92-day aggregates and must not be relabelled as 90-day metrics.

| Page | Clicks | Impressions | CTR | Average position |
| --- | ---: | ---: | ---: | ---: |
| Valuation guide | 12 | 3,568 | 0.34% | 9.31 |
| Calculator | 97 | 1,207 | 8.04% | 14.67 |
| Royalty Exchange comparison | 0 | 117 | 0% | 8.21 |
| Selling-rights guide | 2 | 68 | 2.94% | 15.19 |
| Label-funding article | 0 | 37 | 0% | 12.68 |

For this release exclude the partial publication day, October 8. Compare
October 9-November 5 with September 10-October 7, using equal 28 complete
Search Console reporting dates and identical page/query/country/device/Web
filters. The provided export ends October 5, so the pre-release baseline is
missing October 6-7; obtain a new export before making that comparison. Respect
the source report's reporting timezone rather than silently mixing it with
Stockholm calendar days. Retrieve page-filtered query exports; do not join
unrelated page and query aggregate tables.

Traffic and conversions must be reported separately. No new Plausible outcome,
received-lead count or manual qualification records were verified in this
publication task. Small counts and subsequent edits limit causal attribution.
There is no measured ranking, CTR or conversion uplift yet. Controlled mobile
lab LCP remains poor despite no regression beyond the agreed threshold; see
`performance/summary.json`.
