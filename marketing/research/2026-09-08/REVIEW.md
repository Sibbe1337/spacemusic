# SpaceMusic: evidence-led SEO review and draft approval pack

Prepared 8 September 2026. **DRAFT ONLY. Nothing published, sent or changed in the release.**

## Decision summary

**Recommendation:** improve the existing calculator's explanation and route for visitors who do not know a multiple; correct the old Royalty Exchange comparison; make only a small evidence clarification in the recently updated valuation guide. Review three existing decision pages instead of launching another group of similar genre pages.

The calculator is my first choice because its exact-URL report contains relevant valuation questions and 140 page clicks over the observed 90 days. Its current form asks visitors to supply a multiple but does not explicitly explain beside that field that they can request a review without choosing one, so the proposed change addresses a concrete uncertainty without inventing an instant appraisal.

This is an evidence-based editorial priority, **not a measured conversion uplift or ranking guarantee**. There are no recordings, new screenshots for publication, outreach messages sent, or deployments in this package.

Files for review:

- [Business, performance and proposed edits](REVIEW.md) (this document).
- [Three differentiated workflow drafts](WORKFLOW-DRAFTS.md).
- [Internal-link edits, outreach drafts and recording plan](DISTRIBUTION-DRAFTS.md).
- [Publication gate and matched-period follow-up](APPROVAL-AND-MEASUREMENT.md).
- [Page-filtered Search Console observations](gsc-baseline.json).
- [Current public-page evidence](evidence/manifest.json), with original responses and extracted copy beside the manifest.
- [Draft validation results](validation.json): 25 linked site URLs returned 200 with expected canonicals where applicable; six proposed source/destination links are not duplicates; arithmetic examples, local artifact links and the 139-URL sitemap count passed. These are research checks, not tests of an unpublished implementation.

## Access and scope

**Observation:** the repository remote is [Sibbe1337/spacemusic](https://github.com/Sibbe1337/spacemusic), and the authenticated Search Console property is `sc-domain:spacemusic.io`. The public site and [release record](../../RELEASE.md) identify the same project. No other website project was selected.

The requested service named **SEO** is not exposed by an available connector. The available Semrush project/keyword service reports insufficient API units, so its project details, integration list, country keyword volume and difficulty could not be retrieved. No units or subscription were purchased. The [Semrush access page](https://www.semrush.com/mcp-access) is the provider's access route, not a source of keyword metrics.

Questions already requested from the owner: the SEO service/project URL and the primary target country. Until answered, market-specific research is provisional. Search Console and Plausible were accessible directly through the authenticated browser. No credentials or customer records were exported.

## Business brief

| Field | Verified observation | Source / boundary |
| --- | --- | --- |
| Business | SPACE is a prospective direct music-rights buyer, not an independent adviser for the seller. | [Homepage](https://spacemusic.io/), [offer policy](https://spacemusic.io/pricing.md) |
| Intended visitor | An independent artist, producer, label or other catalog owner considering selling defined revenue-generating rights. In this brief, the visitor is the **seller**, while SPACE is the buyer. | [Apply](https://spacemusic.io/apply/) |
| Problem | Understand the income and rights being offered, assess a possible upfront sale, and start a review without mistaking a calculator for an offer. | [Calculator](https://spacemusic.io/calculator/), [valuation guide](https://spacemusic.io/guides/music-catalog-valuation-2026/) |
| Verified capability | Free initial application and individual catalog review; partial defined rights considered subject to ownership and agreement; review across genres. | [Apply](https://spacemusic.io/apply/), [process](https://spacemusic.io/how-it-works/) |
| Calculator | Monthly net income × 12 × visitor's assumed annual-income multiple × share sold; optional receipts-to-net input mode. No automatic market multiple, market valuation or binding offer. | Current [calculator](https://spacemusic.io/calculator/) inspected as HTML and rendered UI |
| Initial setup | Email and artist/label are required; name, referral and updates are optional. No document upload is needed in the first form. Relevant evidence is requested privately by email. | Current [Apply UI](https://spacemusic.io/apply/) |
| Pricing | Application and initial review free; no listing fee or auction commission; no obligation to accept. Independent adviser costs, tax and other transaction costs are not thereby guaranteed to be zero. | [Offer policy](https://spacemusic.io/pricing.md), [offer checklist](https://spacemusic.io/blog/music-catalog-offer-checklist/) |
| Offer / payment | Initial offer typically 5–7 business days after relevant information is received, if the catalog fits. Bank transfer after agreement completion and rights-transfer conditions. | [Process](https://spacemusic.io/how-it-works/), [policy](https://spacemusic.io/pricing.md) |
| Country / language | Public content is English. A primary commercial target country and complete list of eligible seller jurisdictions are **not verified**. US is the strongest observed traffic source, not an owner-approved targeting policy. | GSC: US 86 clicks / 5,866 impressions; UK 12 / 525, all-page country report, 9 June–6 September |
| Conversion action | Request a free catalog review at `/apply/`. Qualified application requires separate manual review of contactability, transferable rights and documented income. | [Apply](https://spacemusic.io/apply/), [homepage qualification wording](https://spacemusic.io/) |

**Recommendation:** provisionally prioritize US-English research, while retaining globally understandable English copy and labeling US legal references. Do not promise eligibility for every country or introduce a fixed income minimum.

### Integration observations

| Surface | What was verified | What was not verified |
| --- | --- | --- |
| Search Console | Authenticated domain property and exact-page performance reports. | Full project connection inventory inside the unnamed SEO service. |
| Plausible | Authenticated site dashboard, actual goal rows, and public analytics script. | Which visits were staff/research visits, accepted leads or qualified leads. |
| Form receiver | Existing production Apply and release records preserve the Formspree receiver. | Inbox delivery, lead qualification and any CRM synchronization were not tested in this review. No test application was submitted. |
| GitHub / hosting | Repository remote; release record identifies Cloudflare Pages project `spacemusic` and current snapshot `tmp/journey-v4-20260907`. | No fresh write/deploy authorization check, no publication through an SEO integration. |
| Other products | No live Spotify import, AI catalog appraisal, Stripe checkout or seller-workspace integration is established by this audit. | Repository implementation or old screenshots are not proof of a live customer capability. |

### Existing content

The live [sitemap](https://spacemusic.io/sitemap.xml) contains **139 URLs**, including **13 blog articles**. The research capture inspected 38 public responses, including all 13 articles' titles, headings and openings, the relevant full articles, principal product pages and the three comparison pages selected for drafts; it is not a legal/factual audit of every paragraph on all 139 URLs.

| Existing content family | Public examples and editorial treatment |
| --- | --- |
| Valuation / calculation | [Calculator](https://spacemusic.io/calculator/), [valuation guide](https://spacemusic.io/guides/music-catalog-valuation-2026/), [streams-worth guide](https://spacemusic.io/guides/what-are-your-streams-worth-2026/). Keep separate tool, methodology and streaming-income intents. |
| Selling / choosing a buyer | [Lump-sum guide](https://spacemusic.io/blog/sell-music-catalog-lump-sum-2026/), [ambient/lo-fi buyers](https://spacemusic.io/blog/ambient-lo-fi-music-catalog-buyers/), [Royalty Exchange alternatives](https://spacemusic.io/blog/royalty-exchange-alternatives/), [beatBread comparison](https://spacemusic.io/blog/beatbread-vs-catalog-buyers/). Do not create another generic alternatives roundup. |
| Transaction preparation | [Document checklist](https://spacemusic.io/blog/music-catalog-sale-documents-checklist/), [offer checklist](https://spacemusic.io/blog/music-catalog-offer-checklist/). Both already published 7 September; link rather than recreate. |
| Rights education | [Blanket-license article](https://spacemusic.io/blog/what-is-a-blanket-license/), [rights guide](https://spacemusic.io/guides/music-rights-101/), glossary and comparison pages. Keep detailed legal questions separate from lead capture. |
| Legacy genre articles | [Lo-fi optimization](https://spacemusic.io/blog/maximizing-your-lo-fi-catalog-value/), [ambient royalties](https://spacemusic.io/blog/streaming-royalties-guide-for-ambient-music/), [partial rights](https://spacemusic.io/blog/why-selling-partial-rights-makes-sense/), [PRO registration](https://spacemusic.io/blog/how-to-register-your-ambient-music-with-pros/), [AI/ambient](https://spacemusic.io/blog/future-of-ai-in-ambient-music/), [case study](https://spacemusic.io/blog/case-study-ambient-producer-catalog-sale/). Treat unsupported prices, growth claims and customer outcomes as unverified, not as product evidence. |

**Important observations outside the proposed first refresh:** `/about/` still says SPACE focuses exclusively on ambient/lo-fi/wellness; the streams-worth guide still attributes genre weighting and comparable-sale analysis to the calculator; the old case study claims a $765K transaction without supporting documentation available in this review. Do not reuse those claims in new copy, media or outreach; ask for substantiation or approve a separate correction. `/blog/` returned homepage content and a homepage canonical in the server response, so it is not proposed as an internal-link destination or a new hub. These observations are not evidence of a measured ranking loss.

## Search Console baseline

**Observed 8 September 2026. Period: 9 June–6 September 2026 inclusive, 90 complete calendar days.** September 6 was the latest day shown in the standard daily report. This is not the real-time/24-hour preliminary view; Google can still revise reporting, and the UI did not provide a separate finalization flag for every date.

Filters: domain property `sc-domain:spacemusic.io`; **Web**, all countries, all devices, all search appearances; no site-wide query filter. Exact URL page filter was applied before reading each page's Queries tab. Slash and slashless URLs were kept separate. No language filter was applied or claimed.

Site total: **167 clicks, 9,655 impressions, average position 11.8**. [Open baseline report](https://search.google.com/search-console/performance/search-analytics?resource_id=sc-domain%3Aspacemusic.io&start_date=20260609&end_date=20260906&metrics=CLICKS%2CIMPRESSIONS%2CPOSITION).

Google documents differences between page and property aggregation and omissions in query reporting. Page totals must not be assigned to the few visible query rows, and impressions are **not keyword search volume**. [Google report documentation](https://support.google.com/webmasters/answer/7576553?hl=en), [data discrepancies](https://support.google.com/webmasters/answer/17010575?hl=en).

### Ranked shortlist: three pages, not five forced candidates

Metrics in this table belong to the **exact page + exact visible query**, not to the whole page.

| Priority / page URL | Buyer-related query | Clicks | Impressions | Avg. position | Missing / inaccurate information | Proposed edit |
| --- | --- | ---: | ---: | ---: | --- | --- |
| 1. https://spacemusic.io/calculator/ | how much is a music catalog worth | 0 | 136 | 7.8 | Asks the visitor to choose a multiple without an explicit adjacent route for those who do not know one; headline suggests an assured upside. | Explain the two routes: hypothetical arithmetic or individual review without a multiple. Replace headline with a question, not a value promise. |
| 1. https://spacemusic.io/calculator/ | music catalog valuation | 5 | 27 | 17.6 | Same issue; a tool is not a market appraisal. | Same refresh, not another page for this wording. |
| 2. https://spacemusic.io/guides/music-catalog-valuation-2026/ | music catalog valuation multiples 2025 2026 | 0 | 16 | 3.4 | H2 says “Revenue Multiple Ranges by Genre” but the text correctly provides no verified universal ranges. | Rename H2 and explain that a cited 2026 survey measures perceptions, not a guaranteed offer or closed-deal dataset. |
| 2. https://spacemusic.io/guides/music-catalog-valuation-2026/ | what's the average acquisition multiple for jazz catalogs | 0 | 39 | 10.7 | No verified jazz average is available; inventing one would be worse than an honest answer. | Keep the evidence-led response; explicitly distinguish genre from transaction comparability. No jazz duplicate article. |
| 3. https://spacemusic.io/compare/space-vs-royalty-exchange/ | sell royalty | 0 | 2 | 26.5 | Says SPACE is exclusively genre-limited; suggests partial deals are restricted at Royalty Exchange; fixed fee/speed claims need verification. | Correct against current SPACE policy and Royalty Exchange's published deal options. Demand evidence is weak, factual correction evidence is strong. |

Page totals, separately: calculator **140 / 1,377 / 14.1**; valuation guide **17 / 7,012 / 8.5**; Royalty Exchange comparison **0 / 104 / 8.6** (clicks / impressions / position). The comparison also has “royalty marketplace” at 0 / 1 / 25.0, an ambiguous seller/investor intent.

**Why not the other two inspected pages?** The buyers guide has 0 clicks and 65 impressions but its two exposed queries concern artist negotiations and bands that sold catalogs, not clear seller buying intent. The partial-sale comparison has 0 clicks and 8 impressions but no exposed query rows; it remains a useful factual-repair draft, not a proven query opportunity.

**Brand separation:** site-level “spacemusic” has 0 clicks / 5 impressions / position 27.4 and is kept in a brand-form bucket; the term can also describe a genre. “space music inc” has 0 / 9 / 33.4 and is an ambiguous entity, not confirmed company demand. These are site-level query observations, not joined to homepage totals or treated as non-brand acquisition searches. None of the selected pages' exposed query rows contains the SpaceMusic company name.

The recently published calculator/guide changes fall **after this baseline**. The low historical CTR cannot establish that their current copy is failing.

## Buying-search research

**Market status:** English-language exploratory research; US is a provisional recommendation based on observed traffic, pending owner confirmation. The search tool does not expose a controlled US location/device or a verified Google rank order. Results below are current public search-result observations, not a US rank-tracking report.

**Volume and difficulty:** unavailable for every keyword below because the connected provider could not supply keyword data. “Unavailable” is not zero volume or low difficulty. Google Trends indexes, GSC impressions and page traffic are not substituted for monthly searches.

The working inventory contains 15 buyer-intent candidates, grouped by the task the seller is trying to complete. Current results were checked for the strongest cluster seeds; individual variants are not claimed to have separate volume or SERP validation.

| Priority / buyer question | Keywords | Available volume / difficulty | Expected page type | Existing destination / new page decision | Evidence and reason |
| --- | --- | --- | --- | --- | --- |
| 1. What might my catalog be worth? | how much is a music catalog worth; music catalog valuation calculator; how to value a music catalog | Not available / not available | Interactive scenario tool, clear assumptions, route to review | [Refresh calculator](https://spacemusic.io/calculator/); no new calculator page | Exact-page GSC questions; current results include [Tools 4 Music](https://tools4music.com/calculators/catalog-valuation) and [Encore](https://encoremarkets.us/value). SPACE should explain its narrower verified functionality, not copy unsupported automated-valuation claims. |
| 2. Which multiple is relevant to my rights? | music catalog valuation; music catalog valuation multiples 2026; music publishing catalog appraisal | Not available / not available | Sourced methodology guide | [Existing valuation guide](https://spacemusic.io/guides/music-catalog-valuation-2026/) | GSC multiple/appraisal questions; results include [Duetti's index](https://www.duetti.co/music-finance-index), [Royalty Exchange's valuation guide](https://royaltyexchange.com/blog/valuing-music-royalty-assets-a-how-to-guide) and [RouteNote](https://routenote.com/radar/how-much-is-my-music-catalogue-worth/). Add interpretation, not invented genre benchmarks. |
| 3. Who will buy directly, and how do alternatives differ? | sell music catalog; Royalty Exchange alternatives; beatBread vs catalog buyers | Not available / not available | Commercial process page plus scoped comparison articles | [How it works](https://spacemusic.io/how-it-works/), [existing alternatives](https://spacemusic.io/blog/royalty-exchange-alternatives/), [existing beatBread article](https://spacemusic.io/blog/beatbread-vs-catalog-buyers/) | [Duetti](https://www.duetti.co/), [Royalty Exchange](https://royaltyexchange.com/creators/catalog-deal-options) and [beatBread](https://www.beatbread.com/artist-funding) describe different routes. Keep the generic alternatives roundup distinct from a two-company comparison; no new roundup. |
| 4. Can I sell selected rights without treating everything as one asset? | sell part of my music catalog; selling masters vs publishing; catalog sale vs catalog loan | Not available / not available | Decision comparison with worked examples and limits | Revise the three existing comparison URLs in WORKFLOW-DRAFTS.md | Existing URLs already cover the intent; current results mix legal explanation and funding providers. US [Copyright Office](https://www.copyright.gov/circs/circ56a.pdf) distinguishes the assets; [Royalty Exchange](https://royaltyexchange.com/creators/catalog-deal-options) documents partial structures. Sparse/no page-query demand evidence, so prioritize factual quality over predicted traffic. |
| 5. What must I prepare and check before selling? | music catalog sale documents; music catalog due diligence checklist; music catalog offer checklist | Not available / not available | Task checklist, source documents, independent review | [Document checklist](https://spacemusic.io/blog/music-catalog-sale-documents-checklist/) and [offer checklist](https://spacemusic.io/blog/music-catalog-offer-checklist/), already live | Results include [rightsHUB](https://rightshub.net/news/how-to-audit-your-music-catalogue) and [From The Stem](https://ftsmusic.com/articles/music-catalog-due-diligence-checklist). SPACE already has both destinations; improve discovery rather than duplicate them. |

These are five workflow/intent groups, not five mandatory landing pages. In group 3, compare multi-provider options on the existing alternatives article, and the mechanics of a specific advance on the beatBread article. In group 4, each decision has genuinely different inputs and consequences, so separate existing comparisons are appropriate.

Exclude from commercial targeting: celebrity sale news, CD price guides, “cooltoad website value,” broad music listening, and investor-only “buy royalties” searches. They do not reliably represent someone offering a catalog to SPACE.

### SERP observations versus recommendations

**Observed:** competing calculation pages expose numerical scenarios and sometimes defaults/ranges; educational results explain rights, earnings and multiples; transaction-checklist results emphasize documents and exceptions. An accessible Duetti index is labeled **H1 2026 Outlook, published January 12, 2026**, and describes industry-panel perceptions. It must not be represented as a verified H2 closed-transaction price table. [Duetti source](https://www.duetti.co/music-finance-index).

**Recommended:** answer the seller's task with transparent assumptions and a short next step. Do not infer that a search-result snippet's financial claim is accurate or copy competitors' multiples; verification against the underlying source matters more than matching their marketing language.

## First-page refresh: calculator

Current page checked via fresh HTTP response and rendered browser, not the older cached search snippet. Current title and description already accurately describe a hypothetical tool. **Keep both unchanged.**

- Title: `Music Catalog Value Calculator: Build a Sale Scenario — SPACE`
- Description: `Calculate a hypothetical catalog sale from monthly net income, your assumed multiple and the share sold. Request a free individual catalog review.`

### Proposed changed copy

| Location | Current copy | Proposed copy | Source / reason |
| --- | --- | --- | --- |
| H1 | Your catalog is worth more than monthly royalties. | How much could your music catalog sell for? | [Calculator](https://spacemusic.io/calculator/) is explicitly hypothetical; the buyer question is observed in its own GSC report. Ask the question without asserting an outcome. |
| Intro | Explore a hypothetical sale using your monthly net income and an assumed multiple you choose. This is not a market valuation or a SPACE offer. | Use documented net income to explore a hypothetical sale, or request an individual review if you do not know which assumptions to use. This calculator does not estimate a market multiple or produce a SPACE offer. | Current [tool](https://spacemusic.io/calculator/) and [Apply](https://spacemusic.io/apply/). Explain the alternative to guessing. |
| Multiple helper | Choose your own positive assumption. No market multiple is supplied. A multiple is not a number of years to multiply again, nor the legal term of a sale. | Choose a positive multiple only to explore an assumption. No market multiple is supplied. Don't know what to enter? You can leave it blank and use the free-review button below; no multiple is needed to apply. A multiple is not the legal term of a sale or another number of years to multiply. | Current Apply does not ask for a multiple. No new form behavior or automatic quote is proposed. |

### Replacement section: “How this is calculated”

**Current copy**

> Monthly net income x 12 x assumed multiple x share sold. There is no extra years multiplier and no predicted price range.

**Proposed copy (English draft)**

### From an assumption to a useful next step

Monthly net income × 12 × assumed annual-income multiple × share sold = your hypothetical scenario. There is no additional years multiplier or predicted price range.

For example, $1,000 a month × 12 × an arbitrary 4 × 50% gives $24,000. The 4 is an illustration, not a market benchmark or an offer. If the income already represents only your owned interest, the percentage you sell applies to that interest once, not to the entire catalog again.

**Don't know a multiple? You do not need one to request a review.** Start with your email and artist or label name using the free-review button above. SPACE requests the relevant income and rights documents privately by email and assesses each catalog individually. Submitting the form requests a review, not a sale.

A scenario is also not cash in your bank account. Taxes, transaction costs, outstanding balances and payment conditions need separate consideration before accepting an offer.

**Sources:** [current calculator](https://spacemusic.io/calculator/), [current Apply](https://spacemusic.io/apply/), [offer policy](https://spacemusic.io/pricing.md), [offer checklist](https://spacemusic.io/blog/music-catalog-offer-checklist/). The arithmetic example is invented educational material, not evidence of a completed deal. [WIPO](https://www.wipo.int/en/web/business/ip-valuation) supports separating asset valuation assumptions from an actual transaction price.

**Implementation boundary:** copy only; preserve field validation, receipts mode, multiplication, event semantics, canonical, form receiver and existing next-step link. Do not add a second duplicate Apply link in this section. This is a proposed usability improvement; no abandonment event or user test establishes that the helper text currently causes lost leads.

**Images:** no decorative image or invented dashboard is needed. Optional real footage should show the actual blank multiple field and Apply form. These screens were inspected, but no screenshot asset is approved for publication; see the recording plan for footage still required. No financial/customer screenshot is needed to support arithmetic.

## Small companion corrections

### Valuation guide

Current H2: **Revenue Multiple Ranges by Genre**.

Proposed H2: **Why there is no universal genre multiple**.

Keep the current paragraph beginning “There is no verified, generally applicable 2026 multiple table on this page.” Append:

> When reading a market report, check what it actually measures. Duetti and Billboard's publicly accessible H1 2026 Music Finance Index describes a panel's perceptions of catalog multiples, not a list of completed transactions or an offer for your music. Its introduction defines a multiple relative to trailing 12-month net revenue and explains that rights type, age, genre and geography affect interpretation. Do not copy a survey figure into a sale calculation without checking the income base and rights being compared.

Link the report name to [Duetti's index](https://www.duetti.co/music-finance-index). This provides a useful evidence distinction for actual multiple-related queries without supplying an unsupported jazz average. Preserve the guide's current URL, H1, title, description, example and existing content. The site is a commercial participant; this is not an independent appraisal.

### Royalty Exchange comparison

Current quick verdict:

> Royalty Exchange runs an auction-style marketplace where investors bid on your royalties, typically charging around 15% commission. SPACE buys catalogs directly with no auction or commission, specializing in ambient, lo-fi, and wellness music. Choose Royalty Exchange if you want competitive bidding on a mainstream catalog; choose SPACE for a fast, direct sale of ambient or meditation music.

Proposed quick verdict:

> SPACE is a direct buyer that reviews revenue-generating music catalogs across genres. Royalty Exchange is a marketplace connecting rights holders with investors and describes options involving selected songs, a percentage of earnings or a specific royalty stream. Compare written proposals for the same rights, income base, term and share, including fees and payment conditions. Neither route is shown here to pay more or close faster for your catalog.

Source: [SPACE Apply](https://spacemusic.io/apply/), [policy](https://spacemusic.io/pricing.md), [Royalty Exchange deal options](https://royaltyexchange.com/creators/catalog-deal-options). Revise matching table/verdict/FAQ statements in the same eventual release so the corrected summary is not contradicted below it. Replace unsupported fixed fee assertions with “Confirm fees for the proposed structure”; do not suggest fees are zero. Preserve the existing comparison URL. The source describes partial choices, but does not substantiate the old comparison's universal fee, payout-time or seller-control claims.

#### Matching comparison copy for review

The current table is captured in `evidence/compare__space-vs-royalty-exchange.source`. Proposed replacements below retain its comparison subjects while making uncertainty explicit; they are not a new design.

| Row | Current SPACE / Royalty Exchange wording | Proposed SPACE | Proposed Royalty Exchange |
| --- | --- | --- | --- |
| Deal type | Direct purchase / auction marketplace | Direct acquisition proposal for defined rights | Marketplace; ask which listing route applies to the proposed asset |
| Genre focus | Ambient/lo-fi/meditation/wellness / all genres and royalty types | Revenue-generating catalogs across genres; individual review | Confirm eligibility for the specific rights and income source |
| Commission / fees | No commission or listing fees / approximately 15% | Free application and initial review; no listing fee or auction commission. Other transaction costs may apply. | Obtain current written fees for the proposed structure; no universal fee quoted here |
| Payout speed | Days after acceptance / weeks | Bank transfer after completed agreement and satisfied transfer conditions | Confirm review, listing and settlement timing for the selected route |
| Partial rights sales | Yes / limited, mostly full streams | Defined partial interests considered, subject to ownership and agreement | Published options include selected songs, percentages of earnings and specific royalty streams |
| Minimum catalog size | No strict minimum / consistent income needed for bidders | No universal numerical threshold stated here; catalog fit is assessed | Confirm current eligibility; no universal numerical threshold verified here |
| Creative control | Retained by creator / varies | Retained approvals and rights depend on the agreement | Retained approvals and rights depend on the agreement |
| Process complexity | Submit, offer, accept / documentation, listing, auction | Application, evidence review and agreed transfer requirements | Listing route and required evidence should be confirmed before proceeding |
| Valuation approach | Mood expertise / investor bids | Individual review; public calculator is hypothetical only | Compare the actual written proposal, not a headline marketplace figure |
| Track record | Newer niche entrant / 2,300+ since 2011 | No independently substantiated acquisition count supplied here | Do not rely on the old count without a current dated source |

SPACE column: [current policy](https://spacemusic.io/pricing.md), [process](https://spacemusic.io/how-it-works/). Partial options: [Royalty Exchange deal options](https://royaltyexchange.com/creators/catalog-deal-options). Its [eXchange explanation](https://royaltyexchange.com/blog/about-the-exchange), published in 2021 and still accessible, describes non-auction listings; it is sufficient to reject the absolute “auction only” description, not to establish every current eligibility rule or price. Questions about unverified terms are editorial recommendations, not asserted provider capabilities.

**Replacement introduction:**

> If you are considering selling defined music rights, compare who would acquire them and what the agreement includes. SPACE is a direct buyer. Royalty Exchange offers a marketplace route. This comparison explains the questions to ask about scope, fees, timing and retained rights; it does not establish which provider will offer more for your catalog.

**Replacement SPACE description:**

> SPACE reviews revenue-generating catalogs across genres and may make an individual acquisition proposal if a catalog is a fit. The initial application and review are free. A proposed partial sale needs a defined ownership and income basis; retained creative approvals and payment conditions must be confirmed in the agreement.

**Replacement Royalty Exchange description:**

> Royalty Exchange connects rights holders and investors through a marketplace. Do not assume every transaction requires an auction: its published eXchange explanation also describes listings that receive offers without one. Confirm which current route, eligibility requirements, fees and settlement steps apply to the rights you propose to sell.

**Strengths and limitations replacement bullets:** use “Direct counterparty; free initial review; defined partial interests considered” for SPACE's process options, and “Individual fit review; no guaranteed offer; retained rights and closing conditions require agreement” for its limitations. For Royalty Exchange use “Marketplace route; published non-auction listing route; published partial-structure options,” followed by “Confirm asset eligibility, fees, evidence requirements and settlement terms; no guaranteed price or timing.” These replace unsupported scale, universal speed, niche-service quality and guaranteed-control comparisons.

**Replacement final verdict:**

> Choose which route to investigate by comparing written terms for the same assets, share and duration. A higher headline figure may include more rights, deductions or conditions. SPACE has a commercial interest in an acquisition; use independent advice before accepting any proposal, including one from SPACE.

| Existing FAQ question | Proposed answer, also to be reflected in matching structured data |
| --- | --- |
| Does Royalty Exchange buy music catalogs directly? | Royalty Exchange describes a marketplace connecting rights holders and investors. Confirm the legal buyer in the actual proposal rather than assuming the platform itself is your counterparty. |
| Can I sell only part of my royalties on SPACE? | You can propose a defined partial interest for review. Ownership, transferability, the income share and retained approvals must be confirmed; a partial sale does not automatically preserve every decision right. |
| How long does a Royalty Exchange auction take? | Ask for the current timetable for the route offered to you, including review and settlement. This page does not verify a universal 30-day auction or closing period. |
| Is SPACE only for ambient and lo-fi music? | No. SPACE reviews revenue-generating catalogs across genres, subject to individual fit and rights review. |

Keep the comparison's URL and accurate existing title/meta description. Preserve its useful related links and review action, but label the final action “Request a free catalog review” rather than implying an instant independent valuation. No new source-backed transaction count, fee range or screenshot is available to add.

## AI visibility: what is and is not measured

The unnamed SEO service's AI summary, tracked prompts, scans and third-party cited pages could not be accessed. The earlier pasted “38/100”, “3 ChatGPT mentions” and competitor totals are **not treated as a current verified baseline**.

The authenticated Google Search Console **Generative AI features** report does expose **89 site impressions** during 9 June–6 September, all countries/devices. It is a different measurement, not a cross-engine visibility score. [Open report](https://search.google.com/search-console/performance/search-analytics/ai?resource_id=sc-domain%3Aspacemusic.io&start_date=20260609&end_date=20260906).

| Exact prompt | Scan date | Engines / surface checked | Mentions | Citations | Exposed source URL / metric |
| --- | --- | --- | --- | --- | --- |
| Not exposed | No scan date; aggregate 9 June–6 September, read 8 September | Google generative-AI search features; no separate engine/version split exposed | Not exposed | Not exposed as a citation count | https://spacemusic.io/guides/music-catalog-valuation-2026/ : 26 impressions |
| Not exposed | Same | Same | Not exposed | Not exposed | https://spacemusic.io/guides/music-catalog-valuation-2026 : 24 impressions |
| Not exposed | Same | Same | Not exposed | Not exposed | https://spacemusic.io/calculator/ : 20 impressions |
| Not exposed | Same | Same | Not exposed | Not exposed | https://spacemusic.io/ : 8 impressions |
| Not exposed | Same | Same | Not exposed | Not exposed | https://spacemusic.io/calculator : 7 impressions |
| Not exposed | Same | Same | Not exposed | Not exposed | https://spacemusic.io/blog/future-of-ai-in-ambient-music/ : 2 impressions |
| Not exposed | Same | Same | Not exposed | Not exposed | https://spacemusic.io/guides/best-music-rights-buyers-2026/ : 2 impressions |
| Not exposed | Same | Same | Not exposed | Not exposed | https://spacemusic.io/apply/ : 1 impression |
| Not available | Not available | ChatGPT, Perplexity, Gemini standalone and Copilot not scanned in this task | Unknown | Unknown | No accessible prompt-level report or cited third-party URLs |

Do not sum the page rows to replace Google's site total. Referral traffic from an AI-labelled source also does not establish the prompt, citation count or the engines that were scanned.

The current calculator and valuation guide were opened and inspected. One verifiable gap in this Google-exposed content is the missing explicit no-multiple-needed route beside the calculator field. The refresh answers it; it is not proof that an AI engine previously omitted SPACE because of that gap. No third-party page is falsely labeled an AI citation.

**Five fixed prompts proposed for future checks, not scans performed:**

1. “How can an independent artist estimate a music catalog's sale value from documented net royalty income?”
2. “Can I sell half of my owned master-recording rights while keeping my publishing rights?”
3. “How do a direct music catalog sale, a royalty marketplace and a royalty advance differ?”
4. “What documents and contract terms should I check before accepting a music catalog purchase offer?”
5. “Does SPACE at spacemusic.io review revenue-generating catalogs outside ambient and lo-fi, and what does the initial review cost?”

Fix English language, approved market, engine/product/version, search mode and signed-out/new-chat conditions before recurring runs. Store date, exact prompt, response, mention, direct citation URL and whether the cited page supports the answer. Keep the branded fifth prompt separate from the four non-brand prompts; do not add unchecked engines to totals.

## Conversions, separately

Plausible was checked for **7 September 2026 only**, all sources/pages, one complete calendar day under its site settings. It shows `apply_clicked`: **3 unique visitors / 4 events**; `calculator_used`: **1 / 1**. A legacy `Form: Submission` appears at **1 / 1**; it is not proof of a successful catalog application. [Plausible day report](https://plausible.io/spacemusic.io?period=day&date=2026-09-07).

`application_started` and `application_submitted` did not appear in the displayed goal rows. This does **not** establish zero real applications, zero qualifying leads, or a working end-to-end receiver. Qualified applications remain unknown. Instrumentation was introduced during this period and staff visits may be included, so no old/new conversion rate comparison or improvement claim is justified. The follow-up specification keeps these outcomes separate from Google traffic.

## Approval requested, not assumed

Approve the specific calculator, guide and comparison wording before implementation; review the three longer drafts separately. Confirm target country and provide the SEO project URL for the remaining keyword and prompt-level data. Editorial outreach remains unsent and the film remains a plan. Publication and follow-up controls are in [APPROVAL-AND-MEASUREMENT.md](APPROVAL-AND-MEASUREMENT.md).
