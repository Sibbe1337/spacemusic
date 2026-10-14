# Homepage Loading Performance

## Production Release

Published on 2026-09-07 to Cloudflare Pages project `spacemusic`, branch
`main`: https://bf29e6f0.spacemusic-a6n.pages.dev

Baseline created by this performance release: `tmp/home-fonts-preload-20260907`.
It contains 241 files: 239 public assets plus `_headers` and `_redirects`.
Both hosting control files must be retained in future releases.

The subsequent application-navigation hotfix is now the current production
baseline: `tmp/apply-navigation-20260907`. It preserves this performance work.
Use `marketing/RELEASE.md` to select the latest baseline for future changes.

The source was `tmp/homepage-social-metadata-20260907`, verified against
every public production response immediately before deployment. Rollback
baseline: that same directory and https://d32bc49f.spacemusic-a6n.pages.dev.

Only the existing homepage `index.html` changed. All 230 other existing
files, including other HTML pages, runtime modules, old CSS, image assets,
sitemap, robots, AI resources and hosting rules, remain byte-identical.
Ten new files contain seven unchanged WOFF2 subsets, two font licenses and
a fingerprinted stylesheet. The homepage body, titles, descriptions,
canonical, structured data and social metadata remain unchanged.

## Diagnosis and Decision

The supplied September 3 report claimed one blocking script, one stylesheet
and a 4,311 ms mobile LCP. Fresh Lighthouse 13.4.1 mobile measurements instead
found three blocking stylesheets: the application CSS and its two Google
Fonts `@import` requests. The existing analytics script was already async;
the application entry was already an implicitly deferred module script.
No generic analytics deferral or duplicate defer attribute was added.

Three fresh production baseline runs consistently scored 81/100, with LCP
between 3,666 and 3,685 ms. The headline was the LCP element. FCP was nearly
as late as LCP, and the font stylesheets were discovered behind the main CSS.

The first candidate served the exact same fonts locally and preloaded the
two used Latin subsets. Its single preview run scored 89 with FCP 2,431 ms
and LCP 3,383 ms. The remaining startup waterfall included a lazy homepage
module discovered only after the application entry and shared code loaded.

The selected candidate also includes a native `modulepreload` hint for the
existing homepage module, without changing or eagerly executing its code.
Its three preview runs scored 99/100 with LCP 2,094 / 2,056 / 2,176 ms and
zero CLS or TBT. The homepage's full layout stylesheet remains blocking:
no fragile critical-CSS extraction, stylesheet onload handler, CSS removal,
or JavaScript-dependent styling fallback was introduced.

Fonts retain the provider's variable settings, Unicode ranges and swap
behavior. Only two actually used subsets are preloaded. The other subsets
are available on demand, and no third-party font requests occur on a fresh
homepage load. Other routes keep their existing direct-load CSS for this
incremental rollout.

## Verification

- All 239 public production files match the selected release byte-for-byte.
- All 137 production sitemap URLs pass canonical and robots checks.
- Local and hosted-preview comparisons at 390px and 1440px, with and without
  JavaScript, preserve content, all metadata/schema, loaded font settings,
  layout geometry and full-page appearance. Final pre-release runs had zero
  changed screenshot pixels in all four configurations.
- The visual test permits at most 0.001% browser rasterization noise, while
  requiring exact content, metadata, loaded fonts and geometry. An earlier
  desktop comparison differed by just 22 pixels out of approximately 9.7M;
  subsequent comparisons were pixel-identical.
- All nine font/license assets are checked against provenance hashes; only
  the two used Latin fonts are requested, once each.
- Existing social metadata, article-to-home navigation, browser back/forward,
  mobile, and llms.txt header/redirect tests pass on the selected preview.
- Four negative builder tests reject source overwrite, nested output,
  existing output and unexpected arguments without modifying either release.
- Desktop Lighthouse scored 99 on the original production page and 100 on
  the selected preview, with LCP 888 ms and 585 ms respectively (one run each).

All production performance rechecks completed on 2026-09-07. These compare
the same production hostname, not the faster preview hostname:

| Metric | Production before | Production after |
| --- | --- | --- |
| Mobile Performance, three runs | 81 / 81 / 81 | 93 / 91 / 93 |
| Mobile LCP, ms | 3666 / 3669 / 3685 | 2914 / 2919 / 2909 |
| Mobile FCP, ms | 3650 / 3653 / 3670 | 1999 / 2454 / 1994 |
| Mobile CLS | 0 / 0 / 0 | 0 / 0 / 0 |
| Mobile TBT, ms | 0 / 0 / 0 | 0 / 0 / 0 |
| Desktop Performance, one run | 99 | 100 |
| Desktop LCP, ms, one run | 888 | 684 |

Median mobile Performance improved from 81 to 93, LCP from 3669.422 to
2913.805 ms (about 21%), and FCP from 3652.922 to 1998.805 ms (about 45%).
The production mobile LCP is still above the 2500 ms good threshold. Do not
report the preview's 99 or 2094 ms as production performance.

The final production audit retains one blocking layout stylesheet, with an
estimated 150 ms opportunity, and reports roughly 78 KiB of unused shared
JavaScript. Those estimates are not guaranteed savings. Removing essential
CSS or editing the shared compiled vendor bundle was not justified for this
narrow, SEO-preserving release.

Live regression tests also pass: full social metadata lifecycle, llms.txt
GET/HEAD/query/host/slash handling, nine font/license hashes, and no external
font requests on the homepage. Comparison against the immutable prior
release is pixel-identical in three configurations, with 22 rasterization
pixels differing out of approximately 9.7M on desktop with JavaScript.
All text, metadata, font settings and layout geometry match exactly.

Raw production reports:
`tmp/home-performance-after-{1,2,3}-20260907.json` and
`tmp/home-performance-desktop-after-20260907.json`.

## Method and Limits

Tests use Lighthouse 13.4.1 with fresh headless Chrome launches. Mobile uses
the default simulated mobile preset: 150 ms RTT, 1,638.4 Kbps throughput,
4x CPU slowdown and a 412x823 screen. Desktop uses `--preset=desktop`.
Only Plausible event submission is blocked (`*plausible.io/api/event*`), to
avoid adding audit visits to analytics; its script is still loaded.
Screenshots use separate clean browser contexts.

These are lab measurements, not CrUX or real-user field data. The user's
historical 4,311 ms / 81 / 98 figures were not reused as a measured baseline.
Preview and production hostnames can have different timing. Do not promise
the same score for every device, connection or test, or claim ranking,
conversion or AI-citation gains from these results alone.

Reports remain in `tmp/home-performance-*-20260907.json` and
`tmp/home-desktop-*-20260907.json`. Visuals are in
`tmp/home-font-checks-20260907/`. The first font-only candidate
`tmp/home-fonts-20260907` and its preview https://250f2896.spacemusic-a6n.pages.dev
were not deployed to production. The selected preview was
https://83f813c2.spacemusic-a6n.pages.dev.

## Reproduce

```sh
node scripts/build-home-font-release.mjs VERIFIED_SOURCE FRESH_OUTPUT
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node scripts/check-home-fonts.mjs BASELINE_ORIGIN CANDIDATE_ORIGIN
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node scripts/check-homepage-social.mjs CANDIDATE_ORIGIN
node scripts/verify-release-files.mjs FRESH_OUTPUT CANDIDATE_ORIGIN
node scripts/check-llms-routing.mjs CANDIDATE_ORIGIN
node scripts/check-production-seo.mjs
npx --yes lighthouse@13.4.1 URL --only-categories=performance --chrome-flags='--headless=new' --output=json --output-path=REPORT.json --blocked-url-patterns='*plausible.io/api/event*' --quiet
```

The builder is a guarded transformation of the prior snapshot with Google
Fonts imports, not a generic rebuild of the root/backend project. It refuses
unexpected source CSS, hosting configuration, overlapping output, existing
output and unverified font bytes. Start future website updates from the
current release instead of rerunning it on already-transformed HTML.

References checked 2026-09-07:

- https://web.dev/articles/optimize-lcp
- https://web.dev/articles/font-best-practices
- https://developer.chrome.com/docs/performance/insights/render-blocking
- https://raw.githubusercontent.com/google/fonts/main/ofl/fraunces/OFL.txt
- https://raw.githubusercontent.com/google/fonts/main/ofl/plusjakartasans/OFL.txt
