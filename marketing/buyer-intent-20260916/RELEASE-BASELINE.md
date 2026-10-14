# September 16 release baseline

Captured before promotion of approved artifact `tmp/buyer-intent-v2-20260916`.

## Search Console

Source: authenticated Search Console UI for `sc-domain:spacemusic.io`, captured
September 16, 2026. Last update shown: five hours ago. The default seven-day
chart ended September 13; the latest 90 complete available dates were therefore
June 16 through September 13 inclusive. Search type Web; all countries, devices
and search appearances; no page or query filter except the exact-page check
explicitly identified below. Impressions are NOT keyword search volume.

| Complete period | Clicks | Impressions | CTR | Average position |
| --- | ---: | ---: | ---: | ---: |
| 2026-06-16 to 2026-09-13 (90 days) | 152 | 8,831 | 1.7% | 14 |
| 2026-08-17 to 2026-09-13 (28 days) | 34 | 2,231 | 1.5% | 24.8 |

Selected **page totals** from the 90-day Pages table, not joined to property-level queries:

| Path | Clicks | Impressions | Position |
| --- | ---: | ---: | ---: |
| /calculator/ | 127 | 1,306 | 14.7 |
| /guides/music-catalog-valuation-2026/ | 14 | 5,945 | 8.7 |
| / | 4 | 152 | 10.4 |
| /compare/major-label-vs-independent/ | 3 | 274 | 34.2 |
| /guides/music-catalog-valuation-2026 (no slash) | 2 | 303 | 9.6 |
| /compare/space-vs-royalty-exchange/ | 0 | 111 | 8.3 |
| /guides/best-music-rights-buyers-2026/ | 0 | 53 | 11.5 |
| /how-it-works/ | 0 | 43 | 5.1 |
| /apply/ | 0 | 27 | 33.0 |
| /compare/space-vs-duetti/ | 0 | 19 | 12.9 |
| /compare/partial-sale-vs-full-sale/ | 0 | 9 | 10.3 |
| /guides/how-to-sell-music-rights/ | 0 | 6 | 4.0 |

The exact-page filter for `/guides/how-to-sell-music-rights/` confirmed 0 clicks,
6 impressions, 0% CTR and position 4 for the same 90 days. Its Queries table
exposed **No data**. Do not invent a buyer query, search volume or strong ranking
evidence from six impressions. Its refresh is justified by factual corrections
and its central internal-link role, not demonstrated query demand.

## Mobile lab comparison

PageSpeed Insights UI; mobile; emulated Moto G Power; Lighthouse 13.4.1;
HeadlessChromium 151.0.7922.173; slow 4G; initial page load. Three independently
requested reports per version, September 16 at approximately 09:06-09:12 UTC.
No CrUX field data was exposed. These are lab results, not visitor measurements.

| Version / run | LCP ms | TBT ms | CLS | Report |
| --- | ---: | ---: | ---: | --- |
| Production before 1 | 3001 | 0 | 0 | https://pagespeed.web.dev/analysis/https-spacemusic-io/bql0pke1br?form_factor=mobile |
| Production before 2 | 2851 | 0 | 0 | https://pagespeed.web.dev/analysis/https-spacemusic-io/webo2d5s6h?form_factor=mobile |
| Production before 3 | 3001 | 1058 | 0 | https://pagespeed.web.dev/analysis/https-spacemusic-io/l1mmf2fri9?form_factor=mobile |
| Approved preview 1 | 2701 | 0 | 0 | https://pagespeed.web.dev/analysis/https-9b4782a6-spacemusic-a6n-pages-dev/g9aumoncmw?form_factor=mobile |
| Approved preview 2 | 2851 | 1149 | 0 | https://pagespeed.web.dev/analysis/https-9b4782a6-spacemusic-a6n-pages-dev/cu30zsh4t6?form_factor=mobile |
| Approved preview 3 | 2701 | 0 | 0 | https://pagespeed.web.dev/analysis/https-9b4782a6-spacemusic-a6n-pages-dev/rxzcup0d9p?form_factor=mobile |

Median LCP: 3001 ms before, 2701 ms candidate (300 ms lower, approximately 10%).
The regression gate (>10% AND >250 ms slower) is not triggered. One large TBT
outlier occurred in each variant; both median TBT values are zero. Do not claim
a proven real-user speed improvement. Hosting origin differs between production
and preview. Preview SEO score 66 is explained by deliberate noindex; production
must be independently checked to have no preview noindex. Both variants scored
96 for automated accessibility, with an existing contrast warning still open.

## Follow-up method

Read final data after each period is complete. Exclude deployment day. Compare
2026-09-17 through 2026-10-14 with 2026-08-20 through 2026-09-16 (28 days each),
and optionally 2026-09-17 through 2026-11-11 with 2026-07-23 through 2026-09-16
(56 days each). The complete pre-period must be retrieved later because data
currently stops on September 13. Keep Web, exact page, query, country and device
filters identical; retain slash variants separately unless intentionally grouped.
Separate branded queries from non-branded, hidden queries from zero-demand, and
search impressions from keyword volume. Record site totals and page-filtered
queries separately. Conversions and manually qualified applications need their
own evidence; this release does not verify Plausible reporting or lead quality.
No ranking, lead-volume or AI-citation effect has yet been measured.
