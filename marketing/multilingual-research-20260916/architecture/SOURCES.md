# Architecture audit: sources and evidence

Accessed: 2026-09-16, Europe/Stockholm. Read-only local inspection, public HTTP GETs and web retrieval. No browser automation or form submission.

## Official sources

These are primary sources. Short notes identify their relevance; architecture choices in BRIEF.md are recommendations, not promises from Google or Typeform.

| ID | Source URL | Relevance |
| --- | --- | --- |
| G01 | [Google: multilingual and multi-regional sites](https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites) | Language versus country targeting, distinct URLs, visible language, user choice, generic `.io`, regional duplicates |
| G02 | [Google: localized versions](https://developers.google.com/search/docs/specialty/international/localized-versions) | Reciprocal/self hreflang, equivalent implementation methods, valid codes, optional fallback, sitemap structure |
| G03 | [Google: canonical URLs](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) | Consistent canonical signals, same-language preference, HTML/client agreement |
| G04 | [Google: locale-adaptive crawling](https://developers.google.com/search/docs/specialty/international/locale-adaptive-pages) | Discovery limitations of location/language negotiation; Googlebot lacks Accept-Language |
| G05 | [Google: spam policies, scaled content abuse](https://developers.google.com/search/docs/essentials/spam-policies#scaled-content) | Manipulative low-value page generation, including translation-based transformations |
| G06 | [Google: generative AI content guidance](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content) | Accuracy, usefulness, metadata quality and creation context |
| G07 | [Google: AI features and your website](https://developers.google.com/search/docs/appearance/ai-features) | Index/snippet eligibility and no inclusion guarantee; older overview needs G08/G12 supplementation |
| G08 | [Google: optimizing for generative AI Search](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide) | Current AI guidance; expressly rejects llms.txt ranking effects and special-schema requirements |
| G09 | [Google: JavaScript SEO basics](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics) | Rendering, pre-rendering, canonicals, crawlable links and meaningful error status |
| G10 | [Google: build and submit a sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) | Canonical URLs and truthful lastmod; priority/changefreq are ignored |
| G11 | [Google Search documentation changelog](https://developers.google.com/search/updates) | May 8 entry: FAQ rich results stopped May 7, 2026; June 15: docs removed and llms.txt clarification |
| G12 | [Search Console: Search generative AI control](https://support.google.com/webmasters/answer/16908024) | Worldwide August 31, 2026 rollout; default inclusion, parent/child inheritance, separate training control |
| G13 | [Search Console: Generative AI performance report](https://support.google.com/webmasters/answer/16984139) | AI impression reporting and limitations; worldwide August 31, 2026 rollout notice |
| T01 | [Typeform: create multi-language forms](https://help.typeform.com/hc/en-us/articles/23541138531732-Create-multi-language-forms) | Eligible plans, reviewed translations, browser selection, explicit language parameter and response languages |
| T02 | [Typeform developer documentation: translations](https://www.typeform.com/developers/create/translations/) | Translation status, stale-source detection and legacy automatic-translation behavior |
| T03 | [Typeform: multiple-language workaround](https://help.typeform.com/hc/en-us/articles/360058731891-Create-forms-in-multiple-languages-workaround) | Separate forms are an alternative, but require separate integration review here |

### Currency of guidance

The old [FAQ documentation address](https://developers.google.com/search/docs/appearance/structured-data/faqpage) redirected to Google's changelog during this audit. Do not cite the older government/health eligibility rule as today's availability. G08 and G12 also add information not present in the older G07 overview. G13 means the older blanket statement that AI performance cannot be viewed separately is no longer sufficient; the new report is specifically an impressions report.

The `ai-seo` and `seo-audit` skills, plus the latter's international reference, were read. They are workflow prompts, not evidence. This audit does not adopt their unsupported universal percentage-lift claims, blanket bot/training conflations, routine FAQ/llms prescriptions, or an all-languages-must-be-prefixed rule that would force an unnecessary English URL migration. `x-default` is optional, not a mandatory pass/fail requirement for every site. No Google requirement to split sitemaps by content type was established.

## Local release and implementation evidence

| Evidence | What was inspected |
| --- | --- |
| [Marketing release record](/Users/emilsoujeh/spacemusic/marketing/RELEASE.md:9) | Current production artifact, 141-URL contract, separate editorial preview, preservation and performance gates |
| [Editorial correction ledger](/Users/emilsoujeh/spacemusic/marketing/editorial-20260916/CONTENT-REVIEW.md:5) | Six unverified contributor/claim holds; unchanged author metadata; newsletter/view-count limitations |
| [Production sitemap](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/sitemap.xml) | All 141 unique locations, 20 lastmod entries, no hreflang extension |
| [Production homepage](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/index.html) | Pre-rendered content, current entry, English language, canonical, Worldwide Service claim, inline analytics allowlist |
| [SEOHead client module](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/assets/SEOHead-C4J8_WVH.js:1) | Canonical default/normalization, English breadcrumb creation, metadata/schema output, no locale alternates |
| [Current React entry](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/assets/index-article-360c41838159-quietseo-fd17485db4c3-intent-50f4feb4050e-links-0798455b493c-brand-ba3115eb02ed.js:1) | English route map, NotFound fallback, 63 reachable modules, aliased createRoot/render startup |
| [React vendor module](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/assets/vendor-DhPEFgb5.js) | `ay` export maps to createRoot; entry imports it as `m` |
| [Wordmark release builder](/Users/emilsoujeh/spacemusic/scripts/build-wordmark-preview.mjs:1) | Full-artifact copying, guarded static/client edits, versioned import graph |
| [Standalone Apply](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/apply/index.html) | English guided-form entry, Formspree alternative, consent/policy links, confirmation and analytics |
| [Intake source](/Users/emilsoujeh/spacemusic/marketing/typeform-intake/intake.mjs:1) | Form ID, English runtime strings, filtered source metadata, no arbitrary query forwarding |
| [Notification Worker](/Users/emilsoujeh/spacemusic/marketing/typeform-intake/notification-worker/worker.mjs:81) | Single form/field IDs, completed-response handling, privacy-preserving alert rather than answer storage |
| [Form specification](/Users/emilsoujeh/spacemusic/marketing/typeform-intake/FORM-DRAFT.md:3) | English wording, historical Plus plan, conditional revenue/currency, stable references, uncertainty semantics |
| [Typeform publish log](/Users/emilsoujeh/spacemusic/marketing/typeform-intake/PUBLISH-LOG-20260916.md:1) | Later production status supersedes old draft-status prose; historical QA is not rerun evidence |
| [Pricing](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/pricing.md:1) | Free initial review; conditional offer/payment; no locale/country price schedule |
| [Privacy](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/privacy/index.html) | Provider disclosures, retention, opt-in, international processing; retained newsletter wording |
| [Brand facts](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/.well-known/brand-facts.json:1) | Published direct-buyer offer facts; not an operational country/language eligibility matrix |
| [Robots](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/robots.txt:1), [headers](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/_headers:1), [redirects](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/_redirects:1) | Allowed crawling, sitemap, retained text-resource canonicals and route redirects |
| [llms.txt](/Users/emilsoujeh/spacemusic/tmp/wordmark-preview-v1-20260916/llms.txt:1) | Existing 141-URL inventory member; no measured AI uplift |

`git ls-files --stage web` reports a mode-160000 gitlink, commit `fba93fd03ea141373aa42a3818c6d9a02174e79d`; directory listing is empty. No submodule retrieval or source replacement was attempted.

## Fresh read-only checks

Node filesystem/XML-tag inspection and inert JSDOM parsing were used. Page scripts were not executed. JSON-LD was parsed from raw HTML, not inferred absent from a text-only web extractor. Client findings came from the reachable production module graph, not obsolete retained assets.

| Check | Result |
| --- | --- |
| Unique sitemap locations / matching local files | 141 / 141 |
| HTML / non-HTML | 139 / 2 |
| HTML language declarations | 139 `en` |
| Matching unique HTML canonicals | 139 |
| HTML/sitemap hreflang | 0 |
| Invalid JSON-LD payloads | 0 |
| HTML pages with FAQPage | 111 |
| Restrictive noindex/nosnippet/max-snippet:0 metadata found | 0 |
| Six flagged production article Person bylines | Present; preview unverified-contributor notice absent |

Inventory breakdown: home 1; Apply 1; calculator 1; pricing 1; llms 1; process 1; streaming-rates 8; tools 1; guides 6; glossary 34; compare 17; sell 39; data 3; brand facts 1; about 1; privacy 1; blog 15 (directory plus 14 articles); for 9. Total 141.

### Public HTTP sample

All ten paths below returned HTTP 200, without X-Robots-Tag, and their response bodies exactly matched the local wordmark artifact on 2026-09-16:

- [Sitemap](https://spacemusic.io/sitemap.xml)
- [Homepage](https://spacemusic.io/)
- [Apply](https://spacemusic.io/apply/)
- [Privacy](https://spacemusic.io/privacy/)
- [How it works](https://spacemusic.io/how-it-works/)
- [Pricing policy](https://spacemusic.io/pricing.md)
- [llms.txt](https://spacemusic.io/llms.txt)
- [Robots](https://spacemusic.io/robots.txt)
- [Brand facts](https://spacemusic.io/brand-facts/)
- [Flagged case study](https://spacemusic.io/blog/case-study-ambient-producer-catalog-sale/)

The two non-HTML resources returned their expected HTTP canonical Link headers. Live sitemap SHA-256: `035ae44a112073f720a96d6e2738eadbef78888a70f007492e439586f1cab279`. Homepage SHA-256: `495699ecb3427031aa8134f6bb9b9b9dd2fa9cdd7f0c07a478410a9424813238`.

Public [Typeform](https://form.typeform.com/to/xzx5SBJb) GET returned 200 and title `SPACE catalog review`. Embedded public configuration showed `settings.language: en`, `meta.allow_indexing: false`, `auto_translate: true`, English questions/endings, and only `landing_path` / `apply_source_path` hidden fields. No `translation_languages` key was observed. These are configuration observations, not account-entitlement, multilingual-runtime or submission-delivery verification.

## Boundaries and unresolved evidence

The release record's full 532-file/141-live-route verification is inherited evidence. This audit refreshed all sitemap HTML metadata locally and only the ten live resources listed above. It did not run a complete live crawl, JavaScript/browser journeys, rich-result validation, Search Console inspection, response reconciliation, real-user performance analysis or legal review. Account entitlement, support languages, country eligibility, bank coverage, source claims and actual AI impressions remain owner-verification gates. No ranking/traffic/citation gain is inferred from clean metadata.

Only `BRIEF.md` and `SOURCES.md` in this architecture directory were written, using apply_patch. Existing dirty worktree files and other agents' research were left untouched.
