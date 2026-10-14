# Selling-guide refresh: review draft

Status: **PREVIEW ONLY. Not approved for production.**

Review URL: https://0049f3a9.spacemusic-a6n.pages.dev/guides/how-to-sell-music-rights/

Production remains `https://02276b90.spacemusic-a6n.pages.dev`, public
`https://spacemusic.io/`, artifact `tmp/buyer-intent-v2-20260916`.
Never promote an earlier design preview or the incomplete first guide draft.

## Observations and rationale

The existing `/guides/how-to-sell-music-rights/` is a central footer destination.
Its exact-page Search Console filter exposed 0 clicks, 6 impressions and average
position 4 for June 16 through September 13, 2026: Web, all countries/devices,
all queries and appearances. The page-filtered Queries table exposed no data.
This is an accuracy and buyer-journey refresh, **not evidence of high search
volume**. Keyword volume/difficulty, a priority country and cross-engine AI
visibility have not been verified. The page remains English.

The previous copy asserted a generic 3-15x valuation range, treated NPS as net
royalties of any kind, implied partial ownership preserves creative control,
quoted generic lawyer fees, and gave overly absolute answers about future music.
The meta description repeated the unsupported multiple. Two related-guide
destinations did not exist. The complete previous and proposed records are
preserved in `manifest-v2.json`; the editable proposed copy is `content.mjs`.

Recommendation: revise this existing URL rather than create a competing
catalog-sale guide. Keep its title, H1, ten section headings/IDs, core topics,
FAQ questions and valid existing genre links. Improve specificity and the path
to review without pretending SPACE sells loans or guarantees purchases.

## Changes for approval

| Existing problem | Proposed change | Evidence |
| --- | --- | --- |
| Generic multiples and payout assumptions | Explicit $1,000 x 12 x assumed 4 x 50% = $24,000 scenario; not a market valuation or SPACE offer | WIPO valuation framework; arithmetic; SPACE policy |
| NPS conflated with all receipts | Separate publisher and master economics; reconcile actual deductions and rights | Round Hill 2022 annual report, printed page 1 |
| Self-release treated as ownership | Separate recording/composition rights and review the chain of title | U.S. Copyright Office |
| Partial sale implies control | Specify share, approvals, term, obligations and future-release exclusions | Conditional contract checklist; independent advice recommended |
| Buyer/advance categories blurred | Direct buyer, marketplace and advance distinctions with current provider sources | Duetti, Royalty Exchange, beatBread |
| Implied predictable closing/payment | Typical initial-offer timeframe only; closing/payment conditional | SPACE pricing and offer policy |
| Generic tax treatment and fees | Jurisdiction-specific caution, limited U.S. musical-works example, individual adviser quote | IRS Publication 550, currently 2025 edition |
| Little label-specific preparation | Label-owned versus licensed masters, artist obligations, retained cash flow and release-funding comparison | Educational workflow, not a new financial product |
| Weak next step | Contextual calculator, valuation, document checklist, offer checklist, funding guide and free-review links | Existing public destinations, no new form questions |

No new images, testimonials, case studies, rate benchmarks, routes or product
screens were invented. The numerical examples are explicitly hypothetical.
No real screenshot is needed to substantiate the financial examples. Browser
screenshots are used only for presentation QA, not as customer evidence.

## Sources

Reviewed September 16, 2026. Primary sources, linked beside relevant claims:

- https://www.copyright.gov/register/pa-sr.html
- https://www.copyright.gov/circs/circ01.pdf
- https://www.wipo.int/en/web/business/ip-valuation
- https://rhm-assets.s3.us-east-2.amazonaws.com/u/2020/10/2022-AFS-Round-Hill-WEB.pdf#page=3 (historical definitions only, not current market pricing)
- https://www.duetti.co/what-we-do
- https://royaltyexchange.com/resources/creators/frequently-asked-questions-about-selling-royalties
- https://www.beatbread.com/faq
- https://www.irs.gov/publications/p550 (country-specific, no tax-rate recommendation)
- https://spacemusic.io/pricing.md

SPACE's Apply flow was checked against the approved standalone Typeform release.
No document upload is needed to begin; private evidence comes later. SPACE is
disclosed as a potential buyer, not the seller's independent adviser.

## Build and safeguards

```sh
MARKED_MODULE=/Users/emilsoujeh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/marked/lib/marked.esm.js node scripts/build-selling-guide.mjs tmp/buyer-intent-v2-20260916 FRESH_OUTPUT FRESH_MANIFEST
node scripts/test-selling-guide.mjs FRESH_MANIFEST
```

Current candidate: `tmp/selling-guide-v2-20260916`, revision `f6fb8f7c0460`.
One HTML page receives copy changes. Thirteen modules are versioned because
the shared RelatedContent component adds an opt-in native-fragment behavior;
only this reviewed guide opts in. All other page content is byte-equivalent
after import-reference normalization. Existing assets, all 140 sitemap URLs,
hosting rules, robots, canonical URLs, forms, intake receiver, tracking and CSS
are preserved. The unrelated Music Rights 101 record is unchanged.

The guide serves the same reviewed content in static HTML and client rendering.
Nine native FAQ disclosures work without JavaScript; their answers match the
FAQ schema. Existing Article schema gains a truthful review date. Titles and
H1 remain unchanged; description, Open Graph/Twitter descriptions and Article
description agree. Two missing related links now point to the existing partial
sale comparison and this guide's tax section. Both related-link blocks include
the complete list in server HTML as well as client content.

The first preview (`5d2f8ded`) is superseded. Independent review found missing
SSR related links and router-intercepted fragment navigation there. Both are
fixed and regression-tested in v2. Paragraph/list spacing uses existing CSS.

Validation: 1,480 preservation/SSR/schema/link/module checks and 13 existing
scenario, privacy/tracking and Typeform/fallback tests pass. No test leads,
analytics conversions or notification emails were sent. A three-run mobile
performance comparison for this particular guide is still a production gate;
the earlier homepage comparison applies to the already-published package,
not proof of this guide's performance or ranking effect.

Final preview verification on September 16:

- All 459 public files match the complete v2 artifact; all 140 sitemap URLs
  respond successfully, have production canonicals and preview noindex headers.
- Production still matches all 446 files of the approved `02276b90` release.
- Browser rendering checked at 390, 768 and 1440 pixels without horizontal
  overflow. The 390-pixel checklist and desktop valuation section were inspected.
- Both related tax links scroll to the correct section after JavaScript loads.
  The native FAQ opens with Enter and closes with Space. TOC links work.
- All three new contextual Apply links reach the approved standalone Apply
  heading, with no iframe loaded before Start. Back navigation returns correctly.
- Independent v2 review found no remaining material issues: full guide text/link
  SSR-client parity, preserved Music Rights 101 behavior, and 60 active modules
  bundled without warnings. Initial v1 findings and their fixes are retained above.

## Publication and follow-up

After explicit approval, rerun preview/mobile checks, promote only the complete
v2 artifact, verify public files and all sitemap URLs, then update RELEASE.md.
Rollback is the complete `tmp/buyer-intent-v2-20260916` artifact; retain the
separate Typeform notification Worker and responses.

Use equal complete 28-day periods excluding the eventual guide deployment day.
Keep exact page, Web, country/device and query filters identical; report hidden
queries separately and do not equate impressions with market search volume.
Evaluate received and manually qualified applications separately from clicks.
No ranking or AI-citation improvement has yet been measured.
