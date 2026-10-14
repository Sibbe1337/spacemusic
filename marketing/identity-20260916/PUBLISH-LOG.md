# Wordmark and internal-links release

Owner authorization: September 16, 2026, "approved and delpoy".
Approved candidate: `tmp/wordmark-preview-v1-20260916`.
Preview: https://83918285.spacemusic-a6n.pages.dev/.
Published September 16, 2026, approximately 10:54 UTC, to Cloudflare Pages
project `spacemusic`, production branch `main`.
Immutable production: https://6984da7b.spacemusic-a6n.pages.dev.
Public site: https://spacemusic.io/.

Live verification completed immediately after deployment: all 532 public files
byte-match the tested artifact; all 141 sitemap URLs pass status, canonical and
robots checks; no preview noindex on production. All 18 new redirect variants
pass. Existing pricing.md (24 checks) and llms.txt content/MIME/canonical/redirect
checks pass. Hosting control files were verified through their effects rather
than downloaded. Homepage, Sell, Resources and standalone Apply were inspected
in a real browser, including client navigation. No form/newsletter was submitted.

## Content and controls

532 public files plus `_headers` and `_redirects`; 139 HTML pages; 141 sitemap
URLs. All 140 existing sitemap addresses remain; `/blog/` is the only addition.
Custom five-path wordmark in header/footer/Apply; full scope and checks in
`README.md` and `../internal-links-20260916/README.md`.

The previous live release was byte-verified immediately before deployment:
446 public files, zero mismatches. Complete rollback artifact:
`tmp/buyer-intent-v2-20260916`, immutable deployment
https://02276b90.spacemusic-a6n.pages.dev.
Redeploy it to project `spacemusic`, branch `main`, including both hosting
control files. Do not alter Typeform responses or its separate notification Worker.

## Fresh mobile performance gate

PageSpeed Insights UI, September 16, 2026, approximately 10:48-10:53 UTC.
Emulated Moto G Power, slow 4G, initial page load, Lighthouse 13.4.1,
HeadlessChromium 151.0.7922.173. Three requested reports per version.
Exact values read from the reports' visible score-calculator links.

| Version / run | LCP ms | TBT ms | CLS | Report |
| --- | ---: | ---: | ---: | --- |
| Before 1 | 2851 | 0 | 0 | https://pagespeed.web.dev/analysis/https-spacemusic-io/i8twx9ktzs?form_factor=mobile |
| Before 2 | 2701 | 0 | 0 | https://pagespeed.web.dev/analysis/https-spacemusic-io/6k65qo4zgi?form_factor=mobile |
| Before 3 | 2701 | 2 | 0 | https://pagespeed.web.dev/analysis/https-spacemusic-io/dc653f76ef?form_factor=mobile |
| Candidate 1 | 2701 | 0 | 0 | https://pagespeed.web.dev/analysis/https-83918285-spacemusic-a6n-pages-dev/hum16h08zp?form_factor=mobile |
| Candidate 2 | 2701 | 0 | 0 | https://pagespeed.web.dev/analysis/https-83918285-spacemusic-a6n-pages-dev/xxey1ppt6s?form_factor=mobile |
| Candidate 3 | 2701 | 0 | 0 | https://pagespeed.web.dev/analysis/https-83918285-spacemusic-a6n-pages-dev/unvwkyc4ty?form_factor=mobile |

Median LCP: **2701 ms before and after**. The >10% AND >250ms regression
threshold is not triggered. These are lab results, not visitor measurements;
hosting origins differ, and PageSpeed exposes no CrUX field data. The preview's
SEO score of 66 is expected from its noindex header; production must be verified
separately. Both versions retain an existing contrast warning (96 accessibility).
No real-user speed improvement or ranking effect is claimed.

## Search and conversion baseline

Use the same-day authenticated Search Console baseline in
`../buyer-intent-20260916/RELEASE-BASELINE.md`: latest complete available 90 days
June 16-September 13, 2026; Web, all countries/devices/search appearances;
152 clicks, 8,831 impressions, 1.7% CTR, average position 14.
Latest 28 complete days August 17-September 13: 34 clicks, 2,231 impressions.
This is an inherited recorded baseline, not a new Search Console retrieval.

Exclude deployment day. Compare September 17-October 14 with August 20-September
16 (28 days each), retrieving the complete pre-period when available. Optional
56-day comparison: September 17-November 11 versus July 23-September 16.
Keep the exact page/query/country/device filters identical, split brand and
non-brand, and do not substitute impressions for search volume. The several
September 16 releases overlap; changes cannot be attributed to the logo alone.
Report verified submissions and manually qualified leads separately. No new
Plausible reconciliation, conversion lift or AI-visibility effect is verified.
