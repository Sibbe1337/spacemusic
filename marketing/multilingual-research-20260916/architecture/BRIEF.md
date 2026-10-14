# International SEO/GEO expansion: architecture and governance brief

Date: 2026-09-16. Status: research only, not implementation or launch approval.

## Decision

**Conditionally feasible as a small language pilot; not ready for bulk translation or country landing-page expansion.** Preserve all 141 existing canonical URLs. Add one owner-approved language only after editorial, operational and intake gates pass. Language selection and keyword volumes belong to the other research workstreams, not this audit.

The largest risks are unreviewed claims, an English-only intake, and a static/client implementation without a populated marketing source checkout. Translation is not proof of local service availability, local legal expertise, payment coverage or support in that language.

## Verified baseline

Production is `6984da7b`, built from [the wordmark snapshot](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916), per [RELEASE.md](/Users/emilsoujeh/spacemusic/marketing/RELEASE.md:9). The separate editorial preview `b5189220` / `tmp/editorial-preview-v5-20260916` is **not live** and has not completed factual/attribution correction.

Fresh checks in this audit:

| Surface | Finding | Expansion implication |
| --- | --- | --- |
| Sitemap | 141 unique URLs: 139 HTML, `/pricing.md`, `/llms.txt`; all map to local files | Baseline URL set is a preservation contract, not a mandate to translate every page |
| HTML | All 139 declare `lang="en"`; one matching self-canonical each; no hreflang; no restrictive index/snippet meta found | Missing hreflang is expected for the present single-language site, not a current error |
| Robots/hosting | Crawling allowed; sitemap declared; Markdown/text canonical headers and slash redirects exist | Preserve `_headers`, `_redirects`, robots and canonical conventions |
| Live sample | Ten public GETs returned 200 and byte-matched the production artifact | Confirms this audit's baseline, not a fresh full-site live crawl |
| Structured data | JSON-LD parses across the 139 HTML pages; 111 pages contain `FAQPage` | Parse success is not claim verification or rich-result eligibility |
| Territory claims | Homepage Service JSON-LD says `areaServed: Worldwide`, in static HTML and reachable client module | Unsupported by a verified territory matrix in inspected material; verify, qualify or remove through a separate approved correction |
| Languages | Public Typeform configuration says `language: en`; no `translation_languages` key observed | No verified non-English form or support capability. `auto_translate: true` alone does not prove published translations |

Eight newer BlogPosting schemas use `inLanguage: en-US`; that describes content language, not US service eligibility. No verified support-language list was found. The `.io` domain does not require a country-domain migration: Google treats it as generic. [G01]

Evidence, counts, live paths and official URLs are in [SOURCES.md](/Users/emilsoujeh/spacemusic/marketing/multilingual-research-20260916/architecture/SOURCES.md).

## Architecture constraints

The deployed marketing site serves pre-rendered HTML from Cloudflare Pages, then mounts a code-split React application. This is **not evidence of request-time SSR**. The entry imports the vendor's `createRoot` alias and calls `.render(...)`, rather than hydrating the existing markup. There are 63 reachable JavaScript modules from the current entry. Existing routes are unprefixed English routes with a wildcard NotFound route; no locale routing was found.

[SEOHead](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/assets/SEOHead-C4J8_WVH.js:1) emits client canonicals, metadata and JSON-LD, defaults omitted canonicals to the homepage, and constructs English breadcrumbs. Copying HTML into a locale directory while retaining these modules risks translated content being replaced, wrong metadata, English links or NotFound after JavaScript starts. This is a code-derived risk, not a browser-tested failure in a nonexistent locale.

The `web` gitlink is empty locally. Existing guarded builders modify the complete artifact and version changed client dependencies; [the wordmark builder](/Users/emilsoujeh/spacemusic/scripts/build-wordmark-preview.mjs:1) demonstrates this dual-surface release process. Do not deploy `seller_ui`, `admin_ui` or an unrelated backend as the marketing build.

**Recommended pilot implementation, subject to approval:** add a small reproducible static locale generator with reviewed content and minimal isolated JavaScript. Do not attach the English SPA entry to its output. Use full-document links when crossing between this pilot and the existing application. For a wider multilingual site, first restore the actual marketing source and establish a reproducible build, then implement shared locale-aware components. Neither path needs a wholesale framework migration merely for SEO. Pre-rendering also serves crawlers that do not execute JavaScript. [G09]

## URL and discovery contract

1. Leave English at its current URLs, including `/`, `/apply/`, articles and text resources. Do not move it to `/en/`, rename legacy slugs, or redirect the existing 141 pages for this project. New pages can use `/{language}/.../`. Start with a language code, not a country claim; `/sv/` would be an example, not a selected market.
2. Keep content deterministic by URL. Provide ordinary language-switch links, with an explicit English fallback where a translation is unavailable. No IP, inferred country, browser-language or cookie-based forced website redirects. Avoid language query parameters as indexable website URLs. [G01, G04]
3. Give each genuine translation its own absolute self-canonical. Never canonicalize a translated page back to English as a substitute for managing quality. Keep initial HTML and client metadata consistent; canonical signals are preferences, not indexing guarantees. Same-language regional duplicates need a separate consolidation decision. [G03]
4. For this pilot, generate **sitemap-based hreflang only** from one reviewed page-family manifest. Google treats HTML, headers and sitemap annotations as equivalent. Include the page itself and reciprocal equivalents, absolute URLs, valid language codes and optionally `x-default`. Proposed fallback: the corresponding English page, not the homepage for every article. Untranslated articles have no invented alternate. [G02]
5. Retain every existing `<loc>` and add only published canonical translations. Add the XHTML namespace and alternate children to the paired sitemap entries. No draft, redirect, error or noindex target in those clusters. A single sitemap is sufficient at this size; splitting by language or content type is an operational choice, not a Google requirement. Use truthful significant-update dates, not deploy-time freshness resets. [G02, G10]
6. Missing translation routes must not return a generic English homepage with HTTP 200. Plan real error responses for unbuilt locale paths and test hosting fallback behavior. Do not add translation links before the target exists. [G09]

## Translation and operating model

Maintain one page-family manifest containing: stable content ID; English URL; approved locale URL; source revision/hash; translator; actual subject reviewer; claim evidence; territory scope; policy version; intake language; approval status; review date; and next-review trigger. Generate sitemap alternates, language selectors and locale metadata from it. Missing approval or stale source content blocks publication.

Translate the full user journey, not just navigation: body, headings, titles, descriptions, breadcrumbs, image alt text, structured-data strings, form prompts, validation, consent, failure recovery, confirmation and follow-up expectations. Use a terminology glossary for masters, publishing, royalties, rights share, sale versus advance, and hypothetical valuation. Human review must check legal/commercial meaning and numbers; machine translation may draft, not approve. Accurate, useful AI-assisted work is not automatically spam, but mass low-value translation aimed at rankings is unsafe. [G01, G05, G06]

Keep supported website languages, response/support languages, seller eligibility, rights territories, contracting entity and payment currencies as **separate facts**. Assign an accountable owner for each. Do not invent an address, local office, country customer base, local buyer status or `LocalBusiness` markup. Do not turn a translated US example or PRO procedure into jurisdiction-specific advice. Use qualified advisers where necessary; this audit is not a legal compliance opinion.

### Intake is a separate release dependency

The standalone [Apply page](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/apply/index.html) loads Typeform only after Start, with an explicit Formspree short-form alternative. English runtime errors and confirmations also live in [the intake module](/Users/emilsoujeh/spacemusic/marketing/typeform-intake/intake.mjs:1). Translate both paths and test the privacy links. Keep no-upload, no-payment, no-obligation and separate optional marketing consent semantics.

Current Typeform docs require an eligible plan for native multi-language forms; local records establish Plus historically, not current entitlement. Do not assume the feature is paid for. If entitled, prefer reviewed translations on the existing form over clones. Typeform documents `typeform-lang` for an already-configured translation; test explicit website-language selection in the actual embed. Do not rely on automatic browser-language selection or assume vendor language codes equal Google hreflang codes. [T01]

The embed currently has `transitiveSearchParams: []` and passes only filtered public source paths. Any locale setting must be an explicit allowlisted value, not arbitrary query forwarding. Preserve question/choice IDs and branch logic. The [notification Worker](/Users/emilsoujeh/spacemusic/marketing/typeform-intake/notification-worker/worker.mjs:81) rejects other form IDs and expects specific email-field IDs; cloned localized forms would require an approved integration change, not just a new embed link. Typeform responses remain the record and email remains an alert.

Require reviewed, synchronized provider translations, not empty language rows that may trigger automatic translations under Typeform's documented legacy behavior. [T02] Recheck owner, representative, partnership, known/unknown revenue and branch-back paths. Preserve decimal-comma/point validation, self-reported currency and uncertain rights answers. Currency input does not promise settlement in that currency. Verify receiver records and alerts only in an authorized QA phase; this audit submitted nothing.

If a fully localized intake is not yet feasible, a limited informational pilot could explicitly disclose that the form and correspondence are in English before the CTA. That is not an end-to-end localized service and requires owner acceptance. Otherwise defer the conversion pilot.

### Pricing, privacy and measurement

Use the approved [pricing policy](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/pricing.md:1) as the commercial reference: free application and initial review, no listing fee/auction commission, no obligation, conditional review timeline, bank payment after agreement and transfer requirements. Preserve the distinction between an initial offer in typically 5-7 business days after relevant information and actual payment. `$0 / EUR 0` does not establish paid pricing, FX handling, taxes or all-country bank coverage. No paid report launch belongs in translation work.

The live [privacy policy](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/privacy/index.html) names Typeform, Formspree, Cloudflare, Resend and Google Workspace, rejects an EU-only processing promise, and separates marketing opt-in. A localized notice requires qualified review of actual processing and applicable obligations. Reconcile its legacy newsletter language with the nonfunctional-newsletter flag before translating that promise. An English notice merely linked from a translated CTA is not evidence of adequate localized consent/compliance.

The current inline `spaceFunnel.publicPath` allowlist contains the existing 141 public paths; unknown locale paths are rejected. It also recognizes the unprefixed Apply route. Locale traffic and source attribution will be incomplete unless this allowlist and CTA recognition are deliberately extended. Preserve filtering of queries, fragments, personal data, answers and financial figures. Separate intake submissions from qualified seller leads and closed transactions.

## Do not translate yet

These six articles are on hold under [CONTENT-REVIEW.md](/Users/emilsoujeh/spacemusic/marketing/editorial-20260916/CONTENT-REVIEW.md:14). Keep their English URLs; correction requires separate approval.

| Existing article slug under `/blog/` | Gate |
| --- | --- |
| `maximizing-your-lo-fi-catalog-value/` | John Doe attribution, claimed experience, multiples and market assertions |
| `streaming-royalties-guide-for-ambient-music/` | Jane Smith attribution, artist-experience claim and payout/royalty explanations |
| `why-selling-partial-rights-makes-sense/` | John Doe attribution, examples and commercial claims |
| `how-to-register-your-ambient-music-with-pros/` | Michael Brown attribution, current procedures and territory applicability |
| `case-study-ambient-producer-catalog-sale/` | Source documents and permission for the claimed $85K/year to $765K transaction |
| `future-of-ai-in-ambient-music/` | Michael Brown attribution, dated tool claims and unsupported monthly-track estimate |

The current production HTML still presents the named Person bylines without the preview's unverified-contributor notice. A visual redesign is not fact-checking. Align visible attribution, metadata and JSON-LD after a real review; do not invent replacement credentials or refresh dates to imply one.

Also defer bulk translation of genre multiples, streaming rates, buyer comparisons, market statistics, tax/PRO/legal guides and legacy view counts until their individual claims and regional applicability are rechecked. The current selling guide still contains broad valuation/timeline claims; its pending rewrite is not the source of truth. `/data/space-market-index/` and `/data/conversion-intelligence/` contain loading states and benchmark/analytics claims in the static artifact; data availability and substantiation were not verified. Do not scale these as translated landing pages.

First candidates, after approval, are the core service explanation, process, narrowly reviewed seller preparation content, pricing/privacy information and the honest intake handoff. Review even these before reuse; prior publication is not blanket approval of every country or translation.

## Google AI eligibility, not an AI boost promise

Google requires indexed, snippet-eligible content for AI supporting links. Technical compliance does not guarantee indexing or selection. [G07] Newer official guidance additionally requires inclusion through Search Console's Search generative AI control. The documented worldwide rollout was August 31, 2026; verify the domain and inherited locale-property setting with the owner. This audit did not access or change that setting. [G08, G12]

Google now explicitly says it ignores `llms.txt` for visibility/rankings and does not require special AI markup. Keep the existing URL for compatibility and factual maintenance, not a promised GEO benefit. Routine FAQ schema has no demonstrated guaranteed AI boost. Google stopped showing FAQ rich results on May 7, 2026 and removed the documentation June 15; older health/government-only guidance is no longer the current feature status. Preserve useful answers, not schema quotas. [G08, G11]

Do not equate training-bot permissions with search inclusion. Googlebot and Search controls matter; `Google-Extended` is not an AI citation switch. Check other search providers separately before making provider-specific claims. No ranking, conversion or citation lift was measured here.

For follow-up, obtain equal-period page/country organic reports, index/canonical checks, qualified inquiries and source-path reconciliation. Google's newly documented Generative AI performance report supplies AI impressions by page/country/device; it is not a complete all-assistant citation or conversion report. Availability and data for SPACE were not checked. [G13]

## Incremental gates

1. **Approve scope and claims.** Confirm one supportable language and service boundaries using the other agents' research; resolve Worldwide/support claims; appoint translator, subject reviewer and policy owner. Freeze excluded content.
2. **Build a preview-only slice.** Base it on the latest verified production artifact at implementation time, not the editorial preview. Build a small complete journey, reviewed locale manifest, metadata, sitemap pairs and explicit language choice. Keep unfinished translations private or preview-noindex and out of production discovery.
3. **Verify before release.** Assert `baseline URLs` is a subset of `candidate URLs`; all 141 retain their paths, canonical targets and intended status. Diff unrelated copy/metadata/assets. Check raw HTML, JavaScript-on/off behavior, deep links, history, locale switching, true errors, hreflang reciprocity, policy parity, mobile accessibility, intake fallbacks and privacy-safe attribution. Browser testing is a future launch gate, not something performed in this audit.
4. **Publish only after owner approval.** Preserve hosting files, existing Worker and response store. Reuse the established performance gate: investigate a homepage LCP regression exceeding both 10% and 250 ms in comparable three-run mobile medians. Check that preview noindex cannot reach production. Retain the entire immediate prelaunch artifact for rollback; presently that would be the wordmark snapshot, unless a newer release intervenes.
5. **Expand only on evidence.** Review index selection, correct-language journeys, inquiry quality, maintenance cost and observed AI impressions after a meaningful comparison period. No automatic 141-by-language or genre-by-country rollout. Pause new locales when source changes cannot be reviewed promptly.

## Limits

No code, production, provider, policy, Search Console or form settings were changed. No browser automation, account-response access, form submissions or keyword-volume research was used. No callable subagent runtime was available in this session; this is the architecture slice alongside the other agents' research, not a claimed independent multi-agent consensus. Writes are limited to this directory's brief and source ledger.
