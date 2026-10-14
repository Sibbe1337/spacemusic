# Blog Articles

## Latest Release: Streaming Income Added to Lump-Sum Guide

Updated on 2026-09-07 at the existing URL:
https://spacemusic.io/blog/sell-music-catalog-lump-sum-2026/

Verified baseline: `tmp/primary-wave-refined-20260907` (222 files, all matched
production before this change).
Release: `tmp/lump-sum-income-20260907` (227 files).

The supplied "How to Stop Depending on Monthly Streaming Royalties and Get
Paid Upfront for Your Music" draft substantially duplicated this guide. Its
useful cash-flow perspective was added to the existing article rather than
creating another overlapping URL. The guide grew from 1,812 to 2,385 words.

An additive section separates royalty performance from reporting/payment
delays and explains that a lump sum does not create a replacement salary.
A hypothetical $24,000 usable budget covers monthly gaps of $750, $1,000 or
$1,500 for 32, 24 or 16 months respectively. The text states its assumptions,
excludes an investment return, and does not present depletion arithmetic as
a valuation or evidence that selling has a higher lifetime value.

The draft's fixed Spotify/Apple/TIDAL payout numbers, unverified institutional
research attributions, unsupported $2,000 SPACE minimum, universal 3x-10x
range, genre-wide stability claims, loan characterization of beatBread,
obligation-free buyout promises and unconditional profile/future-work
guarantees were not published. A new FAQ asks readers to establish account,
metadata and artist-profile arrangements separately from the rights transfer.

New primary references, checked 2026-09-07:

- Spotify: https://loudandclear.byspotify.com/faqs/how-do-artists-and-songwriters-get-paid/
- Apple: https://artists.apple.com/support/1124-apple-music-insights-royalty-rate
- DistroKid: https://support.distrokid.com/hc/en-us/articles/360013547274-How-and-When-Do-I-Get-Paid
- CFPB: https://www.consumerfinance.gov/archive/blog/budgeting-how-to-create-a-budget-and-stick-with-it/

SPACE-specific wording follows the unchanged live `/pricing.md` policy.
Apple's historical illustration is not presented as a current fixed rate.

The article builder now updates an earlier authored article in place within
the existing route chain. It versions only the target, three ancestor
modules and entry, preserving the other article data and legacy fallback.
No duplicate article wrapper is added. Both earlier-article and active-article
update paths were exercised; the unchanged active article produced the same
module and entry hashes in the separate build-only regression fixture
`tmp/blog-active-update-check-20260907`. That fixture is not a deployable,
prerendered release and must not be published.

Local verification:

- All 67 prior article content blocks remain intact and in order, with every
  original section anchor retained.
- Existing title, H1, canonical, description, publication date and sharing
  metadata are identical. Reading time and schema word count reflect the
  expanded content. Both edits occurred on the same calendar date.
- All 134 other HTML pages are unchanged after normalizing only the versioned
  entry reference; all 87 other original files are byte-identical.
- The Primary Wave comparison, sitemap, robots, llms.txt, pricing.md,
  glossary link and original assets are preserved. No URL was added or removed.
- All four other authored articles retain identical data, without duplicate
  wrappers. Their browser routes and a legacy article pass.
- Desktop, mobile, no-JavaScript, glossary navigation, contents anchors,
  41 internal link/asset destinations and all three budget calculations pass.
- No JavaScript errors or failed local assets were observed.

Checks: `scripts/prerender-blog-post.mjs` and `scripts/check-blog-update.mjs`.
Screenshots: `tmp/sell-music-catalog-lump-sum-2026-preview`.
Production deployment: https://9569948a.spacemusic-a6n.pages.dev

Baseline created by this content release: `tmp/lump-sum-income-20260907`.
The subsequent header/routing-only release is documented in
`marketing/ai/README.md`; use that newer snapshot for the next deployment.
Previous release:
https://2d196107.spacemusic-a6n.pages.dev and
`tmp/primary-wave-refined-20260907`.

Post-release verification:

- All 227 live production files match this release byte-for-byte.
- All 137 sitemap URLs pass the production SEO checker, including canonical
  and robots checks.
- Googlebot and Twitterbot receive HTTP 200 and the full updated content,
  with no noindex response header.
- Live 390px/320px mobile checks pass for the new contents anchor and
  three-row budget table, with no page-wide overflow.
- The existing Primary Wave comparison still shows its seven updated FAQs;
  client navigation from it to the updated lump-sum article passes.
- The application link works and no form was submitted. No live browser
  JavaScript errors were observed.

Live screenshot:
`tmp/sell-music-catalog-lump-sum-2026-preview/mobile-income-live.png`.
Technical regression checks do not guarantee future rankings.

## Previous Release: beatBread Upfront Cash Comparison

Published on 2026-09-07:
https://spacemusic.io/blog/beatbread-vs-catalog-buyers/

Production deployment: https://98fe38a4.spacemusic-a6n.pages.dev

Source: `tmp/royalty-exchange-alternatives-20260907` (215 files, verified against production).
Final release: `tmp/beatbread-vs-catalog-buyers-20260907` (219 files).

The supplied draft became a focused 1,553-word explanation of cash at
closing, fee collection and retained income, rather than another broad
company ranking. It links to the existing buyer, lump-sum and Royalty
Exchange guides. Five external primary-source URLs support the descriptions;
SPACE-specific statements cite the existing offer policy. The article
discloses SPACE's interest and does not claim private offer testing.

Corrections distinguish beatBread's published $278 plus 2.8% fee from
interest, and future-revenue collection from an upfront deduction. The
$10,000 example yields a $558 fee and $10,558 advance-plus-fee recoupment,
not a valuation or total lifetime collection estimate. The article separates
recoupment from the contractual term and does not assume all income is
withheld. The five-row hypothetical cash comparison explicitly states its
assumptions and does not establish a universal payout winner.

Unsupported multiples, broad non-recourse immunity, obligation-free sales,
guaranteed future-music exclusions and week-one payment promises were
removed. Centralized source notes are in
`marketing/competitors/catalog-funding.yaml`.

Verification:

- All 219 production files match the release byte-for-byte.
- All 137 sitemap URLs pass production checks. Existing sitemap records,
  robots, GEO files and old assets remain unchanged.
- All 134 existing HTML pages preserve their content and SEO metadata,
  allowing only updated versioned entry references and one contextual link
  on `/glossary/advance/`. No existing URL was removed or redirected.
- All 30 local article link/asset destinations exist. Desktop, mobile,
  no-JavaScript, four earlier authored articles and a legacy article pass.
- Arithmetic checks pass for the fee, recoupment sum, hypothetical closing
  cash difference and separate retained-income illustration.
- Live mobile checks pass for the five-row table and cash values, contents
  anchor, glossary navigation and application landing. No form was submitted.
- Googlebot and Twitterbot requests receive full content and sharing
  metadata with HTTP 200 and no noindex response header.

Screenshots: `tmp/beatbread-vs-catalog-buyers-preview`, including
`mobile-comparison-live.png`.

## Previous Release: Royalty Exchange Alternatives

Published on 2026-09-07:
https://spacemusic.io/blog/royalty-exchange-alternatives/

Production deployment: https://946dd76c.spacemusic-a6n.pages.dev

Source: `tmp/catalog-buyers-refined-20260907` (211 files, verified against production).
Final release: `tmp/royalty-exchange-alternatives-20260907` (215 files).

The supplied draft became a distinct 1,515-word guide focused on avoiding
an auction, distinguishing marketplace exposure from ownership transfers,
and checking existing listing commitments before switching routes. It links
to the broader buyer comparison and lump-sum guide rather than duplicating
their scope. The companion JSON supplies metadata and navigation checks;
source notes are in `marketing/competitors/catalog-funding.yaml`.

Eight external primary sources support the provider descriptions. Royalty
Exchange's published guides describe non-auction Direct Listings; the article
does not imply that these historical guides establish current eligibility.
Its seller rules describe winning bids as binding, contrary to the draft's
unqualified right to decline. Unsupported price-compression claims, universal
multiples, guaranteed payment timelines and absence of continuing obligations
were removed. Limbo's investor-partner role and beatBread's revenue-purchase
advance model are distinguished from conventional direct catalog purchases.

Verification:

- All 215 production files match the release byte-for-byte.
- All 136 sitemap URLs pass production checks. Existing sitemap records,
  robots, GEO files and old assets remain unchanged.
- All 133 existing HTML pages retain their content and SEO metadata, with
  versioned entry references updated and one contextual link added to
  `/glossary/music-catalog/`. No existing URL was removed or redirected.
- All 29 local article link/asset destinations exist. Desktop, mobile,
  no-JavaScript, three earlier authored articles and a legacy article pass.
- Live mobile checks pass for the four-row comparison, contents anchor,
  glossary navigation and application landing page. No form was submitted.
- Googlebot and Twitterbot requests receive the full article and sharing
  metadata with HTTP 200 and no noindex response header.
- The prerender test now waits for Helmet's deferred canonical update after
  client-side navigation before asserting metadata; no runtime fix was needed.

Screenshots: `tmp/royalty-exchange-alternatives-preview`, including
`mobile-comparison-live.png`.

## Previous Release: Consolidated Platform Draft

Published on 2026-09-07 to the existing comparison:
https://spacemusic.io/blog/ambient-lo-fi-music-catalog-buyers/

Production deployment: https://47e30554.spacemusic-a6n.pages.dev

Source: `tmp/catalog-buyers-20260907` (209 files, verified against production).
Final release: `tmp/catalog-buyers-refined-20260907` (211 files).

The supplied "Best Platforms to Sell Your Music Catalog for a Lump Sum in
2025/2026" draft substantially repeated the existing buyer comparison and
lump-sum guide. Its useful additions were consolidated into the comparison,
not published on a competing near-duplicate URL. The title, description,
canonical, publication date and sharing metadata remain unchanged.

The article now has 2,165 words. An additive section distinguishes review,
signed agreement and available funds, and explains fee and continuing-duty
checks. One new FAQ addresses non-recourse terms without promising immunity
from all contractual obligations. The original article content is retained;
only the added section, contents link and FAQ affect the body. The reading
estimate and schema word count reflect the expanded content.

The builder supports a guarded content-only update of the active authored
article without adding another wrapper to the fallback chain:

```sh
node scripts/build-blog-post.mjs SOURCE OUTPUT SLUG --update
node scripts/prerender-blog-post.mjs OUTPUT SLUG
```

Use a fresh output directory. Metadata identity, the active article slug,
existing sitemap record and unique glossary link are checked. Updating an
older, non-active article is intentionally rejected rather than guessed.
The existing create path and original entry-point commands remain supported.

Verification:

- All 211 production files match the candidate byte-for-byte.
- All 135 sitemap URLs pass production checks; the sitemap, robots and old
  assets are byte-identical to the source. No URL or redirect was added.
- The other 132 HTML pages preserve their content and metadata, with only
  versioned entry references changed. The target article preserves its
  previous body after removing the three explicitly allowed additions.
- All 35 local link/asset destinations exist. Desktop, mobile, no-JavaScript,
  earlier articles and legacy article tests pass without page errors.
- Live mobile checks pass for the new contents anchor, glossary navigation
  and application link. Googlebot and Twitterbot receive the updated text
  and social metadata with HTTP 200 and no noindex response header.
- Negative build tests reject duplicate creation, updating the wrong active
  article, unknown modes and source overwrites before output writes.
- Create and update paths generate byte-identical runtime modules for the
  same article revision. The create-regression output is not a deployment.

Screenshot: `tmp/ambient-lo-fi-music-catalog-buyers-preview/mobile-payment-checklist.png`.

## Previous Release: Ambient and Lo-Fi Buyer Comparison

Published on 2026-09-07:
https://spacemusic.io/blog/ambient-lo-fi-music-catalog-buyers/

Production deployment: https://43afbf4a.spacemusic-a6n.pages.dev

Source: `tmp/lump-sum-20260907` (205 files, verified against production).
Final release: `tmp/catalog-buyers-20260907` (209 files).

`ambient-lo-fi-music-catalog-buyers.md` contains the 1,861-word article;
the companion JSON supplies metadata, glossary linking and navigation tests.
Source notes are recorded in `marketing/competitors/catalog-funding.yaml`.
The article compares SPACE, Duetti, Limbo, Royalty Exchange, beatBread and
Primary Wave using eight external primary-source URLs, plus SPACE's policy.
It discloses SPACE's authorship and does not claim an independent ranking,
private offer testing, highest prices or universal genre eligibility.

Corrections remove unsupported multiples, guaranteed genre durability,
investor/deal counts, celebrity transaction values and claims of universal
institutional exclusion. Limbo's investor-partner model and distribution-client
advance requirement are explicit. beatBread is not mischaracterized as an
interest-bearing loan. The comparison adds Duetti's publicly described
independent-creator acquisition offering and distinguishes purchases from
marketplaces and advances.

Verification:

- All 209 production files match the release byte-for-byte.
- All 135 sitemap URLs pass the production canonical and robots checks.
- All 132 existing HTML pages retain their content and metadata. The only
  content addition is a contextual link on `/glossary/catalog-acquisition/`;
  versioned entry references change across the HTML. All old assets remain.
- All 35 local article link/asset destinations exist in the release.
- Desktop, mobile, contents anchors, no-JavaScript rendering, both earlier
  new articles and an original legacy article pass browser checks.
- Live mobile checks verify six company rows and navigation from the
  glossary to the article and from the article to `/apply/`, without errors.
- Googlebot and Twitterbot receive the complete article and sharing metadata
  with HTTP 200 and no noindex response header.

Screenshots: `tmp/ambient-lo-fi-music-catalog-buyers-preview`.
The prerenderer now checks all earlier authored articles present in the
release and uses per-article `navigationChecks` for cross-article links.
Adding test metadata to an older JSON file does not change its deployed page.

## Previous Release: Lump-Sum Catalog Sale

Published on 2026-09-07:
https://spacemusic.io/blog/sell-music-catalog-lump-sum-2026/

Production deployment: https://32840956.spacemusic-a6n.pages.dev

The source snapshot was `tmp/blanket-license-20260907-v2` (201 files),
verified byte-for-byte against production before this build. The new
205-file release is in `tmp/lump-sum-20260907`.

`sell-music-catalog-lump-sum-2026.md` contains the edited 1,812-word article.
Its JSON file supplies metadata, the inbound glossary link and content
checks. The article focuses on sale scope, illustrative multiple arithmetic,
net proceeds, advances and contract review, complementing the existing
general selling and valuation guides rather than replacing them.

The supplied draft's unsupported market-wide multiples, buyer thresholds,
genre-demand claims and guaranteed offers were removed. beatBread is no
longer described as an interest-bearing loan. Payment timing, continuing
obligations, future works, partial interests and master/publishing ownership
are qualified. Five primary-source URLs support the legal and competitor
descriptions; SPACE-specific statements link to the existing offer policy.

Build a new post against a verified production snapshot:

```sh
node scripts/build-blog-post.mjs SOURCE OUTPUT SLUG
node scripts/prerender-blog-post.mjs OUTPUT SLUG
```

Both commands are required, with a fresh output directory. See dependency
overrides below. The original blanket-license command names remain as
compatibility entry points. `blanket-license-page.mjs` is now the shared
article template; published assets for earlier articles remain unchanged.
The wrapper delegates other slugs to the previously deployed blog module.
Do not substitute the old frontend build in `web` for the current snapshot.

Verification for this release:

- All 205 deployed files match the final candidate byte-for-byte.
- All 134 sitemap URLs pass the production canonical and robots checks.
- All 131 existing HTML files preserve their text and metadata. Changes are
  limited to versioned entry-script references and one new contextual link
  on `/glossary/buyout-deal/`. No existing URL or sitemap record was removed.
- All 33 local article link/asset destinations resolve in the release.
- Desktop, mobile, contents anchors, glossary navigation, the previous new
  article and an original legacy article pass browser checks.
- The full article renders without JavaScript. Googlebot and Twitterbot
  receive HTTP 200, article content and sharing metadata, with no noindex
  response header.
- Article schema, canonical, title, description and social image match
  before and after rendering. No page errors or missing local assets were
  observed during the browser tests.

Screenshots: `tmp/sell-music-catalog-lump-sum-2026-preview`.

## Previous Release: Blanket License

Published on 2026-09-07:
https://spacemusic.io/blog/what-is-a-blanket-license/

Cloudflare Pages production release:
https://c7259b32.spacemusic-a6n.pages.dev

## Content

`what-is-a-blanket-license.md` contains the edited article and source links.
The companion JSON supplies the title, description, publication date and
SPACE organization attribution. The article has 1,452 words, a seven-minute
reading estimate, ten external source URLs and visible FAQ answers. No
invented author credentials, view counts or guaranteed valuations are used.

The supplied draft was corrected to distinguish BMI's for-profit model,
business music use from consumer Spotify use, repertoire coverage, master
and composition rights, mechanical and performance royalties, recording and
work identifiers, royalty distribution rules, and transaction-specific
publishing transfers. Existing references to guaranteed offers or automatic
valuation increases were qualified against SPACE's offer policy.

## Build

The source baseline was the verified 197-file production snapshot at
`tmp/social-preview-20260907`. The final 201-file release is stored at
`tmp/blanket-license-20260907-v2`.

Run the following against a fresh output directory:

```sh
node scripts/build-blanket-license-post.mjs SOURCE OUTPUT
node scripts/prerender-blanket-license-post.mjs OUTPUT
```

The builder uses `marked`; the prerenderer uses `playwright` and installed
Chrome. `MARKED_MODULE` and `PLAYWRIGHT_MODULE` can point to those packages
in the Codex workspace dependency runtime when they are not installed in
the project. `BROWSER_CHANNEL` defaults to `chrome`.

The builder's initial article shell MUST be prerendered before deployment.
The prerenderer writes full HTML only after checking its title, canonical,
description, article schema and contents. It then verifies the glossary
link, an existing blog route, responsive layouts, anchor navigation, assets
and JavaScript-disabled rendering.

The production marketing frontend source remains absent from `web`.
Readable page code and scoped styles live here; a guarded build integrates
them with the verified release's shared components. The new blog wrapper
delegates every other slug to the original blog component. The glossary
change adds a contextual link only for the blanket-license term. Original
assets are retained; new modules and the entry script use versioned names.

## Verification

- All 201 published files match the candidate byte-for-byte.
- All 133 sitemap URLs pass `scripts/check-production-seo.mjs`.
- Existing page text and metadata were preserved. Aside from entry-script
  references, the only existing-page addition is the glossary's read link.
- Robots, GEO files, canonical URLs and the homepage sharing image remain
  intact. The sitemap adds the new article without removing existing URLs.
- Requests with Googlebot and Twitterbot user agents receive the complete
  article and sharing metadata with HTTP 200.
- Browser checks passed on desktop, mobile and without JavaScript, with no
  page errors or missing local assets. Screenshots are available in
  `tmp/blanket-license-preview`.

These checks verify technical publication and preservation, not indexing
or ranking outcomes in Google or AI search services.
