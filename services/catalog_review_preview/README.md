# SPACE catalog review: phase 1

Implemented September 17-18, 2026, following the approved
`docs/toolost-launch-plan-20260917.md`. This is the design approval gate, not
a production portal or a completed Too Lost integration.

Owner design approval was received September 18, 2026. Work now continues in the
separate `services/catalog_review/` backend foundation. This preview remains
synthetic and unchanged; approval did not activate an API or production release.

## Open

```sh
node services/catalog_review_preview/server.mjs
```

Open http://127.0.0.1:4197/. An alternative unprivileged port can be supplied
as the first argument. The server binds only to 127.0.0.1, verifies the Host
header and serves an explicit list of assets. Do not expose it through a tunnel
or deploy it as a customer workspace.

Use **Open demo review** to start. The first path demonstrates a simulated
read-only provider connection; the second uses sample document references.
Under **Preview scenarios**, choose a scenario and restart to test wrong
account, declined permission, session expiry, empty catalog, interrupted import,
missing evidence, failed save, failed submission or unknown currency.

## What works

- Full interactive journey: invitation, source, permission disclosure, explicitly
  simulated authorization, account confirmation, import stages, coverage,
  release selection, rights, documents, versioned demo submission, follow-up,
  connection and deletion-request settings.
- Existing Inter font and approved SPACE wordmark are served read-only from
  their existing repository locations. No stock imagery or new visual identity.
- Guarded state transitions and an immutable submission snapshot. Editing is
  unavailable after submission. Follow-up answers do not rewrite version 1.
- Sample amounts use fixed-precision arithmetic; negatives are retained;
  unknown currency or no reported history never becomes a confirmed zero.
  Account totals are not presented as selected-release income or valuations.
- Partial import resumes from a fixture checkpoint. A different source resets
  the old source's selection and rights answers. Stale callbacks are ignored.
- Synthetic choices and unfinished rights answers resume in the same browser
  tab using guarded event replay. Blocked storage has a memory-only fallback
  with an honest notice. This is not server persistence or authentication.
- Failed saves and submissions keep input. Duplicate submission does not create
  another snapshot. Missing ownership and missing evidence remain explicit.
- No real file picker: only named fixture references. No actual files are
  attached, scanned or downloaded. No fabricated verified-document badge.
- Visible labels, focus on errors/step headings, keyboard controls, reduced
  motion, a skip link and responsive single-column mobile layouts.

## Isolation

This directory does not import the legacy seller, valuation or payout backend.
It does not change the existing local portal or any marketing release file.
The browser CSP forbids all network connections and form submissions; only
same-origin preview scripts/fonts/styles/images are allowed. The HTTP server
rejects mutations, arbitrary file paths, query-bearing URLs and API routes.
No analytics, email transport, secrets, API clients, OAuth tokens, billing,
customer identifiers, database, production DNS or hosting configuration exists
in this preview. Sample `example.com` identities are fictional.

All responses carry no-store and noindex narrowly on this local server.
These settings are not applied to the public website. Authentication, tenant
isolation, encrypted storage, real OAuth, private uploads, queues, reviewer MFA
and data deletion must still be built and verified in later phases.

## Tests

```sh
node --test services/catalog_review_preview/*.test.mjs
node --test marketing/funnel/scenario.test.mjs marketing/funnel/tracking.test.mjs marketing/typeform-intake/intake.test.mjs
```

Node built-ins power the model and loopback-server tests. DOM tests use the
already-installed `jsdom` from `services/seller_ui`; no new dependency or runtime
was installed. The DOM suite runs the actual UI event handlers with explicitly
linked local modules, disabled external resources and accelerated local timers.
It is not a substitute for browser or production integration tests.

See `QA.md` for observed results and limitations. Neither fixture tests nor
the UI's simulated permissions establish sandbox access or commercial approval.

## Handoff

Phase 0 decision material: `READINESS.md` and `TOO-LOST-QUESTIONS.md`.
Design preview: this directory. The next gate is owner review of the screens,
then approval of the isolated hosting/data-handling choices before phase 2.

No production deploy, new paid plan, live customer migration or external email
is authorized or performed by completing this preview. Preserve the existing
Apply/Typeform/short-form and notifier while the private system is developed.

Rollback for this phase means stopping the loopback preview process. The live
site has no dependency on it; no marketing rollback is necessary.
