# Production overlap and correction inventory

Read on 2026-09-16 from the artifact identified by `marketing/RELEASE.md`:
`/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916`.
This is production despite the directory name. Do not substitute the pending
editorial preview or older unapproved selling-guide drafts as the baseline.

## Inventory facts

Parsed `sitemap.xml`: 141 URLs. Counts include section indexes:

| Section | URLs |
| --- | ---: |
| Sell | 39: index plus 38 genre routes |
| Compare | 17 |
| Glossary | 34 |
| Guides | 6 |
| Blog | 15: directory plus 14 articles |
| Creator personas (`/for/`) | 9 |
| Streaming rates | 8 |
| Data | 3 |
| Other core/tool/policy URLs | 10 |

Of these, 139 are HTML routes; all declare `lang="en"`, and no `hreflang`
attribute was found in those HTML files. The other two sitemap URLs are
`pricing.md` and `llms.txt`. No `/es/`, `/fr/`, `/it/`, `/de/`, `/pt/` or `/sv/`
route occurs in the sitemap. This is source inspection, not a fresh live crawl
or Search Console indexing assessment.

## Already covered: improve, do not duplicate

| Proposed topic / intent | Existing destination | Assessment |
| --- | --- | --- |
| Sell a catalog / process | https://spacemusic.io/sell/ and https://spacemusic.io/how-it-works/ | Core commercial destination exists; factual review of Sell body needed. |
| Free review | https://spacemusic.io/apply/ | Existing guided form plus explicit short-form alternative. No uploads required to start; unknown income allowed at intake. Not guaranteed approval. |
| What is my catalog worth? | https://spacemusic.io/calculator/ and https://spacemusic.io/guides/music-catalog-valuation-2026/ | Scenario and valuation explanation already exist. No new calculator or report promise. |
| General selling guide | https://spacemusic.io/guides/how-to-sell-music-rights/ | Broad sections already include rights, valuation, preparation, mistakes, after-sale questions and hold-versus-sell. Needs separate legacy-claim review, not duplication. |
| Buyer shortlist | https://spacemusic.io/guides/best-music-rights-buyers-2026/ | Existing roundup; update/correct before creating another list. |
| Due diligence / what documents do I need? | https://spacemusic.io/blog/music-catalog-sale-documents-checklist/ | Income, ownership, agreements, track schedule, missing evidence and private sharing covered. |
| Evaluating the offer / net proceeds / ongoing duties | https://spacemusic.io/blog/music-catalog-offer-checklist/ | Rights, share, term, deductions, conditions, retained obligations and advice covered. |
| Partial versus full sale | https://spacemusic.io/compare/partial-sale-vs-full-sale/ | Already refreshed with owned-share and future-work distinctions. Also a glossary route and older blog exist. |
| Catalog sale versus loan | https://spacemusic.io/compare/catalog-sale-vs-catalog-loan/ | Already refreshed; separates advance from loan and links label funding. |
| beatBread versus buying | https://spacemusic.io/blog/beatbread-vs-catalog-buyers/ | Detailed sourced comparison exists, including current fee arithmetic and different end conditions. |
| Royalty Exchange alternatives | https://spacemusic.io/blog/royalty-exchange-alternatives/ | Already clarifies non-auction routes and discusses Duetti, Limbo, SPACE and beatBread. |
| SPACE versus Royalty Exchange | https://spacemusic.io/compare/space-vs-royalty-exchange/ | Exists but materially conflicts with the better alternatives article and current source evidence. |
| SPACE versus Duetti | https://spacemusic.io/compare/space-vs-duetti/ | September 16 first-party review already present; do not pitch as missing or uncorrected. |
| Independent label funding | https://spacemusic.io/blog/independent-record-label-funding-options/ | Published September 16. Already covers advances, loans, sales, retained cash flow and rights ownership. |
| Independent owner / all-genre seller | https://spacemusic.io/for/independent-artist-catalog-owner/ | Already includes all-genre coverage, catalog preparation and label pathway. |
| Masters versus publishing | https://spacemusic.io/compare/selling-masters-vs-selling-publishing/ | Existing comparison plus both glossary entries; legal/scope accuracy remains a separate review task. |
| Catalog sale proof | https://spacemusic.io/blog/case-study-ambient-producer-catalog-sale/ | Existing URL is not verified customer proof. See correction table. |
| Market data | https://spacemusic.io/data/music-catalog-market-2026/ and https://spacemusic.io/data/space-market-index/ | Existing routes are not evidence of a validated proprietary dataset or available report product. |

## Substantive corrections required before translation

These are observed text problems and evidence gaps, not edits made in this task.

| Production page | Exact observation from local HTML | Required editorial treatment |
| --- | --- | --- |
| `/sell/` | "Cinematic Ambient Music Commands the Highest Multiples in Functional Music" | Unsupported comparative pricing claim. Require a relevant, current dataset and method or remove/reframe. A cinematic use case does not establish a premium offer. |
| `/sell/` | "Sleep Music Sits at the Center of a $100 Billion Market" | Sector-size assertion cannot establish catalog demand, music revenue, SPACE buying capacity or price. Evidence, scope and date are missing from this claim. |
| `/sell/` | "Wellness Music Is a Core Asset in a $60 Billion Industry" | Same category-error risk; broad wellness spending is not catalog-sale opportunity sizing. |
| `/sell/` | Repeated "Buyer demand is rising" genre cards; references to premium rates, playlist followers and named platforms | Require direct supporting evidence and careful scope. Named services are not verified buyers of the seller's catalog, partners of SPACE or promised placements. |
| `/compare/space-vs-royalty-exchange/` | SPACE "focuses exclusively" on ambient/lo-fi/wellness; niche-only suitability; payment within days of accepting; retained creative control | Conflicts with approved all-genre/individual-review positioning and conditional transfer/payment policy. Correct in place. |
| `/compare/space-vs-royalty-exchange/` | Approximately 15% universal commission and partial sales described as limited | Current Royalty Exchange FAQ supports partial streams and fees agreed before listing. Replace unsupported simplifications using current first-party evidence. |
| `/guides/best-music-rights-buyers-2026/` | SPACE is "our top pick" for niche genres; broad creative-control retention language; higher-multiple claims based on specialization | Disclose publisher interest, remove unsupported winner/price assumptions and correct all-genre positioning. Verify current entities and products separately. |
| `/blog/case-study-ambient-producer-catalog-sale/` | John Doe byline; claimed $85K/year, $765K transaction for 75%; presented as a success story | `marketing/editorial-20260916/CONTENT-REVIEW.md` explicitly lacks evidence/permission. No localization or use as verified proof until resolved. |

Matching cinematic and sleep headlines also occur in:

- `/sell/sell-cinematic-ambient-catalog/index.html` within the production artifact.
- `/sell/sell-sleep-music-catalog/index.html` within the production artifact.
- `assets/commercialGenrePages-DCv6f_Bz.js` within the production artifact.
- Several retained `GenreIndex-*` assets, including `GenreIndex-nzzjt_go-journey-396b323aebc9-review-51e10d24b4de-growth-52842f5a03ff-quietseo-fd17485db4c3-links-0798455b493c-brand-ba3115eb02ed.js`.

This demonstrates that the concern is not only an isolated paragraph. Before a
later approved correction, trace the active client import graph and align server
HTML, client-rendered content and metadata; matching an old retained asset does
not establish that the asset is active. No assets were changed here.

The pending editorial preview fixes presentation and flags contributor issues;
the release notes explicitly say it does not fact-check the retained articles.
A design release is not a substitute for these factual corrections.

## Genuine or conditional new destinations

No localized seller paths, Limbo-specific comparison, ANote-specific comparison,
or dedicated independent-record-label persona route appears in the 141-URL sitemap.
That makes those new URLs possible, not automatically worthwhile. Demand evidence,
distinct intent, language support and substantive source review remain gates.
Existing articles already touch Limbo and label needs, so duplication risk remains.

## Verification boundaries

The application, process, current comparison and relevant article HTML were read
without executing the form. Headings were extracted for the valuation guide and
related coverage checks. The source is the release authority requested by the
parent; live deployment byte equality was not re-audited in this research.
