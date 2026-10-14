# SPACE Jev site review

29 September 2026. Uses TypeSafe Jev (`jev-1.13.0`, requested as `jev-latest`) on
public inputs only: the published website text and aggregated Search Console
queries. No customer data, leads, documents or personal data are sent. The API key
is read from the owner-only file created by `../jev-catalog-review/secrets.mjs`
and is never printed or written. Nothing here changes the website.

Outputs are review lists for a person, not verdicts. Typed answers are not facts.

## 1. Claims review (`claims.mjs`)

    node experiments/jev-site-review/claims.mjs [release-dir]

Every unique sentence (6,332 across 139 HTML pages of the production release
`tmp/motion-preview-v3-20260929`) gets four yes/no judgments: seller promise,
unsourced external figure, conflict with `pricing.md`, credential or customer case.
Restating SPACE's own policy terms is excluded. Flag threshold: any probability >= 0.5.

Result: 707 flagged sentences on 116 pages (promise 102, unsourced number 456,
policy conflict 80, credential/case 271). 3.84M input tokens, about USD 0.16.

Sanity check: on the pages already listed in
`marketing/editorial-20260916/CONTENT-REVIEW.md` it flags the known issues
($85K to $765K case, "15 years of experience", "15,000+ AI tracks", "8-12x
multiples") at 0.88-0.97, plus "Created a competitive bidding environment" in the
case study, which contradicts SPACE's no-auction positioning.

New, not in the content review: every `/sell/sell-*` genre page and several `/for/*`
pages contain an anonymous customer story (for example "SPACE matched the producer
with an ed-tech startup", "valued the catalog at 13x annual revenue ($416,000)")
and a multiple range presented as fact ("4-8x annual revenue"). These need the
same source-or-remove review.

Known false-positive pattern: most high `policy_conflict` hits describe competitors
(Royalty Exchange commission, auctions), not SPACE. Review, do not auto-fix.

Files: `output/claims-flagged.csv` (sorted), `output/claims-all.json`.

## 2. Search intent (`queries.mjs`)

    node experiments/jev-site-review/queries.mjs [release-dir] [queries.csv]

426 queries from the Search Console export of 22 September 2026 (last 16 months).
Per query: intent (6 options) and the best of the 141 sitemap pages, or none.
1.52M input tokens, about USD 0.06. Note: this export covers only named queries;
most site impressions come from anonymized queries not included here.

| Intent | Queries | Impressions | Clicks |
| --- | ---: | ---: | ---: |
| seller | 117 | 853 | 16 |
| industry_research | 109 | 736 | 0 |
| artist_earnings | 175 | 567 | 0 |
| off_topic | 16 | 274 | 0 |
| buyer_investor | 4 | 51 | 0 |
| brand | 5 | 26 | 0 |

Findings:
- The valuation guide is the right page for 32 queries / 778 impressions but got
  9 clicks. The "valuation multiples 2025 2026" queries rank 3-5 with zero clicks:
  searchers want a multiples table, and the claims review shows current multiples
  are unsourced. A sourced multiples table is both the SEO and the compliance fix.
- Gap cluster with no page: streaming platform catalog sizes 2026 (Deezer,
  Spotify, Apple Music, YouTube Music, Tidal), ranking 2-8 already via other pages.
- Gap: "music catalogs for sale 2026" (buyer intent, position 9) and "music
  marketplace"; SPACE is not a marketplace, so at most an explainer.
- Artist-earnings glossary queries mostly rank 40-90; low priority until the
  streaming-rate hub exists.

Files: `output/queries.csv` (sorted by impressions), `output/queries-all.json`.

## Cost and model

Total about USD 0.22 at the lab's recorded USD 0.042/M input tokens (5.36M tokens).
Not an invoice. Model returned `jev-1.13.0` on every request.
