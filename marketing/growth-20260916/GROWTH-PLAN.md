# SPACE: qualified catalogs across genres

Status: implementation preview and content drafts, September 16, 2026. Nothing in this package is authorized for production yet.

## Business brief

- Seller: an independent artist, producer, label or owner considering a sale of existing catalog rights. The customer problem is understanding eligibility, sale scope, required evidence and the trade-off between retained income and an upfront payment.
- Service: direct review and potential purchase, not an auction marketplace. All genres considered is the owner's stated direction, not a guarantee of acceptance. Selected recordings and defined shares can be proposed, subject to review and agreement.
- Initial application and review: free; no listing fee or auction commission. No new paid report, automatic offer, income threshold, guaranteed closing time or legal service is introduced.
- Primary action: request a free individual catalog review at `/apply/`. The approved Typeform and explicit Formspree alternative remain unchanged.
- Language: English. Published service coverage says worldwide; actual country eligibility and any compliance exclusions need operational confirmation. Do not invent country offices or location pages. Analyze US separately because it led the older observed traffic, not because it is the only market.
- Sources: [offer policy](https://spacemusic.io/pricing.md), [application](https://spacemusic.io/apply/), approved owner direction in this conversation. The existing About page contradicts that direction; its correction is in this preview.

## Measurement and limits

Interpret the first-stage target as **100 Google Web Search clicks/day averaged over 28 complete days**, or 2,800 clicks per 28 days. Track qualified received applications separately. A homepage redesign is a conversion hypothesis, not a traffic forecast or ranking guarantee.

The last locally verified 90-day observation covers **June 9-September 6, 2026**, Web search, all countries, all devices, all appearances. It is an older baseline, not today's performance. Source: `../research/2026-09-08/gsc-baseline.json`, observed September 8.

| Scope | Clicks | Impressions | Average position | What this supports |
| --- | ---: | ---: | ---: | --- |
| Whole property | 167 | 9,655 | 11.8 | An older average of 1.86 clicks/day, not a current forecast |
| `/calculator/` | 140 | 1,377 | 14.1 | Protect the existing traffic entry point and its next-step path |
| `/guides/music-catalog-valuation-2026/` | 17 | 7,012 | 8.5 | Inspect relevant page-filtered queries before further snippet changes |

The 100/day target is roughly 54 times that older daily average. It is a substantial acquisition goal, not a quick visual fix. Search Console impressions are NOT monthly keyword search volume. Current keyword volume and difficulty are unavailable; previous Semrush access lacked sufficient API units. No volume estimates are invented here.

Before production promotion, export a fresh complete 28-day and 90-day report. Preserve exact page/query/country/device/search-type filters. Separate explicit SPACE-branded queries from generic seller queries; ambiguous `space music` queries require manual classification. Do not join an unrelated property query table to page totals.

## Sequence and acceptance gates

### 1. Approve and release this preview

Implemented: Inter typography, clearer homepage hierarchy, one primary review action, all-genre positioning on Home/About/Sell/Brand Facts, native keyboard-accessible FAQ, direct links from the nine existing homepage genre cards to their existing destinations, and aligned machine-readable company information. The unsupported About revenue minimum, market-growth claim and reference multiples are corrected, not silently retained as facts.

Kept: all 139 sitemap URLs; all existing mood/genre articles; page titles; canonicals; robots; hosting rules; current calculator logic; the approved Apply experience; existing analytics and recipients. Outside four expressly changed pages, body content and metadata are unchanged. Head font/preload assets change to serve the shared typography. Current live production is preserved as rollback.

Gate: owner preview approval, fresh baseline, functional checks and comparable mobile-performance runs. Record production promotion separately in `marketing/RELEASE.md`. Do not claim that unchanged URLs eliminate ranking risk.

### 2. Improve demand capture before more broad articles

| Priority | Search intent | Existing destination | Next action |
| --- | --- | --- | --- |
| 1 | What could my catalog be worth? | `/calculator/` and the existing valuation guide | Preserve distinct tool/guide roles. Check the latest exact-page queries and snippet against current organic results. Do not imply the scenario is a quote. |
| 2 | Can I sell my existing music catalog? | `/sell/`, `/guides/how-to-sell-music-rights/` | Review eligibility and full/partial scope. Preserve the guide's educational role and the hub's navigation role. |
| 3 | Can my label sell its catalog? | Existing independent-owner persona plus draft below | Label-level rights/contract inventory is a genuinely different workflow. Validate query evidence and overlap before publishing. |
| 4 | Can I sell recordings with producer/band obligations? | Rights guide and two draft sections below | Begin as enriched existing content unless evidence supports a separate page. |

Publish at most one approved pilot at a time. Inspect indexing and exact-page queries before scaling. Existing content overlaps matter more than hitting an arbitrary article count.

### 3. Build evidence and distribution

Prepare one real, permissioned, anonymized catalog-review example with the original evidence, exclusions and explanation of scope. Do not claim a completed purchase or payout without records and permission. Add the actual reviewer's identity and verified role before using expert bylines.

Offer the document checklist to a short, manually researched list of relevant artist managers, label-service teams and music-business educators. Outreach stays in drafts. Seek useful editorial references, not paid ranking links or exchange networks. Three qualified referral partners may be commercially more useful than hundreds of irrelevant visits; this is a strategic hypothesis, not measured ROI.

Google recommends people-first, useful and reliable content rather than content produced chiefly to capture rankings. [Google guidance](https://developers.google.com/search/docs/fundamentals/creating-helpful-content). For Google's AI search features, use the same sound SEO foundation; special AI files or markup are not a substitute for useful indexed content. [Google AI guidance](https://developers.google.com/search/docs/appearance/ai-features).

### 4. Measure progress, not promises

Milestone checkpoints: **5, 15, 30, 60 and 100 average daily Google clicks over 28 complete days**. These are decision checkpoints, not predicted dates or outcomes. At each checkpoint ask whether the extra visitors produce contactable catalogs with documented income and transferable rights.

Track received Typeform/Formspree applications reconciled to receiver records, reviewed-qualified applications, unreviewed applications separately, and broad genre categories during internal review. No new mandatory form question. Never put names, email, financial amounts or private catalog information in analytics.

Review after 28 and 56 complete post-release days, using equal-length pre-release periods and identical filters. Separate branded/nonbranded, page, country and device. For conversion comparisons, exclude preview/testing activity and flag tracking changes. Current Plausible goal reporting and qualification counts have not been reverified for this package.

Rollback triggers: broken Apply, wrong canonical/noindex on production, missing content or routes, material layout/keyboard failure. Investigate median mobile LCP deterioration exceeding BOTH 10% and 250 ms in three comparable runs before promotion. A fresh three-run lab comparison is still required; no performance uplift is claimed.

## Deliberately not included

No production deployment, paid ads, backlinks purchase, mass article launch, new mandatory questions, payment rollout, new backend/API/database, artificial success stories, additional tracking fields or SEO guarantees.
