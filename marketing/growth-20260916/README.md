# All-genre conversion preview

Status: **preview only**, September 16, 2026. Production is unchanged.

Preview: https://70c85abf.spacemusic-a6n.pages.dev/

Updated Sell page: https://70c85abf.spacemusic-a6n.pages.dev/sell/

Branch alias: https://codex-growth-20260916.spacemusic-a6n.pages.dev/

Candidate: `tmp/growth-preview-v5-20260916` (383 public files plus two hosting control files).

Authoritative production baseline: `tmp/typeform-intake-release-v3-20260915`, deployment `6dea26c1`. Read `marketing/RELEASE.md` before any future promotion; stop and rebase if production has changed. Do not promote an older design preview or include unrelated dirty worktree changes.

## Changes and safety boundary

- Shared locally hosted Inter type system, stronger homepage hierarchy, clear individual-review CTA, all-genre positioning, readable mobile layout and native keyboard-accessible FAQ.
- V5 completes the Sell hub layout: homepage-matched hero and review panel, top-of-page Apply CTA, native jump navigation, three readable guide groups, four subgenre overviews and a high-contrast final CTA. All prior Sell text and anchor destinations are retained. Sell H1, metadata and schema are identical to v4; no other page body or metadata changes relative to v4. Individual genre destinations are not redesigned by this change.
- Home, About, Brand Facts and Sell have intentionally reviewed copy changes. About's unsupported exclusive-genre claim, competitor dismissal, market-growth statistic, minimum income and fixed genre multiples are corrected. The eight existing About genre examples remain, not an exhaustive eligibility list.
- Machine-readable company facts and `llms.txt` agree with the broader positioning. `llms.txt` stays plain text; no HTML title or viewport is inserted. Existing canonical response headers stay unchanged.
- Nine homepage genre cards now link to their existing specific canonical destinations, not nine copies of the same hub link. The hub remains linked.
- All nine homepage sections and prior link destinations remain. Other sitemap page bodies and metadata are unchanged; their head/import references and typography may change. Existing mood/genre copy has NOT been comprehensively fact-checked by this package. Legacy hype/market assertions visible in genre cards are a separate evidence-led follow-up, not verified here.
- All 139 sitemap URLs, titles, canonicals, robots, redirects and hosting rules are retained. Descriptions change only on About, Brand Facts and Sell; Home's H1 and supported company/FAQ schemas intentionally change. The preview host supplies noindex via HTTP, never through production document edits.
- The entire Apply directory is byte-identical. Typeform, fallback receiver, notification Worker, credentials, analytics events and backend are untouched. No customer or synthetic lead was submitted.
- No new paid product, report, mandatory question, income minimum, guaranteed offer or public customer example is introduced.

## Rebuild and verify

Always choose a fresh output directory. Do not overwrite a preserved baseline.

```sh
node scripts/build-growth-release.mjs tmp/typeform-intake-release-v3-20260915 tmp/growth-preview-next marketing/growth-20260916/build-manifest-next.json
node scripts/test-growth-release.mjs marketing/growth-20260916/build-manifest-next.json
node scripts/test-sell-layout.mjs marketing/growth-20260916/build-manifest-v4.json marketing/growth-20260916/build-manifest-next.json
node --test marketing/funnel/scenario.test.mjs marketing/funnel/tracking.test.mjs marketing/typeform-intake/intake.test.mjs
```

The builder asserts the exact baseline entry module, inventory and sitemap size; applies reviewed string replacements to compiled client modules; changes SSR in the same build; creates versioned dependency-graph assets and retains every previous baseline asset. A baseline drift hash manifest makes the input auditable. Home and Sell main HTML are trusted build-time constants shared by SSR and their React routes, not runtime DOM patching or user-supplied HTML.

## Verified September 16

| Check | Result |
| --- | --- |
| Release regression suite | 3,781 assertions passed on v5; fewer dependency edges because Sell now renders its shared build-time HTML |
| Sell layout delta | 589 checks passed against v4: every prior text/link retained, 38 guides, four subgenre overviews, same metadata, SSR/client parity, other page bodies unchanged |
| Calculator / privacy-safe tracking / intake tests | 13 test entries passed, including 47 calculator assertions and 11 intake cases |
| Independent code review | Earlier consent callback and Twitter alt fixes retained; separate v4-to-v5 review found no new issues, including actual SEOHead output and content-to-link associations |
| Module graph bundle validation | Reviewer validated 59 modules with no errors or warnings |
| Preview file comparison | All 383 public files match uploaded candidate |
| Production file comparison | All 338 public files still match original Typeform baseline |
| Preview route checks | 139 sitemap destinations return 200; 137 HTML pages have production canonicals and H1; preview HTTP noindex present |
| Plain-text routing | Existing llms/pricing canonical headers retained |
| Homepage visual review | Desktop and mobile screenshots inspected; Inter confirmed in rendered DOM |
| Responsive DOM review | Configured widths 320, 390, 768 and 1280; no main-content horizontal overflow (actual CSS widths exclude 15px scrollbar) |
| Mobile navigation | Cookie banner dismissed; menu opened; review CTA reached the existing standalone Typeform Apply landing |
| Keyboard | Enter expands the native FAQ; skip link focuses main |
| Client routing | Home to About to Calculator; guide back to Home; reviewed copy rendered correctly |
| Calculator in hosted preview | 1000 x 12 x 4 x 50% = $24,000.00 |
| Additional mobile pages | Brand Facts, Sell and valuation guide: Inter, one description, correct canonical, no document overflow |
| V5 Sell browser checks | Desktop/mobile screenshots reviewed; widths 320, 390, 768, 1280 have no document overflow; native group navigation works; Enter activates subgenre jump; skip link focuses main |
| V5 Sell route checks | Direct load and Home-to-Sell client navigation render the new layout; one description, production canonical and both schemas present; hero CTA reaches existing Typeform Apply landing |
| Browser error log | No page errors in final sampled route sequence; initial browser extension disconnect was recovered |

Checks used the approved computer-use interface for real browser interaction and local Node/JSDOM/VM tests for build artifacts. No shell-controlled browser session or production form submission was used. No claim is made that the full historical 33-test Apply browser suite was rerun.

Shared preview CSS: 18,746 bytes raw / 3,924 gzip (v4 was 9,966 / 2,748). Homepage module: 26,513 raw / 6,166 gzip. Sell module: 48,474 raw / 6,873 gzip; it no longer imports the genre data to render the directory. Inter Latin file: 48,432 bytes; one font preloaded, other scripts are unicode-ranged. These are asset sizes, **not LCP measurements**. No new runtime package or hero image was added.

## Still required before production

Owner approves the preview. Refresh the Search Console baseline and run three comparable mobile-performance measurements before/after, investigating a median LCP regression above both 10% and 250 ms. Neither those performance runs nor current goal reports/qualified-lead counts were verified here. Preserved metadata and passing tests reduce technical risk; they do not guarantee unchanged rankings or increased conversions.

After explicit production approval and the remaining gates, deploy only this verified complete candidate to the existing Pages project/production branch, preserve `6dea26c1` and its snapshot for rollback, then rerun file, route, indexability and Apply smoke checks. Update `marketing/RELEASE.md` only after successful promotion. The current production document was intentionally not changed by this task.

## Editorial deliverables

- `GROWTH-PLAN.md`: evidence, limitations, acquisition priorities and a 2,800-click/28-day target, not a promised outcome.
- `CONTENT-DRAFTS.md`: three differentiated label/collaboration/back-catalog preparation drafts with sources and publication gates. They are not part of the deployed preview or sitemap.
- `copy.mjs`: exact factual/copy edits applied to existing public pages.
- `growth.css`: shared typography and homepage layout source.
- `sell-layout.mjs`, `sell.css`: content-preserving Sell layout and scoped styles.
- `build-manifest-v5.json`: current candidate input hashes and versioned-module mapping. Earlier v1-v4 manifests are preserved iteration records, not release targets. The user's earlier link `6264626b` remains immutable and still shows v4; use the new preview URL above.
