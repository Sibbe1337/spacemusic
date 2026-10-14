# Clear review journey, published September 8, 2026

## Scope

This package implements the first three approved UX priorities, not the paused
redesign or a sitewide performance rewrite. Start from the verified
`tmp/funnel-stage4-v2-20260907` release. The public `web` gitlink is unpopulated;
do not replace the marketing release with an unrelated frontend build.

- Homepage: correct the old income minimum, fixed genre multiples, guaranteed
  payment/price language and misleading calculator promotion. Keep all sections,
  eight FAQ subjects and the catalog-selling topic in H1. The second H1 line
  now invites a free review instead of promising cash in days.
- Process page: explain the initial short form, private evidence follow-up,
  individual review, independent advice and conditional payment. Retain all
  five steps and the existing URL/H1.
- Genre index: use visitor-facing wording, individual-review labels instead
  of headline multiple bands, and emphasize review over the calculator.
- Shared navigation and primary buttons: use the same review action. In-text
  contextual article links retain their descriptive wording. The footer now
  describes review across genres rather than implying a mood-only restriction.
- Apply: same required and optional questions, recipient, payload contract and
  analytics protections. Add autofill hints, working home/privacy/policy links,
  visible error recovery and a focused confirmation with next steps. Hide the
  empty form after success to avoid inviting duplicate submissions; another
  catalog requires an explicit action. No automatic email delivery is claimed.
- No fake seller-terms page was added: the existing pricing/offer policy and
  privacy notice open in separate tabs without clearing the form.
- The closed mobile menu is inert and aria-hidden, with aria-expanded on the
  toggle. Primary Apply links navigate straight to the standalone document,
  while the legacy route bridge remains for programmatic navigation.

Existing long-form articles and individual genre landing-page claims were not
comprehensively fact-checked in this package. They need a separate evidence
review; do not claim every historical market claim on the site is now verified.
No content sections, pages or sitemap URLs are deleted. Corrections replace
unsupported claims; the stylesheet only accommodates the longer CTA and Apply
focus/confirmation/link states, not a new visual theme or font system.

## Reproducible sources

`copy.json` is the reviewed exact old/new copy map. The guarded builder parses
JavaScript string literals rather than doing unbounded text replacements. It
walks the active module graph, preserves all old files byte-for-byte, and
creates 37 versioned modules for changed code and its importers. A common
release fingerprint handles cyclic ESM dependencies without overwriting old
cacheable assets. The retired calculator/form are no longer warmed by navbar
prefetch. Server-delivered HTML receives matching copy/CTA changes.

Build the standalone Apply with the existing environment:

```sh
env VITE_SPACEMUSIC_API_URL= VITE_FORM_ENDPOINT=https://formspree.io/f/mpwdnokz npm run build -- --base=/apply/ --outDir=../../tmp/journey-apply-build
```

Run that command from `services/seller_ui`, then from the repository root:

```sh
node scripts/build-journey-release.mjs tmp/funnel-stage4-v2-20260907 FRESH_OUTPUT tmp/journey-apply-build
node scripts/prerender-funnel-page.mjs FRESH_OUTPUT /
node scripts/prerender-funnel-page.mjs FRESH_OUTPUT /how-it-works/
node scripts/prerender-funnel-page.mjs FRESH_OUTPUT /sell/
```

The source baseline is pinned deliberately. Do not run this old-source builder
as a replacement for a newer verified release. Extend it from the newer source
after reviewing that release's changes. `marketing/RELEASE.md` is authoritative.

## Verification

- `node scripts/journey-support.test.mjs`
- `node scripts/check-journey-release.mjs BASELINE RELEASE`
- `node scripts/check-journey.mjs RELEASE_OR_ORIGIN`
- `node scripts/check-funnel.mjs RELEASE_OR_ORIGIN`
- `env EXPECT_DIRECT_APPLY=1 node scripts/check-funnel-tracker.mjs RELEASE`
- All existing 33 Apply-navigation checks, homepage social metadata, production
  SEO, byte verification and plaintext routing checks.

The journey suite covers 320, 390, 768, 1024 and 1440px, keyboard menu controls,
confirmation focus, unchanged form questions, policy links preserving input,
checklist navigation and no-JavaScript content/contact fallback. All Formspree
and analytics POSTs are intercepted. No synthetic event or test lead is sent
to production. The existing math and tracking privacy tests also pass.

The real Plausible script initially emitted two `/apply/` pageviews when a
router link first entered the SPA route and then redirected to the standalone
form. The failing intercepted test was reproduced. Direct document links now
emit only `/calculator/` and `/apply/` in that two-page journey, while the
programmatic fallback still reaches the correct Apply. This is not proof of
real dashboard reporting or received/qualified leads.

The direct-link transform only changes the imported router Link component,
not Navigate. A regression test protects the existing marketplace redirect;
all 33 navigation checks pass on the final v4 Cloudflare preview. Prerendering
deduplicates identical runtime-injected styles and checks static content
without waiting for external resources.

Native Apply clicks are checked by waiting for the destination document,
correct heading and working form, rather than letting an unrelated resource's
load event exhaust the short click-action timeout. Navigation still has a
30-second limit, and the 10-second form/element assertions remain in place.
The journey test reports failed first-party requests and browser errors on
failure; transient network interruptions were rerun without changing release
files or suppressing application assertions.

A popup test initially read the privacy document during React's transient
empty render after DOMContentLoaded. It now waits for the expected policy
content, not just that load event; the content and links work in preview.

## Performance and release

Three-run mobile Lighthouse baseline: homepage 5884 ms, Apply 1951 ms.
Reports are in `tmp/journey-qa/before/`. The final v4 homepage measured
5891 ms, a 7 ms / 0.1% increase, in three isolated Lighthouse 13.4.1 mobile
runs (`tmp/journey-qa/v4-final-isolated/`). This is within the agreed threshold
of an increase exceeding both 10% and 250 ms. Apply measured 1951 ms
(`tmp/journey-qa/after/`); its HTML, CSS and JS are byte-identical from that
three-run v2 measurement through v4. An earlier concurrent browser-test run
is not used for the final homepage comparison. The homepage's approximately
5.9-second lab LCP remains a separate performance opportunity, not a solved
Core Web Vitals issue.

Final snapshot: `tmp/journey-v4-20260907`, 299 public files plus `_headers`
and `_redirects`. Preview: https://4e9bddc4.spacemusic-a6n.pages.dev.
Production: https://6c66c5dd.spacemusic-a6n.pages.dev, published September 8
at approximately 07:07 CEST. All public files match https://spacemusic.io.
Rollback: `tmp/funnel-stage4-v2-20260907`, deployment `7c1307d4`.

Live byte/SEO checks, all 33 Apply-navigation checks, all seven intercepted
form-response cases, the five-width journey suite, the guide and both article
checks, plaintext routing and social-browser checks all pass. The final local
intercepted test using the real Plausible script also passes: one pageview for
the calculator and one for Apply, with privacy-safe events and no requests
sent to analytics or the real form receiver.
No claim about improved rankings, conversions or real-user Core Web Vitals is
made from these lab tests. The existing 28/56-day follow-up remains scheduled;
the September 8 journey change is annotated in `marketing/funnel/README.md`
when interpreting the same cohorts.
