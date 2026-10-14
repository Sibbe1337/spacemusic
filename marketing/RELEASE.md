# Current Marketing Release

Production: https://2a01bd95.spacemusic-a6n.pages.dev

Public site: https://spacemusic.io/

Cloudflare Pages project `spacemusic`, production branch `main`.

Current verified release directory: `tmp/serp-preview-v3-20261008`.
Despite its build-directory name, this is the published production artifact.
Approved revision: `ef3cecf6bba1`.

Published October 8, 2026, approximately 07:10 UTC, after the owner's explicit
"publicera" approval. Five existing pages refreshed: valuation guide, Calculator,
Royalty Exchange comparison, selling-rights guide and label-funding article.
No new URLs or design overhaul. The 144 sitemap URLs, H1s, canonicals, Apply,
tracking, calculator mathematics, robots, headers and redirects are preserved.
See `marketing/serp-20261008/README.md` and `publication.md` in that directory.

Before publishing, all 599 public files on spacemusic.io matched the prior
release. Re-ran 3,061 preservation/browser checks and the Jev publication gate:
374 new sentences, four documented exceptions, zero blocking flags. Run
`node scripts/jev-publish-gate.mjs CANDIDATE_DIR` before every future deploy.

Verified live October 8, 2026 at 07:11 UTC: all 639 public files match this
artifact byte for byte; `check-production-seo.mjs` passes for all 144 sitemap
URLs. All five pages pass mobile/desktop metadata and schema parity, keyboard
FAQ and Apply navigation checks. The calculator returns $24,000 for
1,000 x 12 x 4 x 50%. No browser errors, real submissions or synthetic analytics
events were generated. Test receipt: `marketing/serp-20261008/qa/live-results.json`.

Immediate rollback: complete `tmp/growth-preview-v1-20260930`, deployment
https://29e7801c.spacemusic-a6n.pages.dev. Redeploy that snapshot to `spacemusic` /
`main`, retaining `_headers` and `_redirects`. Do not deploy the preview server
or its response-only noindex/CSP headers.

## Previous growth release (September 30)

Production: https://29e7801c.spacemusic-a6n.pages.dev

Public site: https://spacemusic.io/

Cloudflare Pages project `spacemusic`, production branch `main`.

Current verified release directory: `tmp/growth-preview-v1-20260930`.
Despite its build-directory name, this is the published production artifact.

Published September 30, 2026 after the owner's "godkänn"; the owner ran the deploy
command. Jev-driven growth release on top of the authenticity v2 release: "Next steps"
links on 131 pages, Music Catalog Deal Tracker (52 deals, 11 stated multiples), streaming
platform catalog sizes and Deezer prices pages (sitemap now 144 URLs), sourced multiples
in the valuation guide, answer-first openings on 16 pages. Run
`node scripts/jev-publish-gate.mjs CANDIDATE_DIR` before every future deploy.
See `marketing/growth-20260930/README.md`.

Verified after publishing: homepage, the 3 new pages, a glossary page, valuation guide,
Deezer page, Calculator, Apply, sitemap, robots and llms.txt match the release files byte
for byte; `check-production-seo.mjs` passes for all 144 sitemap URLs; the new pages and
the next-steps block render live with no browser errors. Pre-release suite: 2,439 checks
on 138 pages; Jev gate 0 blocking.

Immediate rollback: complete `tmp/authentic-preview-v2-20260929`, deployment
https://a090bdaf.spacemusic-a6n.pages.dev. Redeploy that snapshot to `spacemusic` /
`main`, retaining `_headers` and `_redirects`.

## Previous authenticity release (v2)

Production at the time: https://a090bdaf.spacemusic-a6n.pages.dev

Public site: https://spacemusic.io/

Cloudflare Pages project `spacemusic`, production branch `main`.

Current verified release directory: `tmp/authentic-preview-v2-20260929`.
Despite its build-directory name, this is the published production artifact.

Published September 29, 2026 after the owner's "godkän"; the owner ran the deploy
command. Authenticity follow-up on top of the v1 rewrite: streaming calculator rebuilt
(own payout per stream, no invented rates or multiples), dead source links replaced
(0 dead of 84), Hipgnosis replaced by Duetti in the buyers guide, all-genres
positioning, schema and label fixes, prerendered links now match hydrated links.
See `marketing/authentic-20260929/README.md`.

Verified after publishing: homepage, streaming calculator, buyers guide, market data,
streams guide, case-study post, Calculator, Apply, sitemap and robots match the release
files byte for byte; `check-production-seo.mjs` passes for all 141 sitemap URLs; the
live streaming calculator computes $4.8K/yr for 100,000 streams at $0.004 with no
browser errors. Pre-release suite: 2,140 checks on 114 pages.

Immediate rollback: complete `tmp/authentic-preview-v1-20260929`, deployment
https://9a8ee461.spacemusic-a6n.pages.dev. Earlier baseline: `tmp/motion-preview-v3-20260929`
(0205d366). Redeploy the chosen snapshot to `spacemusic` / `main`, retaining `_headers`
and `_redirects`.

## Previous authenticity release (v1)

Production at the time: https://9a8ee461.spacemusic-a6n.pages.dev

Public site: https://spacemusic.io/

Cloudflare Pages project `spacemusic`, production branch `main`.

Current verified release directory: `tmp/authentic-preview-v1-20260929`.
Despite its build-directory name, this is the published production artifact.

Published September 29, 2026 after the owner's "godkänt allt annat" approval; the
owner ran the deploy command. Built from `tmp/motion-preview-v3-20260929` with 1,112
reviewed text edits: invented case studies replaced by labelled illustrative
examples, invented authors replaced by SPACE Editorial Team, valuation multiples
removed, external figures cited or removed, factual corrections, Jev-selected
search titles. URLs, links, canonicals and sitemap unchanged. See
`marketing/authentic-20260929/README.md`.

Verified after publishing: homepage, a genre page, the rewritten case-study post,
a comparison page, the valuation guide, Calculator, Apply, sitemap and robots on
spacemusic.io match the release files byte for byte; `check-production-seo.mjs`
passes for all 141 sitemap URLs. Pre-release suite: 2,135 checks on all 113
changed pages. No new performance measurement was taken (text-only change, no new
requests); re-check PageSpeed.

Immediate rollback: complete `tmp/motion-preview-v3-20260929`, deployment
https://0205d366.spacemusic-a6n.pages.dev. Redeploy that snapshot to
`spacemusic` / `main`, retaining `_headers` and `_redirects`.

## Previous motion release

Production at the time: https://0205d366.spacemusic-a6n.pages.dev

Public site: https://spacemusic.io/

Cloudflare Pages project `spacemusic`, production branch `main`.

Current verified release directory: `tmp/motion-preview-v3-20260929`.
Despite its build-directory name, this is the published production artifact.

Published September 29, 2026, after the owner's "godkänner" authorization; the
owner ran the deploy command. Built from `tmp/editorial-preview-v5-20260916`.
Adds only a CSS scroll-driven animation to the existing homepage "Stream it. Or
sell it." comparison table (one inline style block; no new text, elements,
scripts or requests). Unsupported browsers and reduced motion see the previous
table unchanged. See `marketing/motion-20260929/README.md`.

Verified after publishing: homepage, Sell, Calculator, Apply, sitemap and robots
on spacemusic.io match the release files byte for byte; `check-production-seo.mjs`
passes for all 141 sitemap URLs (canonical and robots clean); the animation is
active at 1280 and 390 px with no horizontal overflow and no browser errors.
Pre-release suite: 1,267 preservation/browser checks passed.

Performance: PageSpeed API quota was exhausted, so local Lighthouse 13.4.1
mobile runs were used. Cross-origin medians (spacemusic.io 2937 ms vs preview
3602 ms) differed, but a same-origin control (production build on pages.dev
5005 ms vs candidate 3404 ms) attributes that to the preview origin. Raw reports
are in `marketing/motion-20260929/lighthouse/`. Re-check with PageSpeed.

Immediate rollback: complete `tmp/editorial-preview-v5-20260916`, deployment
https://55284dbb.spacemusic-a6n.pages.dev. Redeploy that snapshot to
`spacemusic` / `main`, retaining `_headers` and `_redirects`.

## Previous editorial release

Previous production: https://55284dbb.spacemusic-a6n.pages.dev

Release directory: `tmp/editorial-preview-v5-20260916`.
It contains 544 public files plus `_headers` and `_redirects`.

Published September 16, 2026, approximately 12:20 UTC, after the owner's
"The blog is approved" authorization. Publishes the reviewed Resources index
and all 14 article layouts, removing visible decorative stock imagery and
flagging unverified legacy contributors without inventing replacements.
Article text, headings, internal links, metadata, canonicals, JSON-LD, all 141
sitemap URLs and the approved standalone Apply flow are preserved. Non-blog
content and layout are unchanged; a scoped stylesheet and versioned module
references support blog navigation. No multilingual rollout, factual-content
rewrite, backend, Worker, DNS, email or payment changes were included.

All 544 public files match live production. All 141 sitemap URLs pass HTTP 200,
canonical and robots checks; no preview noindex reached production. Pricing.md
(24 checks) and llms.txt routing pass. The preservation/link suite passes 2,063
checks and all 13 scenario/tracking/intake tests pass. No real lead was submitted.
Live browser checks confirm Resources, both article templates, the retained
unverified-contributor notice, the article backlink and the correct Apply handoff.

Fresh three-run homepage mobile lab median LCP: 2851 ms before, 2701 ms on the
approved candidate. The >10% AND >250ms regression gate is not triggered. This
does not demonstrate real-user speed, ranking or conversion improvement; the
existing contrast warning remains. See `marketing/editorial-20260916/PERFORMANCE.md`
and `PUBLISH-LOG.md` for scope, source reports, baseline and limitations.

Its rollback was: complete `tmp/wordmark-preview-v1-20260916`, deployment
https://6984da7b.spacemusic-a6n.pages.dev. Redeploy that complete snapshot to
`spacemusic` / `main`, retaining `_headers` and `_redirects`. Preserve the
separate Typeform notification Worker and responses.

Legacy author, case-study and commercial-claim corrections remain outstanding
under `marketing/editorial-20260916/CONTENT-REVIEW.md`. This design approval
does not verify those claims or approve the multilingual research recommendations.

## Pending conversion preview

September 17, 2026 preview only: https://fa09e20b.spacemusic-a6n.pages.dev/.
Candidate `tmp/conversion-preview-v3-20260917` is based on the current verified
editorial production artifact above. Improves homepage audience links, adds
artist/label guidance to Sell, and clarifies the calculator-to-review journey.
All 141 sitemap URLs, existing text/SEO metadata and the approved Apply flow
are preserved. All 581 preview files match, 2,181 preservation checks and all
13 scenario/tracking/intake tests pass. Preview noindex and unchanged production
spot checks are verified. Owner approval and a fresh three-run performance
comparison are still required before production. See
`marketing/conversion-20260917/README.md`. Production remains `55284dbb`.

## Previous wordmark release

Previous production: https://6984da7b.spacemusic-a6n.pages.dev.
Previous release directory: `tmp/wordmark-preview-v1-20260916`.
532 public files plus `_headers` and `_redirects`.

Published September 16, 2026, approximately 10:54 UTC, after the owner's
"approved and delpoy" authorization. Includes the internal-link cleanup and
new monochrome SPACE wordmark in headers, footers and standalone Apply.
All 140 former sitemap URLs remain; restored Resources at `/blog/` makes 141.
Existing page copy, titles, descriptions, canonicals, JSON-LD and application
flow are preserved. No unapproved selling-guide rewrite, backend, Worker,
DNS, email or payment changes are included.

At that publication, all 532 public files matched live production. All 141
sitemap URLs passed HTTP 200, canonical and robots checks, with no preview
noindex on production. All 18
added redirect variants, pricing.md (24 checks) and llms.txt routing pass.
Live homepage, Sell, Resources and Apply were opened and checked. The link
suite passes 6,918 assertions; wordmark preservation passes 2,919; all 13
scenario/tracking/intake tests pass. No real application was submitted.

Fresh three-run homepage mobile lab median LCP: 2701 ms before and 2701 ms after.
No regression at the agreed >10% AND >250ms threshold. This is not proof of a
real-user speed, ranking or conversion improvement. The existing contrast
warning remains. See `marketing/identity-20260916/PUBLISH-LOG.md` for reports,
Search Console baseline, follow-up method and limitations.

That release's rollback: complete `tmp/buyer-intent-v2-20260916`, deployment
https://02276b90.spacemusic-a6n.pages.dev. Redeploy that complete snapshot to
`spacemusic` / `main`, retaining `_headers` and `_redirects`. Preserve the
separate Typeform notification Worker and responses.

## Approved editorial preview history

Blog preview: https://b5189220.spacemusic-a6n.pages.dev/blog/.
Candidate `tmp/editorial-preview-v5-20260916`, based on the verified
wordmark predecessor above. Redesigns Resources and all 14 articles; removes visible
stock imagery, flags unverified contributors and preserves article text/SEO.
All 544 public preview files match the artifact; all 141 sitemap URLs pass
HTTP/canonical/noindex checks. 2,063 preservation checks and 13 existing
scenario/tracking/intake tests pass. Browser QA covers mobile, contents controls,
table scrolling and the correct Apply handoff. It is now published as `55284dbb`.

Owner approval and the fresh performance gate were completed September 16.
Legacy attribution/content correction remains separately flagged, not completed.
See `marketing/editorial-20260916/README.md` and `CONTENT-REVIEW.md`.
Immediate rollback for the published editorial release is the previous complete
`tmp/wordmark-preview-v1-20260916` artifact, not an older design preview.

## Previous buyer-intent release

Previous production: https://02276b90.spacemusic-a6n.pages.dev

Public site: https://spacemusic.io/

Cloudflare Pages project `spacemusic`, production branch `main`.

Previous verified release directory: `tmp/buyer-intent-v2-20260916`.
It contains 446 public files plus `_headers` and `_redirects`. Always retain
both hosting control files when preparing a new release.

Published September 16, 2026, approximately 09:18 UTC, after the owner's
"Godkant. Fortsatt sen." approval of preview https://9b4782a6.spacemusic-a6n.pages.dev.
Includes the approved whole-site quiet design, all-genre positioning, the
independent-label funding article and corrected Duetti comparison, followed by
the sale-versus-loan, partial-versus-full-sale and independent-catalog-owner
refreshes. No paid report, backend, DNS, Typeform configuration or email changes.
All 139 prior sitemap addresses remain; one approved article makes 140.

All 446 public files match live production. All 140 sitemap URLs pass HTTP 200,
canonical and production robots checks. No preview noindex leaked to production.
The approved standalone Apply flow and calculator logic are retained. The
buyer-intent preservation suite passes 4,633 checks and 13 scenario/tracking/
intake tests pass. Current browser verification covers 26 Apply links across
seven routes, back/forward in the in-app browser, three direct Apply variants
and mobile keyboard-menu navigation. It is not a rerun of the historical
33-case script, whose old form assumptions no longer match guided Typeform.
Pricing/llms routing tests pass against the current release fixtures.

Homepage mobile lab median LCP is 3001 ms before versus 2701 ms on the approved
preview, three runs each in PageSpeed Insights. Both have an occasional TBT
outlier; this is not proof of real-user improvement. The current Search Console
baseline and equal-period follow-up are in
`marketing/buyer-intent-20260916/RELEASE-BASELINE.md`. No measured ranking or
AI-citation effect, fresh lead reconciliation or verified conversion lift.

That release's rollback baseline: `tmp/typeform-intake-release-v3-20260915`,
deployment https://6dea26c1.spacemusic-a6n.pages.dev. Redeploy that complete
snapshot to `spacemusic` / `main` if necessary. Preserve Typeform responses
and the separately deployed notification Worker. Do not publish subsequent
selling-guide drafts without approval.

See `marketing/buyer-intent-20260916/PUBLISH-LOG.md` for verification and scope.

## Internal-link release layer

`tmp/internal-links-release-20260916` is the navigation-only layer built from
the buyer-intent release, not from the unapproved selling-guide rewrite.
It fixes broken routes, restores `/blog/` as a Resources directory, and aligns
server and client navigation. All 140 existing sitemap addresses remain; the
directory makes 141. It is now published as part of the wordmark release above.

Scope, audit and original preview checks are documented in
`marketing/internal-links-20260916/README.md`.

## Previous Typeform release

Published September 16, 2026, approximately 06:00 UTC, after explicit owner
deployment authorization and verification of preview
https://d4f64dbd.spacemusic-a6n.pages.dev. The existing standalone Apply page now
loads the guided Typeform only after Start, with the original Formspree receiver
available as an explicit short-form alternative, never an automatic duplicate.
The privacy policy is updated in server HTML and client content. Other pages
change only their versioned entry-module reference; their content and design
are unchanged. Titles, descriptions, canonicals, robots, structured data,
hosting rules and all 139 sitemap URLs are preserved. All former assets remain.
No report/payment launch, old design preview or unrelated backend was deployed.

All 338 public files match live production. All 139 sitemap URLs passed status,
canonical and robots checks; production has no preview noindex. Existing
pricing.md (24 checks) and llms.txt routing tests pass. Live Apply embed and
client-rendered privacy content were inspected. 11 intake DOM tests and 22
notification Worker/runtime/credential tests pass; these are NOT the old 33
Apply-navigation browser tests. Three clearly labelled Typeform QA routes were
reconciled with stored answers and delivered internal notifications. No real
customer data, Formspree test lead or automatic customer email was sent.

The isolated signed-webhook Worker is live, using the owner's explicitly
approved existing signing configuration. Typeform responses are the record;
email is an alert. Plausible goal reports, browser branch-back stale-answer
behavior and the full historical browser matrix are not verified. A fresh
PageSpeed request returned 429, so no new three-run mobile LCP comparison is
claimed. See `marketing/typeform-intake/PUBLISH-LOG-20260916.md` for evidence,
operational follow-up and key-state details.

That release's rollback baseline was `tmp/pricing-routing-release-20260910`, deployment
https://a74ea86c.spacemusic-a6n.pages.dev. Redeploy that complete snapshot to
`spacemusic` / `main` if needed; retain Typeform responses and notification data.

## Inherited release history

The September 10 predecessor was published approximately 09:07 UTC, after owner approval and
verification of preview https://4fa0530e.spacemusic-a6n.pages.dev.
Only two hosting rules were added: an HTTP canonical Link header on
`/pricing.md` pointing to `https://spacemusic.io/pricing.md`, and an exact 301
from `/pricing.md/` to `/pricing.md`. Existing `llms.txt` rules are retained.
All 333 public files, content, design, Apply, HTML metadata, robots and all 139
sitemap URLs are byte-identical to the previous release. No Markdown content,
pricing offer, paid report, private catalog data or design preview was published.
See `marketing/pricing-routing/README.md` and its `PUBLISH-LOG.md`.

The September 9 predecessor was published after approval of preview `4dc7fbad`.
Only the calculator's approved headline, explanatory copy and two contextual
links changed in that release. Its calculation, current design and Apply are
unchanged. All 139 sitemap URLs, page titles, descriptions, canonicals, robots
metadata and structured data are retained. The 299 previous public files are
preserved, with 34 new versioned modules; unrelated HTML/importers change only
version references. No other research drafts were published.

It inherits the September 8 release's clarified homepage, process and genre index,
standardizes the free-review action, and improves the existing Apply form's
autofill, error recovery, confirmation and policy links. No questions,
receiver, backend, page sections or sitemap URLs were removed. Unsupported
promises were corrected; the broader design project remains paused.

It preserves the September 7 release's privacy-filtered funnel events, source metadata
on the existing Formspree application, a transparent scenario calculator and
the fact-checked valuation guide at its existing URL and H1. Both seller
checklists are published at `/blog/music-catalog-sale-documents-checklist/` and
`/blog/music-catalog-offer-checklist/`, with links from the guide and the
existing metadata and buyout-deal glossary pages respectively.
The standalone Apply navigation fix, questions and recipient are preserved.
Apply also tolerates blocked sessionStorage during initialization. Primary
review links navigate directly to the standalone form without an intermediate
SPA pageview. Legacy programmatic and marketplace redirects still work.
All 137 original sitemap URLs remain; the total is now 139. See `marketing/funnel/README.md` and
`marketing/application-route/README.md` for regression checks.

Historical September 10 preview: https://4fa0530e.spacemusic-a6n.pages.dev.
All 333 public files matched production then. Verified live on September 10: 24 pricing-routing checks,
existing llms.txt routing, all 139 sitemap URLs with applicable canonical and
robots checks, and all 33 Apply-navigation checks with zero browser errors.
Preview noindex was checked and production does not inherit it. No test leads
or synthetic analytics conversions were sent. Prior September 9 form-response,
calculator and five-width journey results are inherited, not rerun as part of
this server-rule-only release. Search Console canonical selection and ranking
effects have not been verified.

The September 10 release's historical predecessor is
`tmp/calculator-review-v2-20260909`, deployment
https://3654f780.spacemusic-a6n.pages.dev. This is NOT the immediate rollback
target for the current Typeform release; use the September 10 snapshot above.

See `marketing/calculator-review/README.md` for the inherited calculator release's guarded builder,
verification and change log. Calculator median mobile lab LCP was 6452.94 ms
before and 6452.73 ms after in three runs each: unchanged, not a performance fix.
The Search Console baseline and equal-period follow-up are in that release's
`PUBLISH-LOG.md`; business conversions remain separate from search traffic.

See `marketing/journey/README.md` for the prior journey tests. Its homepage lab median was
5891 ms versus 5884 ms before; Apply remains 1951 ms. No meaningful regression
was measured, but the homepage still needs a separate performance project.

Do not deploy `tmp/clarity-preview-*`: those are unfinished design drafts based
on the superseded release. Rebuild the design from this baseline or a newer
verified production snapshot, and rerun the application navigation regression
tests before publishing it.

The public marketing frontend source in the `web` gitlink is not populated.
Do not replace this complete static release with an unrelated frontend/backend
build. The guarded release scripts preserve content, routes and old assets.
