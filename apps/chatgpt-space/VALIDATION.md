# Validation / 2026-10-03

## Completed

- `npm test`: 34 tests passed, none skipped. Includes a real SDK client over
  HTTP, initialization, tool/resource discovery, all seven tool/case responses,
  strict inputs, output schemas, source resolution and readonly boundaries.
- Async UI-state tests: delayed responses, newer host results, failed requests,
  unchanged retry arguments, invalid results and cancellation.
- HTTP checks: Host/Origin rejection, request size, malformed JSON, unsupported
  media types, noindex, explicit file allowlist and inline bundle syntax.
- `npm audit --omit=dev`: no known vulnerabilities reported at test time.
- Independent read-only code review found a shutdown bug with persistent MCP
  event streams. Fixed by closing active connections on shutdown; a regression
  test keeps a real SDK client and an explicit SSE stream active during shutdown.
  The reviewer rechecked the fix and independently confirmed clean SIGINT and
  SIGTERM exits with an active SDK stream; no remaining findings in that review.
- Browser verification in the Codex in-app browser used the official AppBridge
  connected to the real local MCP server, not fabricated UI data. Checked overview,
  evidence and buyer views for all three cases, back navigation, missing income,
  currency mismatch and a potential-but-unverified fictional fit.
- Mobile at a 390-pixel viewport: measured widget width and scroll width both
  357 pixels, no horizontal overflow. Primary controls at least 44 pixels tall.
- Keyboard: activated a catalog with Enter, navigated to buyer criteria using
  Tab/Enter; resulting view receives heading focus.
- Light/dark host theme changes reached the widget. Normal viewport restored
  after testing. No remote font, image, analytics or data endpoint is required.

## Not Claimed

- No actual ChatGPT account connection, model tool-selection evaluation, HTTPS
  tunnel, public deployment, directory submission or production readiness test.
- No real customer data, authenticated portal integration, Jev inference,
  royalty ingestion, verified rights, valuation, buyer contact or email sending.
- No screen-reader audio session, external accessibility certification, or
  full browser/device matrix. Browser accessibility-tree and keyboard checks
  are not a substitute for those tests.
- Transport and state-controller failure tests are automated; full browser
  offline/network-interruption simulation has not been performed.

## Unrelated Repository Guard

`npm run project:check` currently exits non-zero: the recorded production
snapshot `tmp/growth-preview-v1-20260930` has 144 sitemap URLs, while recorded
rollback/candidate snapshots have 141. `marketing/RELEASE.md` documents the
September 30 addition of three URLs. The generic equality guard has not been
changed or bypassed here. This app does not edit or deploy any website snapshot,
content, canonical, Apply page or sitemap.

Only the new `apps/chatgpt-space/` package, two root convenience scripts and
the project-map entry were added for this task. Existing unrelated work was
preserved. There is no claim that the whole repository's unrelated checks pass.
A preview screenshot is saved separately at `output/chatgpt-space/preview.jpg`.
