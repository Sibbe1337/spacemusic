# Calculator refresh publication log

## Deployment

Owner approval: "Godkant" on the final calculator preview in this task.
Published: **9 September 2026**, Europe/Stockholm, approximately 08:01 CEST.
The exact second of cutover is not claimed; the approved response was observed
live at 06:02 UTC. Cloudflare lists the deployment as Production on `main`.

- Live page: https://spacemusic.io/calculator/
- Production deployment: https://3654f780.spacemusic-a6n.pages.dev
- Deployment ID: `3654f780-f2bf-4aed-9c37-404f3ac1dc08`.
- Approved preview: https://4dc7fbad.spacemusic-a6n.pages.dev/calculator/
- Release: `tmp/calculator-review-v2-20260909`.
- Immediate predecessor: `tmp/journey-v4-20260907`, https://6c66c5dd.spacemusic-a6n.pages.dev.

The existing dirty working tree was not committed, reset or reverted. Cloudflare's
displayed source revision does not capture the full working tree; the complete
snapshot and byte checks are the release authority for this direct upload.

## Changes and live verification

| Public URL | Published change | Verification |
| --- | --- | --- |
| https://spacemusic.io/calculator/ | H1 becomes "How much could your music catalog sell for?"; clearer hypothetical-scenario introduction; no-multiple-needed explanation using the actual review-button label; worked example; closing-proceeds distinction. | Approved copy verified in rendered and server HTML, with and without JavaScript, at five widths. Formula and validation unchanged. |
| https://spacemusic.io/calculator/ | Added one document-checklist link and one review/payment-policy link. | Both reached by keyboard; correct destination content observed. Existing Apply actions retained without duplication. |
| https://spacemusic.io/apply/ | No form or content change. | All files byte-identical to predecessor; all 33 navigation checks and seven intercepted receiver-response cases passed live. No real submission. |
| https://spacemusic.io/blog/music-catalog-sale-documents-checklist/ | No destination content change; gains a contextual link from the calculator. | HTTP 200, intended article and canonical, browser navigation passed. |
| https://spacemusic.io/pricing.md | No policy change; gains a contextual link from the calculator. | Policy readable in browser; unchanged bytes and working route. |
| Other existing URLs | No content or metadata edits; only necessary references to versioned modules change. | All 333 public files match the approved snapshot. All 139 sitemap URLs retained and production SEO checks passed. |

No image, new article, design change, outreach or video was published. The guide
and comparison corrections from the research pack remain unapproved drafts.

Completed live checks and logs:

- `tmp/calculator-clarity-qa/v2/production/checks.json`: all five suites passed.
- `browser/results.json`: five widths, empty result, review without a multiple, keyboard links, no-JS copy, production indexability.
- `apply/results.json`: 33 Apply-navigation checks.
- `form-mocks.log`: success, error, duplicate protection, retry, blocked analytics and storage; no real receiver traffic.
- `full-journey.log`: five widths, menus, policy links, confirmation and no-JS behavior.
- `release-bytes.log`: 333 matching public files, zero mismatches.
- Separate site-wide check: 139 sitemap URLs, canonical and robots metadata, no index-blocking HTTP headers.
- Separate plaintext routing check: `llms.txt` content type, canonical header, variants and unrelated routes preserved.

The preview remains noindex; production does not have that preview header.
These checks establish technical publication, not indexing, rankings, inbox
delivery, qualified applications or conversion uplift.

## Search Console baseline

Retained research baseline: **9 June-6 September 2026 inclusive, 90 complete
calendar days**. Property `sc-domain:spacemusic.io`, Web, all countries, all
devices, all appearances; exact page filter `https://spacemusic.io/calculator/`.

Page total: **140 clicks, 1,377 impressions, average position 14.1**. Do not
assign these totals to the visible query rows below.

| Exact page-filtered query | Clicks | Impressions | Average position |
| --- | ---: | ---: | ---: |
| how much is a music catalog worth | 0 | 136 | 7.8 |
| music catalog valuation | 5 | 27 | 17.6 |
| how to value a music catalog | 0 | 5 | 9.4 |

Source: [saved authenticated GSC observations](../research/2026-09-08/gsc-baseline.json),
[source report](https://search.google.com/search-console/performance/search-analytics?resource_id=sc-domain%3Aspacemusic.io&start_date=20260609&end_date=20260906&breakdown=query&page=!https%3A%2F%2Fspacemusic.io%2Fcalculator%2F).
This is the existing September 8 research record, not a fresh API export from
the publication turn. Matched 28/56-day baseline values have not yet been extracted.

## Matched-period follow-up

Search Console's API dates use PT (UTC-7/8), not Swedish calendar dates.
[Google's date-range specification](https://developers.google.com/webmaster-tools/v1/searchanalytics/query).
This deployment occurred before 07:00 UTC on September 9, therefore its PT
publication date is **September 8**. Exclude that mixed-version date.

| Comparison | Before, inclusive | After, inclusive |
| --- | --- | --- |
| 28 complete PT days | August 11-September 7, 2026 | September 9-October 6, 2026 |
| 56 complete PT days | July 14-September 7, 2026 | September 9-November 3, 2026 |

Wait for complete/final reported data through the end date, rather than running
the comparison while its last day is still in progress. Use the same property,
Web search type, exact page URL, all-country and all-device filters on both sides.
Freeze the three exact query rows above as a separate cohort. Keep brand queries
separate and keep slashless URLs separate from the selected slash URL. New country
or device segments require their own identically filtered baseline.

Report page totals and query rows separately, with clicks, impressions, CTR,
position, denominators and absolute changes. The 90-day prioritization baseline
is not a valid denominator for a 28-day uplift calculation. Query omissions and
small counts must remain explicit.

## Conversions and interpretation

Report analytics events, receiver-confirmed unique applications and manually
qualified applications separately. Missing analytics does not establish missing
leads; a mocked success event does not establish inbox delivery. Unreviewed leads
must not be classified as unqualified. No lead-quality data was retrieved here.

Confirm Plausible's site timezone before calculating conversion periods. Existing
measurement follow-ups described in `marketing/funnel/README.md` use their own
tracking cohorts; they are not automatically these GSC refresh comparisons.
This deployment is an annotation, not a new automation or a silently rescheduled
existing monitor. No new scheduled task was created.

The September 7 tracking/calculator changes and September 8 journey release are
additional interventions. A before/after change could reflect those releases,
query mix, traffic changes, seasonality or Google presentation, not just this
copy edit. Measured counts and possible explanations must be reported separately.

## Rollback

If a material release fault is found, redeploy the complete verified predecessor
`tmp/journey-v4-20260907` to Cloudflare Pages project `spacemusic`, branch `main`,
then verify its live bytes, SEO and Apply behavior. Keep both snapshots and their
hosting control files. Do not use an older design preview or the earlier
pre-journey funnel snapshot as the immediate rollback.
