# Seller journey: isolated interactive preview

Status: local UX prototype, not approved for production. Built 2026-09-10.

## Run and review

From the repository root:

```sh
node marketing/seller-journey-preview/serve.mjs
```

Open http://127.0.0.1:4193/. The server binds to loopback only, not the local network. Do not deploy this directory as the existing marketing release or enable real customer input.

1. Select **Fill with fictional demo details**, then **Start demo review**.
2. Continue to catalog details. **Use sample catalog** supplies invented numbers.
3. Add both sample documents. No real file picker or upload exists.
4. Review the package, then **Submit demo package**.
5. Open **Preview controls** to simulate a reviewer asking for clarification. Reply with fictional text.
6. **Save & exit**, refresh, and **Continue saved demo** demonstrate local resumption. No email is sent and no identity is verified.

The document and review screens also have preview controls for simulated failures and retries. Restart asks before clearing only this prototype's localStorage key.

## What this demonstrates

- A short first application, with distributor and artist identity kept separate.
- Catalog scope, owned share versus share offered, and an explicit exclusion of future recordings.
- Reported income versus verified income, recording rights versus publishing rights, and unresolved agreements remaining open review questions.
- A single place for evidence, review status and a seller response.
- Local persistence, validation, error recovery, keyboard focus and mobile reflow.

No sale recommendation, valuation multiple, automatic offer, signature or payment is produced. The cutoff is proposed, not an agreed contract boundary. Adding sample evidence never marks it verified.

## Isolation and limitations

There are no Formspree, analytics, email, payment or seller API calls. CSP blocks connections and form actions. Only an explicit allowlist of local assets is served. POST is rejected. The HTML and HTTP responses declare noindex; this is not an access-control mechanism.

Only fictional fixture identifiers and typed demo text are stored in localStorage under `space.seller-journey.preview.v1`. This storage is unencrypted, local to this browser/origin, and not suitable for customer records. Do not enter real personal or catalog data. The application keeps running when storage is blocked, but cannot guarantee persistence. There is no multi-user isolation, cross-device resume, file parsing, malware scanning, actual message delivery or reviewer account. The DistroKid help link is an ordinary optional external navigation.

Inter is served from the existing `marketing/catalog-readiness-draft/preview/fonts/inter.woff2`, with its adjacent `OFL.txt` license. No font is downloaded at runtime. The custom server does not expose repository files, README or QA artifacts.

## Verification

```sh
node --test marketing/seller-journey-preview/model.test.mjs
node marketing/seller-journey-preview/check-browser.mjs
```

Browser QA uses the already available Playwright runtime from `scripts/funnel-support.mjs`, installed Chrome, and `tmp/catalog-readiness-tools/node_modules/axe-core/axe.min.js`. No new application dependencies were added.

- 13 model tests: validation, bounds, zero income, partial statement periods, fixture metadata, duplicate prevention, state transitions, clarification and corrupted storage.
- Full browser journey including failed upload/retry/removal, failed submission/retry/double event, local reload/resume, escaped reply text and isolated reset.
- Eight screens at 320, 390, 768, 1024 and 1440 CSS pixels; axe audits at 390 and 1440; screenshots in `qa/`.
- Keyboard focus, 200% CSS layout zoom, reduced motion, blocked and late-failing storage, JavaScript-disabled explanation, no browser-originated remote requests or submissions, and HTTP allowlist/method checks.
- Automated axe checks found no violations in the tested states. Contrast checks on gradient-backed text remain flagged for manual review by axe. Desktop and mobile screenshots were visually inspected; this is not a complete WCAG certification. Real-device Safari and assistive-technology testing are still needed before production.

The browser script writes its current timestamp and results to `qa/browser-results.json` only on success. Do not treat an old result as a new test run.

Production preservation: read-only byte comparison on 2026-09-10 of `https://spacemusic.io` against `tmp/pricing-routing-release-20260910` matched all 333 public files, including the sitemap. `_headers` and `_redirects` are not served by hosting and were not part of that HTTP byte check. Neither those files nor `marketing/RELEASE.md` were edited. No deployment was made for this preview.

## Proposed implementation after separate approval

1. Confirm this flow and the exact required versus optional catalog fields. Preserve the existing public Apply route, low-friction intake, recipient, SEO content and fallback. Review unknown ownership/currency cases instead of forcing invented answers.
2. Choose the system of record and authentication. The existing local seller-service prototype is a starting point, not a production-ready customer portal; see `docs/seller-platform.md`. Production needs verified single-use, expiring sign-in links, server-side authorization on every review/document, revocation, reviewer access controls and access logs. Do not keep access tokens or financial information in public URLs or analytics.
3. Connect existing Formspree intake without replacing a working flow prematurely. Confirm the account's plan and capabilities first. Record an acknowledged application once with stable references and idempotent retry/reconciliation; a browser click or an email notification is not proof of receipt. Never put provider/admin secrets in the browser.
4. Add private document storage with authenticated access, narrow download permissions, size/type validation, malware scanning, retention/deletion rules and recoverable backups. Do not rely on public links or noindex for privacy. Keep human review separate from upload success.
5. Add reviewer requests and seller responses against the same record, with an audit trail. Send notification-only emails through an authenticated sender; require sign-in to read private evidence. A verified sender/domain and delivery configuration are still needed.
6. Test authorization between different sellers, token expiry/reuse, file access, failures, duplicate/retried intake, accessibility and mobile devices with synthetic data. Compare the release manifest, existing Apply checks, public metadata, canonicals and sitemap before a limited approved rollout. Preserve rollback and the working intake until live verification passes.

Formspree can remain the intake/notification layer, but this preview does not prove that the current subscription includes uploads or webhooks. It is not a replacement for a persistent, access-controlled review workspace.

## Reference points

- [Formspree file upload documentation](https://help.formspree.io/articles/building-your-form/file-uploads/)
- [Formspree webhook documentation](https://help.formspree.io/articles/plugins/webhooks)
- [DistroKid earnings export instructions](https://support.distrokid.com/hc/en-us/articles/360013648253-Saving-Your-Earnings-Information-as-a-Spreadsheet-File)
- Existing local architecture: `docs/seller-platform.md` and `services/seller_ui/`.
- Production baseline: `marketing/RELEASE.md` and `tmp/pricing-routing-release-20260910/`.

These are implementation references, not evidence that a customer has submitted, been verified, or received an offer in this prototype.
