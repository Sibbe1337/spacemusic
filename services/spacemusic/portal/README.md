# Seller portal integration foundation

Status, 2026-09-11: working local integration with an opt-in owner-only Resend mail test, not a production deployment. The owner approved the seller-journey design and local email test. This implementation connects a separate UI to persisted test records, sessions and private local documents. It does not change the live Apply form or activate the legacy valuation/payout API.

## Start

```sh
python3 -m services.spacemusic.portal.app --local
```

Open http://127.0.0.1:4194/. The previous purely simulated design remains on port 4193 when its server is running.

Default private directory: `~/Library/Application Support/SpaceMusic/seller-portal-local/`. It contains a local secret, SQLite records and generated-ID document files. It is outside the repository and HTTP asset allowlist. A custom `--directory` inside the repository is rejected before any files are created. Only loopback hosting and `mode=local` are supported; changing the mode to production fails startup.

Test steps:

1. Open **Local test controls** and create the fictional application. This is a fixture import, not a real Formspree submission.
2. Create a local sign-in link for `alex@example.com`, then open the local test mailbox.
3. Open the single-use link and explicitly confirm sign-in. A page visit alone does not consume it.
4. Use the sample catalog, save it, and upload the two bundled samples.
5. Review and submit the package. The submitted version becomes read-only.
6. Use the local reviewer control to request clarification. Reply and refresh to verify server persistence.
7. Sign out. All existing sessions for that identity are revoked. A new link is needed to return.

Never use real leads, royalty statements, contracts or personal data in this environment. Only example.com application identities are accepted. The separately enabled email test sends a synthetic review sign-in link only to the owner's fixed hello@spacemusic.io inbox. The local mailbox and reviewer controls are deliberately privileged test conveniences, not production authentication or reviewer administration. There is no remote preview URL.

## Owner-only Resend mail test

The normal sign-in form remains simulated. Real mail is a separate, explicitly labeled development control and is disabled by default. To enable it locally:

```sh
python3 -m services.spacemusic.portal.mail
python3 -m services.spacemusic.portal.app --local --resend-key-file "$HOME/Library/Application Support/SpaceMusic/seller-portal-local/resend-test-key"
```

The setup command accepts the credential through a hidden prompt, not a command-line argument. It creates an owner-only (0600) file outside the repository in a private (0700) directory and refuses to overwrite an existing key. The local test file is not a managed production secret store. Do not paste credentials into chat, source files, Git, screenshots or logs. Use a Sending access key scoped to spacemusic.io; provider permissions are configured in Resend, not proven by the local file check.

The optional sender uses httpx, already present in the development runtime; it is lazy-loaded so default local startup has no additional mail dependency. The fixed HTTPS endpoint is api.resend.com/emails, with normal certificate verification, no redirects, no environment proxy inheritance, bounded response size and request timeout. Keep domain-level open/click tracking disabled in Resend. The code contains no tracking pixel and does not add analytics, but it cannot override or inspect provider-level tracking with a send-only key.

Open Local test controls, create the fictional application, then choose **Send test email to hello@spacemusic.io**. The sender, reply-to and recipient are fixed; request data cannot supply an arbitrary address, body, attachment or link. Only the fictional alex@example.com review is accessible through the emailed link. The link contains a bearer token, works once, and expires 15 minutes after the first attempt. It must be opened on the computer running this loopback server. This test cannot prove a customer's identity or remote/cross-device operation.

Five attempts per ten-minute window and twenty per day are enforced in SQLite across restarts. A persisted request ID, origin and hashed link let retries reconstruct exactly the same message and Resend idempotency key without storing plaintext link tokens. Successful provider receipts also persist. Reloading resumes the last test rather than automatically creating another request; a separate **Prepare another email test** action is needed for a new email. No bearer token or API key is returned by the email-test endpoints or local test mailbox. Tokens can still be accessed by the deliberately privileged fixture tools/server operator; this remains local-only.

The UI reports **accepted by provider**, not delivered. Verify actual receipt, SPF/DKIM, absence of rewritten/tracked links and successful one-time sign-in in the owner's mailbox. There is no production outbox worker, delivery webhook, bounce reconciliation or customer notification. Provider errors and uncertain timeouts retain the same request for manual retry; expired/consumed links require a new test. The additional owner_email_tests table is local only.

September 11 verification: 51 API tests passed (24 owner-mail tests plus 27 existing portal/seller tests). Browser checks passed on eight screens at 320, 390, 768 and 1440 pixels, including simulated provider timeout, double click, reload/resume and explicit new-test behavior. Sixteen axe checks found no violations; gradient contrast still needs manual assessment. The three independent review findings were fixed and rechecked with no further actionable findings. Black/Ruff passed, and a credential scan found no key in the eight source/test/documentation files checked.

One owner test request was made against the enabled local server and accepted by Resend on September 11: provider ID `54473419-556c-4380-9e58-a64ff32168cd`, recipient `hello@spacemusic.io`, subject `[TEST] Your SPACE portal sign-in link`. This proves API acceptance only, not inbox arrival, authentication results or clicking the real emailed link. The user's existing Gmail test passed SPF/DKIM earlier, but that is a different sending path and is not evidence for Resend delivery. No customer email or Formspree application was sent.

The live site was checked read-only again: all 333 public files matched the release snapshot, and all 33 Apply navigation checks passed with zero form submissions. No production release, DNS change, Git commit or push was performed for this integration.

Provider references: [send email](https://resend.com/docs/api-reference/emails/send-email), [idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys), [tracking settings](https://resend.com/docs/dashboard/domains/tracking).

### Cross-site mail-link correction, September 11

The first real mail-link opening exposed an over-broad Fetch Metadata check: even a top-level GET from Gmail received `403 Cross-site request denied`. The boundary now permits only `GET /` with `Sec-Fetch-Mode: navigate` and `Sec-Fetch-Dest: document`. This serves the inert sign-in shell; opening it does not consume a token or create a session. Cross-site API requests, downloads, embedded frames, fetches, static assets and mutations remain denied. Exact-host, origin, CSRF, custom request-header and CSP checks are unchanged.

Regression verification: the new entry-navigation test failed with 403 before the fix; all 66 API tests passed afterward, including 14 denied-request variants. The full browser suite also passed. Its mail-link test uses a second real loopback site (`localhost` to `127.0.0.1`) without request interception, asserts Chrome's actual cross-site/navigation/document headers, verifies an external API link is denied, and completes explicit single-use confirmation. Request interception in this Chrome runtime omitted Fetch Metadata, so a mocked page alone did not reproduce the browser boundary correctly. No external mail account is used by this test.

The existing owner server on port 4194 was restarted with the correction. No additional real email was sent and the owner's emailed token was not consumed by these tests. A successful Gmail click after the correction still needs owner confirmation. The production website and SEO configuration were not changed.

Browser-header references: [Sec-Fetch-Mode](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Mode), [Sec-Fetch-Dest](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest).

## Implemented and tested

- Formspree-shaped raw-body webhook verification using a separate secret, a five-minute timestamp tolerance, expected form ID and constant-time signature comparison. Canonically ordered payloads deduplicate independently of signature timestamps. Different submissions from the same email may still create separate reviews.
- Strict contact-field mapping. The original form and recipient stay untouched. Local source metadata accepts only `/`, `/calculator/`, `/apply/`, `/sell/` and `/guides/music-catalog-valuation-2026/`; unknown paths, full URLs and query strings become blank. This is a conservative local-test allowlist, not the full marketing sitemap.
- Random 256-bit, hashed, single-use sign-in tokens, expiring after 15 minutes. Consuming a link retires the other outstanding links for that identity. Resending alone does not invalidate an already delivered link. Request responses do not reveal whether an application exists. Email and client-address request limits are stored transactionally.
- Opaque HttpOnly, SameSite=Strict cookies. A session has a 30-minute idle timeout and a 12-hour absolute lifetime. On HTTPS the cookie is Secure; the explicitly local HTTP server cannot provide transport encryption. Tokens and catalog data are not stored in localStorage/sessionStorage. Sign-in fragments are removed from browser history before consumption and are never sent as URL query parameters.
- Per-review email ownership checks on reads, writes, uploads, downloads and replies. Writes additionally require an exact origin, custom request header and session-bound CSRF token. Untrusted forwarded-client headers are ignored.
- Explicit catalog saves with optimistic revision checks. A stale tab cannot overwrite a newer version. Unknown rights, income basis and agreements stay review questions; no evidence is automatically commercially verified.
- Bounded streamed request bodies, safe generated document IDs, private local files, checksum/integrity checks at submission and download, and attachment-only responses. Missing, corrupt or symlinked evidence prevents submission. Duplicate document categories are rejected; a seller must explicitly remove an item before replacing it.
- Only byte-exact bundled fixtures receive `TEST_FIXTURE` status. Every other allowed upload is quarantined. Quarantined files cannot be downloaded or submitted. This is **not antivirus**, file-format parsing or production content scanning.
- Submission retries do not duplicate the submission event. Reviewer questions and seller replies persist under the same review. No offer, rights transfer, signature or payment endpoint is exposed by this service.
- Server-wide no-store, noindex, no-referrer and nosniff headers; same-origin CSP and an explicit static asset allowlist. No analytics, external script, automatic email delivery or outbound Formspree call. Only the separately enabled owner test makes an outbound email request.

The development test mailbox holds plaintext test links in process memory to demonstrate delivery. It disappears on restart. Only their digests enter the SQLite link table. This is explicitly a test sink, not a durable production mail-outbox implementation.

## Formspree boundary

The proposed production boundary is additive:

`existing Apply -> existing Formspree receiver -> authenticated webhook -> review record -> verified email access -> private workspace`

The public form must not create a second application by posting directly to this portal as well. Keep the working receipt and original recipient as fallback. Do not count the new test fixtures as leads or send them to Plausible.

The webhook parser follows Formspree's documented `Formspree-Signature: t=<unix>,v1=<hex>` scheme over the unmodified timestamp and body. The payload contract uses `form` and `submission`, including `_date`, `email`, `firstName`, `artistLabel`, `territories`, `referralId`, `consentMarketing` and the two source paths. No live webhook or dashboard setting was changed. A real sandbox event is still needed to verify this account's exact payload and delivery/retry behavior. The configured production form ID and signing secret are not supplied here.

See [Formspree webhook documentation](https://help.formspree.io/articles/plugins/webhooks/) and [signature verification](https://help.formspree.io/articles/advanced-features/verify-webhook-signatures). The documented webhook feature is plan-dependent; this account's eligibility was not checked.

## Verification

```sh
python3 -m pytest tests/api/test_seller_portal.py -q
python3 -m pytest tests/api/test_portal_mail.py -q
python3 -m pytest tests/api/test_seller_flow.py tests/api/test_spacemusic_api.py -q
node services/spacemusic/portal/check-browser.mjs
ruff check services/spacemusic/portal tests/api/test_seller_portal.py
```

The tests use the existing local Python/FastAPI runtime and bundled Playwright/Chrome. The browser script starts its own loopback server with a temporary private directory outside the repository, uses synthetic data, blocks non-local browser requests and stops that test server when finished. No dependency in the existing production release was changed.

At handoff: 22 portal API tests and 5 existing seller API tests passed. The browser suite covered seven screens at 320, 390, 768 and 1440 pixels, real local API requests, cookies, reload, upload/quarantine/removal, network failure/retry, submission and clarification, sign-out, used-link rejection and escaped input. Fourteen axe checks found no violations; gradient-backed contrast checks still require manual review. Screenshots were visually checked; real Safari and assistive-technology testing remain required before production. Results and timestamps are in `qa/browser-results.json`.

An independent code review found four issues, all fixed and rechecked: upload SQL arity, pre-validation secret writes, a scratch-release startup dependency and missing evidence integrity checks. Added regressions cover each.

Read-only production verification: all 333 public files matched `tmp/pricing-routing-release-20260910`. The existing 33 Apply-navigation checks passed with zero submissions and no browser errors; results are in `qa/production-navigation/`. The production directory, hosting rules, release marker, public content, routes and 139-entry sitemap were not changed. No commit, push or deployment was performed for this work.

## Required before real customers

1. Promote the owner-only sender to a separately reviewed production transport with managed secrets and a durable delivery worker; verify recipient mapping, account approval/quotas, tracking settings, delivery/bounce events and retries. The local sender is not a production outbox. Do not claim delivery when only a local sink, queued record or API acceptance exists. Remove the development mailbox, owner-email test and fixture/reviewer routes entirely from any production entrypoint.
2. Connect and validate the actual Formspree webhook using its signing secret and form ID. Verify a real sandbox receipt, retry and replay; define operational alerts and reconciliation for missed events. Expand the versioned source allowlist from the then-current verified public release without changing SEO routes.
3. Replace the local SQLite/files adapters with an approved encrypted managed database and private object storage. Define retention, deletion, backups, restore drills, file/DB orphan reconciliation and storage quotas. The code intentionally does not claim production durability or compliance.
4. Integrate content-type/signature validation, malware scanning and safe review/download workflows. `TEST_FIXTURE` must never be treated as a production scan pass. Keep all unscanned files quarantined and never upload private statements to public malware-analysis services.
5. Add separately authenticated reviewer access with MFA, roles and revocation, real audit ownership and notifications. The local seller-accessible reviewer simulation must not survive deployment. Decide how revised rights/evidence packages are versioned after submission.
6. Use supported, pinned runtime versions, HTTPS-only host-scoped secure cookies, reviewed proxy/origin configuration, production secret management, distributed abuse protection and operational monitoring. Review magic-link login-CSRF/account-confirmation behavior and conduct independent security testing.
7. Test the full staging path with synthetic data: two different sellers, expiry/reuse/revocation, blocked storage, cross-device email resume, network and provider outages, file access, duplicate deliveries, concurrent updates and recovery. Only then prepare an additive, reversible production release without replacing the marketing build or mounting the old valuation/payout API.

Security design references: [OWASP token recovery guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html), [session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) and [file uploads](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html). These inform the checks; they are not a security certification.
