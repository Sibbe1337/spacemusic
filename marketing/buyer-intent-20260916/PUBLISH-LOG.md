# Approved production promotion

Date: September 16, 2026, approximately 09:18 UTC.
Owner approval: "Godkant. Fortsatt sen."
Production: https://spacemusic.io/
Immutable deployment: https://02276b90.spacemusic-a6n.pages.dev
Approved preview: https://9b4782a6.spacemusic-a6n.pages.dev
Artifact: `tmp/buyer-intent-v2-20260916` (not v1 or an older design preview).
Manifest: `manifest-v2.json`; includes the complete previously approved design.

## Verification

- Before release, all 338 old production public files matched `tmp/typeform-intake-release-v3-20260915`.
- After release, all 446 public files match the approved artifact byte for byte.
- All 140 sitemap URLs return 200 with applicable self-canonical, H1 and no production noindex. All 139 previous URLs remain.
- Live rendered homepage, Sell, Apply, label funding article and three refreshed buyer-intent pages inspected; each has the expected H1 and production canonical.
- 4,633 preservation checks; 13 scenario, tracking and intake tests, including simulated error/retry/double-submit/blocked-analytics cases. No test applications submitted.
- 26 visible Apply links clicked across homepage (6), Sell (4), process (3), calculator (4), Primary Wave comparison (3), selling guide (3), beatBread article (3). All reached standalone guided Apply with the expected H1 and no preloaded iframe.
- In-app back/forward, slash/no-slash/direct query-and-fragment navigation, and 390px keyboard-opened mobile menu to Apply work. Temporary viewport reset.
- Chrome history automation stalled twice; checks resumed in the in-app browser. No failed site behavior was inferred from the automation interruption. Do not describe this updated coverage as the obsolete historical 33-case browser script.
- 24 pricing-routing checks and llms MIME/canonical/redirect/user-agent checks pass. Initially the old scripts compared against pre-article sitemap/pre-directory text fixtures and failed. Added optional explicit release-fixture arguments without removing assertions; reruns passed against this approved artifact.
- Three-run mobile lab comparison passes the agreed LCP regression gate; complete reports and Search Console baselines are in `RELEASE-BASELINE.md`.

## Rollback

Retain complete `tmp/typeform-intake-release-v3-20260915`, including `_headers`
and `_redirects`. Its immutable deployment is
https://6dea26c1.spacemusic-a6n.pages.dev. Redeploy the full directory to project
`spacemusic`, branch `main`; then recheck all 139 prior sitemap URLs and Apply.
Do not roll back or erase Typeform responses or the notification Worker.

## Still unverified

Actual Google reindexing/ranking changes, business conversion reconciliation,
manual lead qualification, and AI-engine citation changes are not verified by
deployment checks. Existing homepage contrast warning remains a separate issue.
The selling-guide accuracy refresh is a subsequent draft, not part of this
approved release. No unrelated repository changes were committed or deployed.
