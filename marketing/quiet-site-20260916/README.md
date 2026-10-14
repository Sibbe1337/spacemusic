# Quiet whole-site preview and SEO pilot

Date: September 16, 2026. Status: preview only. No production promotion or SEO outcome claim.

## Review links

- [Whole-site preview](https://db999946.spacemusic-a6n.pages.dev/)
- [Sell directory](https://db999946.spacemusic-a6n.pages.dev/sell/)
- [New independent-label funding guide](https://db999946.spacemusic-a6n.pages.dev/blog/independent-record-label-funding-options/)
- [Reviewed Duetti comparison](https://db999946.spacemusic-a6n.pages.dev/compare/space-vs-duetti/)
- [Existing guided Apply, with matching presentation](https://db999946.spacemusic-a6n.pages.dev/apply/)

Immutable artifact: `tmp/quiet-site-seo-v4-20260916`. Branch: `codex/quiet-site-20260916`. Alias: `https://codex-quiet-site-20260916.spacemusic-a6n.pages.dev/`.

Production is still the release documented in `marketing/RELEASE.md`: `tmp/typeform-intake-release-v3-20260915`, deployment `6dea26c1`. Its 338 public files matched spacemusic.io after the preview deployment. Do not deploy a repository-wide build or an old preview.

## What changed

### Presentation

The approved homepage remains the design reference. A versioned, shared CSS layer extends white/pale-grey surfaces, Inter typography, restrained pale-blue actions, readable spacing, flatter link directories and visible keyboard focus across all 137 existing HTML pages. The new article uses the same layer. The Apply form, Typeform receiver, explicit Formspree alternative, consent and completion behavior are preserved.

Every existing HTML page receives one body class and one stylesheet. The design-only stage passes 1,439 assertions that all other bytes are unchanged. Additional contrast fixes cover old dark/gradient panels, inline-styled data pages, the footer email field and native range tracks. No new runtime dependency, image, animation or mandatory field was added.

### SEO and reader usefulness

One new English article addresses an independent label's funding decision. It distinguishes selling defined existing interests from advances and loans, includes a hypothetical retained-cash-flow example and a label-level document pack, and links to the existing calculator, valuation guide, offer/document checklists and application. It does not claim SPACE offers credit or advances. New contextual links come from Home, Sell and the catalog-loan glossary entry. There is no new blog hub or batch of keyword-swapped pages.

The Duetti comparison retains its URL, title, H1, topics and layout. There are 59 explicitly logged string corrections in `seo-manifest-v4.json`: all-genre SPACE positioning, conditional retained rights and payment timing, removal/replacement of unverified deal-volume/funding claims, no invented highest-price or expertise advantage, and current first-party citations. The description changes to match the revised comparison. HTML, client data and FAQ/schema strings agree.

All 139 existing sitemap URLs remain. The guide adds one URL, for 140 total (138 HTML plus two text resources). Canonicals, robots, redirects, llms.txt and pricing.md remain unchanged for existing routes. Old content outside the explicitly reviewed comparison is retained, including known claims requiring future review.

Attribution adds only the new article's known public path to the existing allowlist. No events, receivers or sensitive fields are added. The Apply form and external runtime files remain byte-identical; its inline analytics script differs only by that allowlist addition. Tests reject query strings and strip arbitrary properties, contact details and amounts.

## Sources and boundaries

Business brief and the prior demand-capture plan: `marketing/growth-20260916/GROWTH-PLAN.md`.

- [SPACE offer policy](https://spacemusic.io/pricing.md): direct acquisition, free initial review, defined partial interests, agreement/transfer conditions. All-genre positioning follows the owner's approved direction and current Apply copy.
- [beatBread label funding](https://www.beatbread.com/label) and [FAQ](https://www.beatbread.com/faq): a documented example of an advance product, not an offer from SPACE.
- [Duetti's offer](https://www.duetti.co/what-we-do) and [homepage](https://www.duetti.co/): rights purchases, partial options and public process. No private offers or valuation models were tested.
- [U.S. Copyright Office](https://www.copyright.gov/register/pa-sr.html): distinction between sound recordings and compositions, not worldwide advice on a seller's agreement.
- [WIPO valuation guidance](https://www.wipo.int/en/web/business/ip-valuation): identifiable assets, evidence, transferability and separate income. Not a music-catalog price benchmark.

External sources checked September 16, 2026. The worked example is invented arithmetic, explicitly labelled hypothetical, not a customer case. The article discloses SPACE's commercial interest and recommends independent advice.

## Verification

- Design-only preservation: 1,439 assertions pass.
- Final SEO/preservation, route graph, full article SSR and attribution privacy: 7,951 assertions pass.
- Existing scenario/tracking/intake suite: 13 tests pass, including 47 scenario assertions and 11 intake tests for success, errors, retries, duplicate prevention and blocked analytics.
- Independent read-only review: no actionable findings in the scoped final content/builder delta; all 60 active modules bundle. Reviewer independently confirmed article/Home/Sell SSR-client parity and metadata/TOC agreement.
- Browser screenshots reviewed for Sell, a genre detail, process, About, Apply, calculator, valuation guide, article, comparison, glossary, persona, data, streaming rates, streaming tool, privacy and brand facts. Not every individual page was visually inspected.
- Responsive checks: desktop approximately 1280px; screenshots at 390px and 768px; DOM overflow checks across nine representative routes at 320px and six at 768px passed. All checked headings use Inter.
- Mobile navigation to the real Apply and Typeform welcome screen verified, with no form answers or test lead submitted. Short-form alternative opens explicitly. Calculator 1,000 x 12 x 4 x 50% produces 24,000. Keyboard navigation and article TOC destinations checked.
- All 140 hosted sitemap destinations return 200, preserve production canonicals and have preview-only `X-Robots-Tag: noindex`. Text-resource MIME/canonical headers are correct. No noindex tag is baked into HTML intended for later production.
- All 429 hosted public files match the final artifact byte-for-byte. An initial verification encountered eight network fetch failures; a complete repeat passed without mismatches. Production verification separately passed for all 338 public files.

Screenshots are in tool results; no invented local screenshot filenames. Typeform's external iframe design is not rewritten by this CSS.

## Reproduce

Run from the repository root with fresh output directory names; builders deliberately refuse to overwrite existing artifacts.

```sh
node scripts/build-quiet-site.mjs tmp/quiet-home-v3-20260916 NEW_DESIGN MANIFEST_DESIGN.json
MARKED_MODULE=/absolute/path/to/marked/lib/marked.esm.js node scripts/build-blog-post.mjs NEW_DESIGN NEW_ARTICLE independent-record-label-funding-options
node scripts/build-quiet-site-seo.mjs NEW_ARTICLE NEW_FINAL MANIFEST_SEO.json
node scripts/test-quiet-site.mjs MANIFEST_DESIGN.json
node scripts/test-quiet-site-seo.mjs tmp/quiet-home-v3-20260916 NEW_FINAL MANIFEST_SEO.json
node --test marketing/funnel/scenario.test.mjs marketing/funnel/tracking.test.mjs marketing/typeform-intake/intake.test.mjs
node scripts/check-growth-preview.mjs https://PREVIEW.spacemusic-a6n.pages.dev 140
node scripts/verify-release-files.mjs NEW_FINAL https://PREVIEW.spacemusic-a6n.pages.dev
```

The article builder now inherits the active Navbar/Footer/SEOHead imports rather than reintroducing old navigation, accepts serialized crossorigin attributes, and decodes entities for TOC labels. Existing published articles are not rebuilt by these changes. The finalizer renders the new article from the same compiled article data, so an empty client-only shell must never be deployed as the final artifact.

## Release gates and remaining SEO work

This is not a claim that the whole SEO backlog is complete. Production promotion requires owner approval, a fresh Search Console baseline and a comparable three-run mobile performance comparison. The PageSpeed API returned HTTP 429 during this task; no current performance score or LCP improvement is claimed. Investigate a median regression exceeding both 10% and 250ms before promotion. Full assistive-technology testing has not been performed.

Semrush keyword data could not be retrieved because the connection lacks sufficient API units. No search-volume or difficulty numbers are fabricated. Latest locally verified baseline remains June 9-September 6, 2026, Web search/all countries/all devices/all appearances, observed September 8: 167 property clicks and 9,655 impressions. This is historical, not today's performance. Search Console impressions are not keyword search volume.

Next editorial priority is source review of the remaining competitor pages and older genre value claims. Royalty Exchange, Hipgnosis, Reservoir and Round Hill comparisons still contain inherited positioning/market assertions. Do not treat preservation as fact verification. Check each against primary sources, retaining the URL and useful topics rather than mass-rewriting or deleting them. The new funding guide is one pilot; do not create thin genre or location clones.

After an approved production release, compare equal complete 28-day periods using identical page/query/country/device/search-type filters. Separate branded searches, actual receiver-confirmed submissions, manual qualification and unreviewed applications. Plausible goal reporting and lead-quality counts were not reverified here. The 100-click/day target is a goal, not a guaranteed result of this design.
