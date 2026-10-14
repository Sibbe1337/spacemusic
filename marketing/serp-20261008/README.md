# Five-page SEO / seller-journey release

Status: **published October 8, 2026**, following the owner's "publicera" approval.
Public site: https://spacemusic.io/.
Deployment: https://2a01bd95.spacemusic-a6n.pages.dev.
See `publication.md` for live verification, rollback and measurement windows.

Candidate: `tmp/serp-preview-v3-20261008`, revision `ef3cecf6bba1`.
Baseline and immediate rollback: `tmp/growth-preview-v1-20260930`, the previous
verified production artifact. Versions v1/v2 are superseded, not release candidates.

## Reviewed Changes

| Existing destination | What changed | Why |
| --- | --- | --- |
| `/guides/music-catalog-valuation-2026/` | Concise answer, immediate calculator/review links, correctly contextualized market multiples, offer-comparison explanation, native FAQ | Highest-impression selected page; distinguish survey perceptions from individual offers |
| `/calculator/` | Clear scenario formula and current guided-application explanation | Highest-click selected page; no formula, preset, tracking or form changes |
| `/compare/space-vs-royalty-exchange/` | Neutral comparison, all-genre positioning, historical Direct Listings caveat, current-terms questions, document/offer links, native FAQ | Correct the auction-only simplification and unsupported speed/price advantages |
| `/guides/how-to-sell-music-rights/` | Correct NPS, ownership, partial-sale, tax and future-work claims; preserve ten topics/anchors; readable paragraphs; native FAQ; contextual related resources; shorter description | Remove contradictory buyer advice from both body and structured answers |
| `/blog/independent-record-label-funding-options/` | Direct answer and route-selection section with TOC and sale-process link | Clarify existing-catalog purchase versus advances/loans and avoid advertising a nonexistent SPACE financing product |

The selected H1s and canonical URLs are unchanged. No new articles, routes,
lead forms, paid products, testimonials or market multiples were invented.
See `BRIEF.md` for supplied Search Console metrics and attribution limits.

## Sources And Scope

Sources checked October 8, 2026. Provider pages establish their descriptions,
not independently tested private offers or future availability.

- [Duetti / Billboard H2 2026 index](https://www.duetti.co/music-finance-index-h2-2026): industry-panel perceptions and age-band bases; not verified universal transaction prices.
- [WIPO valuation guidance](https://www.wipo.int/en/web/business/ip-valuation): income versus market methods and identifiable assets/income.
- [Royalty Exchange seller process](https://royaltyexchange.com/how-auctions-work-sellers): marketplace role, bidding, listing agreement and transfer stages.
- [Royalty Exchange Direct Listings announcement](https://royaltyexchange.com/blog/introducing-direct-listings-giving-artists-more-control-over-their-catalog): historical non-auction format; current availability explicitly requires confirmation.
- [US Copyright Office](https://www.copyright.gov/register/pa-sr.html) and [ownership/transfer provisions](https://www.copyright.gov/title17/92chap2.html): composition/recording distinction and transfer scope.
- [Hipgnosis 2021 report glossary](https://www.hipgnosissongs.com/wp-content/uploads/2021/09/210705AnnualReportRNS.pdf): a published publishing-specific NPS definition, not a universal master-income definition.
- [IRS Publication 544](https://www.irs.gov/publications/p544): classification and limited self-created-composition election; individual tax advice still required.
- [beatBread label offering](https://www.beatbread.com/label) and [FAQ](https://www.beatbread.com/faq): provider's advance description, not a SPACE product.
- SPACE's offer policy and Apply were checked in the verified release artifact. No new operational promise or eligibility minimum was introduced.

## Validation

`qa/results.json`: **3,061 automated checks**, including file invariants,
144 sitemap destinations, existing internal destinations, canonical/H1
preservation, duplicate metadata, complete static/hydrated schema equality,
FAQ answer/schema consistency, 320/390/768/1440px, JavaScript on/off,
keyboard disclosures/Apply navigation and scenario mathematics/invalid inputs.

Apply is byte-identical. All existing non-HTML assets, robots, redirects,
headers, sitemap, policy and tracking scripts are preserved. New module names
propagate through imports without overwriting old assets. Other HTML differs
only in references to those versioned modules. The manifest hashes every
baseline file. This is technical preservation evidence, not a ranking guarantee.

No real submissions or analytics events were sent. The local preview server
adds `noindex` and a response-only CSP blocking external connections, frames
and form submissions. Those preview headers are not written into the release.

An independent agent identified and rechecked three fixes: all schema scripts
must survive serialization, two closing CTAs must distinguish a purchase review
from calculator output, and Jev must receive heroes outside `<main>`. Its v3
recheck reported no remaining findings in that scope.

### Jev

Real provider calls used the existing owner-only key file, never printed or
embedded in the site. Inputs were public copy/policy and non-personal editorial
query examples, not lead files or unsanitized query exports.

- Final baseline: `jev-before-complete.json`, 24,336 input tokens.
- Final candidate: `jev-after-complete.json`, 22,381 input tokens.
- Returned model: `jev-1.13.0` via requested `jev-latest`.
- Final publication gate: `tmp/serp-preview-v3-20261008-jev-gate.json`;
  374 new sentences, 269,540 input tokens, four flags covered by documented
  source/context exceptions, zero blocking flags. See actual gate JSON for
  final usage if re-run; classification can vary.

The earlier `jev-before.json` / `jev-after.json` runs are exploratory and
superseded: their extraction omitted editorial heroes on two templates and
some v2 static schemas. Do not use them as a before/after comparison.
Model scores are triage judgments, not facts, CTR estimates, citations or
evidence of rankings. Some scores did not improve; they were not optimized
by weakening necessary caveats. Six exact-sentence source/context exceptions
were added to the existing gate allowlist, with individual reasons.

### Performance

`performance/summary.json` contains three mobile Lighthouse runs before and
after for the calculator and valuation guide, with the same tool, settings
and blocked analytics/external-font patterns. This is a controlled lab
comparison, not field Core Web Vitals. Absolute LCP was already slow in the
baseline; no claim of a fast mobile experience is made. Other pages have no
new three-run performance comparison in this package. Investigate a median
regression exceeding both 10% and 250ms before any publication.

Final v3 medians: calculator 6,752ms before / 6,902ms after (+150ms, +2.2%);
valuation guide 8,865ms before / 8,852ms after (-14ms, -0.2%). Neither crosses
the regression threshold. The absolute lab LCP remains poor; this is not a
performance improvement claim or a substitute for field measurements.

## Reproduce / Preview

```sh
node scripts/build-serp-preview.mjs tmp/NEW_EMPTY_DIRECTORY
node scripts/test-serp-preview.mjs tmp/NEW_EMPTY_DIRECTORY
node scripts/review-serp-jev.mjs tmp/NEW_EMPTY_DIRECTORY marketing/serp-20261008/new-jev-review.json
node scripts/jev-publish-gate.mjs tmp/NEW_EMPTY_DIRECTORY tmp/growth-preview-v1-20260930
node scripts/serp-performance.mjs tmp/growth-preview-v1-20260930 tmp/NEW_EMPTY_DIRECTORY
node scripts/serve-serp-preview.mjs tmp/NEW_EMPTY_DIRECTORY
```

The builder refuses an existing output directory and checks the original
September 30 production identity. After this publication it intentionally
refuses a fresh rebuild against the new release; do not bypass that guard.
The approved artifact was deployed directly, without a Git commit or push.
Never deploy old v1/v2 previews or unrelated dirty files.

## Approval And Measurement

Publication is complete. Before deploying, all 599 baseline public files were
verified against production. After deploying the exact approved artifact, all
639 public files matched, the 144-URL production SEO check passed, and all five
pages passed mobile/desktop schema, metadata, keyboard FAQ and Apply checks.
The previous complete artifact remains available for rollback. The local
preview server's noindex/CSP headers were not deployed.

Record the actual publication date. Compare equal complete 28-day periods
with the same Search Console page, query, country, device and search-type
filters. Obtain page-filtered queries before attributing individual searches
to a page. Keep Google clicks/impressions separate from market search volume
and from Plausible events. The supplied 92-day page aggregates cannot be
relabelled as a fresh 28-day or 90-day baseline.

Report received and manually qualified applications separately. Typeform and
fallback form events are different streams; they are not proof of unique,
qualified leads. No conversion uplift, engine coverage, traffic target date
or ranking outcome is verified by this preview. Mobile performance and
documented customer/buyer evidence remain useful next priorities.
