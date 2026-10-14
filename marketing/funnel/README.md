# Qualified application implementation, September 7, 2026

Design is paused. Start from the current `marketing/RELEASE.md` snapshot, never
the old clarity preview or the unpopulated `web` gitlink.

## Measurement contract

- calculator_used: first valid hypothetical result per browser tab session.
- apply_clicked: activation of a same-origin Apply link from a known public page.
- application_started: first intake edit or valid submit attempt per tab session.
- application_submitted: only after the existing receiver returns HTTP success.

No submitted event is emitted on validation, click, failure or an in-flight
duplicate. Failed requests can be retried. The form recipient and questions are
unchanged. Error display was repaired: previously the intake hid submit errors.
There is no server-side idempotency guarantee if a request is accepted but its
response is lost; deduplicate such retries during private review.

landing_path records the first known public route in sessionStorage.
apply_source_path records the known public route leading to Apply. Missing
attribution stays absent. Both are included as hidden Formspree metadata.
Only allowlisted paths are retained; no URL parameters or fragments. Analytics
properties are rebuilt from these two fields. Names, addresses, catalog data,
documents, tokens and amounts never enter the funnel event API. The tracker
also strips URL parameters and referrer paths, and drops events on non-public
or preview routes. This intentionally ends legacy automatic form/outbound/file
tracking on the public release; old dashboard records remain available.

Statistics are optional and fail open. Missing or throwing analytics does not
block the form. sessionStorage attribution uses an in-memory fallback when
storage is unavailable, which cannot persist across document navigations.
The standalone Apply initializer also catches blocked sessionStorage reads;
its previous direct reads could prevent the form from mounting. Seven mocked
receiver calls cover success, duplicate protection, errors, retries, absent or
throwing analytics and blocked browser storage. No receiver request escapes
these test interceptors.

## Plausible

On September 7 the authenticated spacemusic.io settings were inspected, and
all four event goals plus landing_path and apply_source_path properties were
created and confirmed in the settings tables. Existing goals were preserved.
No production test lead or synthetic conversion was sent. Mocked integration
tests and HTTP acceptance do not establish real dashboard counts or lead
quality. Validate these against genuine subsequent submissions in the existing
private receiver; dashboard verification remains pending real traffic.

Documentation: https://plausible.io/docs/custom-event-goals and
https://plausible.io/docs/script-extensions.

## Private qualification

The empty worksheet and instructions are in `private/lead-review/`, git-ignored
and never copied into public releases. Review contactability, transferable
rights and documented income manually. Pending reviews are reported separately.
No fixed revenue threshold has been added.

## Releases and rollback

| Stage | Local snapshot | Preview | Production | Verification |
| --- | --- | --- | --- | --- |
| Baseline | tmp/apply-navigation-20260907 | n/a | 6b4a9ca6 | 241 files matched live |
| 1: tracking and calculator | tmp/funnel-stage1-v2-20260907 | 67af4c32 | a3b1abea | 244 files matched; 137 URLs; form mock tests; 33 Apply preview checks; social and llms checks |
| 2: valuation guide | tmp/funnel-stage2-20260907 | 13b96d0a | 4f1b3a1a | Preview passed full static content, mobile, keyboard, metadata and source-link checks |
| 3: document checklist | tmp/funnel-stage3-20260907 | 8b1b7ff7 | 79e28ee0 | 252 files matched live; 138 URLs; content and guide links passed; 33 Apply preview checks |
| 4: offer checklist and Apply resilience | tmp/funnel-stage4-v2-20260907 | 58240802 | 7c1307d4 | 259 files matched live; 139 URLs; all 137 original URLs retained; 33 Apply checks passed both preview and live; content and seven mocked receiver calls passed |

Each hash is a deployment at https://HASH.spacemusic-a6n.pages.dev. The Pages
project is `spacemusic`; only branch `main` publishes production. Deploy the
preceding complete snapshot to main to roll back. Never delete old assets;
cached clients may still reference them.

Final production bytes were verified at 2026-09-07 17:23:44 CEST. Subsequent
live browser checks passed for the guide, both articles, correct Apply routing,
mobile layouts, keyboard links and server-delivered article content without
JavaScript. Robots, canonical and sitemap checks passed. Homepage social
metadata and llms.txt routing/content checks passed. The live predecessor was
byte-checked immediately before the final production deployment.

The final snapshot adds `apply/assets/index-BK3T0J9j.js`; Apply CSS is
byte-identical to the baseline, and every earlier asset is retained. Changes
remain in the local working tree; no unrelated Git changes were committed or
reverted. Production was published through the existing Cloudflare Pages
project, not by building the missing `web` submodule.

## Tests

- `node marketing/funnel/scenario.test.mjs`
- `node marketing/funnel/tracking.test.mjs`
- `node scripts/check-funnel.mjs RELEASE_OR_ORIGIN`
- `node scripts/check-funnel-tracker.mjs RELEASE`
- `node scripts/check-funnel-release.mjs tmp/apply-navigation-20260907 RELEASE COUNT`
- `node scripts/check-funnel-content.mjs ORIGIN 4`
- `node scripts/check-funnel-performance.mjs BEFORE/summary.json AFTER/summary.json`
- Existing Apply navigation, production SEO, homepage social, llms routing and byte verification scripts.

All application tests intercept Formspree and block analytics transmission.
No-JavaScript calculator HTML contains the explanation, formula and Apply
links, not a fabricated default value. The interactive calculation needs JS.

## Mobile lab comparison

Lighthouse 13.4.1, installed Chrome headless, default mobile simulation, local
static snapshots, three sequential runs per page. Analytics POSTs blocked.
Reports: `tmp/funnel-qa/before/` and `tmp/funnel-qa/stage1-after/`.

| Page | Baseline median LCP | Stage 1 median LCP |
| --- | --- | --- |
| Homepage | 5734 ms | 5883 ms |
| Calculator | 6784 ms | 6453 ms |
| Apply | 2116 ms | 1951 ms |

The guide's three-run baseline median was 8735 ms; stage 2 was 8404 ms.
Reports are in `tmp/funnel-qa/stage2-after/`. No threshold regression.

For the representative existing BeatBread article: baseline median 6904 ms,
stage 3 median 7055 ms (+2.2%, +151 ms). New document-checklist median: 6152 ms;
it has no pre-publication equivalent. Reports: `blog-before/` and `stage3-after/`.

Final stage 4 medians (`stage4-after/`, three runs per route):

| Page | Reference median LCP | Final median LCP | Difference |
| --- | --- | --- | --- |
| Existing BeatBread article | 6904 ms original baseline | 7207 ms | +4.4%, +303 ms |
| Valuation guide | 8735 ms original baseline | 8853 ms | +1.3%, +118 ms |
| Document checklist | 6152 ms stage 3 | 6303 ms | +2.5%, +151 ms |
| Offer checklist | New page | 6152 ms | No previous equivalent |

These four pages are byte-identical in stage4 and stage4-v2. The latter changes
only the Apply entry and adds its new versioned asset.

### Apply performance investigation

The first final Apply batch (`final-apply-after/`) measured 2401 ms median:
+285 ms / +13.5% against the original 2116 ms baseline. Publication was held
and the initial failing reports retained. The new Apply JS is only 24 bytes
larger than stage 3, with unchanged CSS and markup. Raw observed LCP was about
45-57 ms, compared with about 49-57 ms in the stage 1 samples. FCP, blocking time
and layout shift did not show the simulated LCP jump. The slower samples had
a later LCP frame and different timing for the asynchronous analytics script;
these observations alone do not establish a causal regression.

A fresh sequential comparison, with no concurrent browser tests, ran three
times for each untouched baseline, stage 3 and final candidate. Medians:

- Original baseline: 2118 ms (`apply-investigation-before/`).
- Stage 3: 1952 ms (`apply-investigation-stage3/`).
- Final candidate: 1952 ms (`apply-investigation-final/`), all three scores 98.

The initial failure did not reproduce. The final candidate was -7.8% / -166 ms
against the fresh baseline and essentially unchanged against stage 3. No
production code or test throttling was changed to obtain the repeat results.
The repeat comparisons pass the agreed combined 10% and 250 ms threshold.
Keep the initial reports as evidence of lab variability, not as discarded data.

## Follow-up

Two thread follow-ups are scheduled for October 6 and November 3 at 10:00
local time, after the first 28 and 56 complete calendar days of measurement.
Automation ID: `spacemusic-uppf-ljning-av-kvalificerade-ans-kningar`.
The task is read-only: it must not deploy, create synthetic conversions or
classify leads automatically. Missing access or manual review is reported
explicitly. Exact completed 28-day cohorts should start September 8 so the
partial release day is not mixed with a full-day baseline. Cohort 1 is
September 8-October 5; cohort 2 is October 6-November 2, inclusive.

Journey-release annotation: the clearer review journey and Apply confirmation
went live on September 8 at approximately 07:07 CEST, deployment `6c66c5dd`.
The first cohort therefore includes a few hours of the prior journey, not a
uniform 28-day UX variant. Keep the existing measurement dates and distinguish
this UX change from September 7's tracking implementation when interpreting
conversion changes. See `marketing/journey/README.md`.

The final comparisons pass after the Apply investigation above. Absolute lab results are
not real-user Core Web Vitals and do not establish a ranking or conversion
improvement. Marketing pages still have an existing client-render performance
cost; the redesign/runtime architecture is outside this scope.
