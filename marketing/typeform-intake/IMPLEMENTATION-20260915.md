# Typeform intake: implementation and deployment record

Updated: 2026-09-16. Status: PRODUCTION DEPLOYED.
Current release: https://6dea26c1.spacemusic-a6n.pages.dev and https://spacemusic.io/.
See PUBLISH-LOG-20260916.md for final evidence and remaining limitations.
The dated history below records intermediate states, not current blockers.

### Subsequent deploy request

The user requested deployment again after the connection prerequisite was
explained. Cloudflare authentication was checked, all 333 production files
still matched the baseline, and all 31 automated tests passed again. Typeform
redirected the admin webhook URL to login. The Plus account emil@qlero.io was
not among the signed-in Google accounts. Login was handed to the user; no
different account was selected, webhook activated or main deployment made.
Resume from authentication, then verify the connection and remaining gates
below. Do not confuse the available Cloudflare access with Typeform access.

### Access restored and webhook prepared

On the user's "prova nu" follow-up, the qlero.io Chrome profile exposed the
authenticated account. The prior login blocker was in the separate kodkod
profile, not proof that the Typeform account itself had lost its session.
Browser numeric IDs changed across reconnects; verify profile/account instead
of assuming a previously used numeric ID still identifies the same profile.

After the follow-up deploy authorization, the specified endpoint was added in
Typeform. Its visible state was Webhook OFF. Edit showed an empty Secret and
Completed responses selected. The user was asked to enter the already prepared
signing secret and Save changes personally; the credential file was queued to
open in Codex. Do not enter a new credential on the user's behalf or activate
an unsigned webhook. No new Typeform response or notification was submitted.

Plan & billing was read in the authenticated account: Plus, 1 of 1,000 monthly
responses used, reset October 15, 2026 at 18:39 GMT+2, Contacts & Automations Off.
Automatic response-tier upgrades are ON. This setting was reported to the user
and left unchanged; no plan/add-on purchase was made. Agree a cost/capacity
policy rather than treating the current paid tier as a guaranteed spend cap.

An additional normal homepage-to-Apply link check passed. Back/forward testing
was interrupted by browser-control timeouts, so remains unverified. No test
submission, production website change or security bypass resulted.

### Signed connection check, 2026-09-16

After the user reported the secret saved, Typeform's delivery log showed two
synthetic test requests returning HTTP 401, response body `Invalid signature`.
The latest displayed delivery was `01M2M9RP8GMME9XDQR5FPR3AC6`, at 07:06:53 in
the UI (payload timestamp 05:06:54 UTC). A Typeform-Signature header was present.
The saved webhook remained OFF and its switch was disabled, including after
reload. Do not force-enable the UI or disable receiver signature verification.
The user was asked to replace Secret with the prepared signing key (not the
Resend API key) and save it. The Edit dialog was left open for that handoff.

The actual synthetic payload exposed an independent mapping bug: the editor
UUIDs are field `ref` values, not the webhook's `field.id`. The receiver now
uses observed email ID `oY3yxQa3CAD3` and name ID `cIEzRJe4jZWW`. A regression
test uses literal observed wire IDs and rejects an editor ref used as an ID.
This fixes parsing but does not explain away or bypass the signature failure.

Only the isolated Worker was redeployed, version
`2779ef5d-d7ab-44d8-96c5-a981d3824d1b` (`20260916-v2`). All 21 receiver tests and
11 intake tests passed. The existing synthetic transport reference was reused
twice with current field IDs: both returned 202, while its D1 row retained the
same provider ID, seven historical attempts, accepted status, cleared cipher
and no error. No second provider send occurred. This still does not verify
Typeform-origin signing or a new completed response.

All 333 public production files were re-fetched and matched the immediate
baseline byte-for-byte. No marketing production deployment was made.

### Saved-setting follow-up and real completion, 2026-09-16

The user reported `Webhook saved!`. The authenticated UI showed Webhook ON.
A fresh provider test, `01M2MAJ515S7GRWDN23YTZVVCT`, at 05:20:48 UTC again
returned HTTP 401 `Invalid signature`. No secret value was read into logs or
changed by the agent. The local recovery key has 64 hexadecimal characters,
no outer whitespace, and owner-only permissions. The empty Edit password
field alone is not proof that a saved secret is absent.

To distinguish a synthetic-test problem from a real delivery problem, one
clearly labelled partnership response was completed from the immutable V3
preview using the SPACE mailbox and fictional example information:

- Name: `TEST ONLY - SPACE QA PARTNER 20260916-01`.
- Response: `aw7xbzskirtnmaaw7xbjxnpox44y9u24`, completed 05:25:18 UTC.
- Delivery: `01M2MATD2GNWRF50WRF67H1ABX`, also HTTP 401.
- All eight partner-path answers persisted in Typeform and matched the
  supplied test values. Marketing consent was No; catalog/income fields were
  absent, as expected for the partnership path.
- `landing_path=/apply/`; `apply_source_path` was empty, correctly reflecting
  direct navigation to the preview rather than inventing a referring page.
- The preview displayed Request received. Typeform showed Completed, ending
  B (inquiry), and the response was tagged TEST_ONLY. Exclude it from leads.
- D1 still held only the previously accepted synthetic transport row. The
  new completion had no accepted notification. Do not claim email delivery.

The webhook was paused through its normal visible Webhook ON label; OFF was
verified. The nested switch's disabled attribute is a UI implementation
detail: the visible label toggles the setting normally, without DOM changes.
Edit was left open for the user to replace Secret with the existing prepared
key and Save changes. The credential-file view was queued in Codex to help
the handoff. No further form completions or marketing deployment should be
made until signature verification succeeds. Reuse/redeliver this test after
repair instead of creating duplicate responses.

### End-to-end success and signing-key rotation, 2026-09-16

After the user copied the actual key into Typeform and saved it, the existing
partner QA response was redelivered. No additional response was submitted.
Typeform displayed HTTP 202 at 05:37:39 UTC for delivery
`01M2MATD2GNWRF50WRF67H1ABX`.

- D1 notification digest: `71b151b4a480c1cce98aab65c029e6009ecadb040d833bb1a121aa3d2505a4c5`.
- D1 status: accepted, attempts: 1, no error.
- Resend ID: `a5230e35-edab-4f4b-89b1-ddff037730d8`.
- Resend created: 2026-09-16 05:37:40.098 UTC; last_event: delivered.
- To and Reply-To: SPACE mailbox. Subject: [TEST ONLY] SPACE: New intake received.
- Delivery means acceptance by the recipient's mail server; inbox-versus-spam
  placement was not inspected. This is actual Typeform-to-Worker-to-Resend
  evidence, unlike the earlier direct synthetic transport test.

The previous signing key had appeared in the conversation. With the webhook
visibly OFF, only TYPEFORM_WEBHOOK_SECRET was rotated. Encryption and Resend
credentials, response records and receiver code were not changed. The secret
deployment at 05:40:37 UTC is `0639a5fc-5062-47c8-bc5d-b819a7d52718`.
The current private key file now contains the replacement. A retained private
staged key makes retrying this specific rotation idempotent. The new helper
has a regression test for remote failure, local preservation and retry.
All 22 receiver/runtime/credential tests pass; the 11 intake tests last passed
earlier on the unchanged intake code.

Two direct transport retries signed by the replacement returned 202 using
the already accepted synthetic response reference. Typeform itself has NOT
yet been verified with the replacement. Edit was left open for the required
user credential-entry handoff; webhook remains OFF. The user subsequently
asked to use the existing key, but rotation had already completed. Do not
rotate again or restore the exposed key without a new explicit decision.
After the user saves the replacement, redeliver the same partner QA record
and confirm the provider ID/attempt count do not change before proceeding.
Marketing production has not been deployed.

### Owner-approved signing configuration and production cutover, 2026-09-16

The owner explicitly authorized using the existing key and requested deployment.
At that point Typeform was still signing with the original configuration while
the receiver had the replacement. After a fresh authenticated account check,
Wrangler rolled back only the signing-secret version to
`2779ef5d-d7ab-44d8-96c5-a981d3824d1b`. Receiver code remains 20260916-v2;
encryption, Resend credentials and D1 records were not changed. No credential
was entered through browser automation and no unsigned bypass was introduced.

The existing partner response redelivery returned 202 at 05:47:28 UTC. Its
provider ID and one send attempt stayed unchanged. The webhook is ON. The
owner/unknown-income completion at 05:51:26 UTC and representative/zero-income
completion at 05:59:23 UTC both returned 202 and each produced one delivered
internal alert. Answers and hidden paths were reconciled; all test records are
tagged TEST_ONLY. The historical September 15 representative test predates the
webhook and is not mail-delivery evidence.

The owner's security exception retains a signing credential previously exposed
in the conversation. Do not reproduce it or claim it was rotated successfully
end to end. The unused replacement was moved from the conventional local path
to `typeform-webhook-secret.unused-rotation-20260916` in the private application
support directory. `typeform-webhook-secret.rotation-20260916` also refers to
the inactive replacement. The normal local `typeform-webhook-secret` path is
absent. Do not run the rotation or live transport helper blindly: active
configuration is already stored in Cloudflare and Typeform. A future rotation
requires a coordinated, owner-approved change and provider-origin verification.

After byte-verifying the baseline and immutable preview and rebuilding the
candidate identically, the exact V3 package was deployed to Pages main. All
338 live files and all 139 sitemap routes passed post-deploy checks. See the
publish log for browser evidence and residual testing/measurement gaps.

## Production boundary

- Previous main / rollback: a74ea86c, `tmp/pricing-routing-release-20260910`.
- Current main: 6dea26c1, `tmp/typeform-intake-release-v3-20260915`.
- All 333 public baseline files matched spacemusic.io before work began.
- Candidate: `tmp/typeform-intake-release-v3-20260915`.
- Verified immutable preview: https://d4f64dbd.spacemusic-a6n.pages.dev/apply/
- Candidate branch: `codex/typeform-intake-20260915`, Pages project `spacemusic`.
- Candidate alias: https://codex-typeform-intake-202609.spacemusic-a6n.pages.dev/apply/
- The approved main-branch Pages deployment is complete. No DNS change,
  Formspree recipient change, lead migration, subscription purchase,
  report/payments launch or CRM was included.
- The Typeform -> Cloudflare -> Resend endpoint is ON and verified using actual
  synthetic form completions, not just direct HTTP transport tests.

## Implemented

The existing Apply shell, H1, page metadata, canonical and process copy remain.
A locally versioned official Typeform SDK loads only after an explicit start.
The form ID is xzx5SBJb. The short-form alternative retains the existing
Formspree receiver; it never receives an automatic duplicate of a Typeform reply.
Missing contact names and territories are not fabricated.

The guided form serves owners, representatives and partnership inquiries.
Unknown income is permitted; nothing is automatically qualified, rejected,
valued or offered. Uploads and payment questions are not part of this release.

Only allowlisted public landing/source paths are forwarded. Browser query
strings, fragments, answers and response IDs are not analytics properties.
Typeform completions use `intake_submitted`, not the legacy seller-only
`application_submitted`. Plausible goal registration/reporting for these new
events has NOT been verified. Do not combine their counts into qualified leads.

The privacy-policy changes are present in both SSR and client content in
production. Other HTML changes only its versioned entry-module
reference. The builder compares the complete restored Apply head, all other
HTML, every existing binary/config file and all 139 unchanged sitemap URLs.
The 335 original files remain, with five versioned assets added.

## Typeform changes verified in the UI

- Form renamed to SPACE catalog review.
- Typeform branding disabled; embedded welcome screen confirmed unbranded.
- Sending partial responses to integrations disabled; no partial capture added.
- Only `landing_path` and `apply_source_path` URL parameters enabled.
- Settings saved and edits published in Typeform.
- The previous paid Contacts & Automations flow remains Draft/inactive.
- Webhook is ON with the explicitly owner-approved original signing
  configuration. Three real synthetic form completions have delivered alerts.
- Auto-upgrade is ON; quota alert recipients/settings remain unverified.

The previous single synthetic Typeform response remains tagged TEST_ONLY. Its
15 answered fields were reconciled in RECEIVER-TEST-20260915.md. That is prior
receiver evidence, not proof of this new notification connection.

## Notification service

- Worker: `space-intake-notifications`.
- Endpoint: https://space-intake-notifications.samplehubkupp.workers.dev/typeform
- Health: https://space-intake-notifications.samplehubkupp.workers.dev/health
- Active version: 2779ef5d-d7ab-44d8-96c5-a981d3824d1b (owner-approved rollback
  of the secret-only rotation; receiver code is 20260916-v2).
- D1: `space-intake-notifications`, c8fee9f4-8312-4443-a70c-130a326a2774,
  created with the EU jurisdiction constraint. This does not imply EU-only
  processing by Typeform, Resend, Google or the overall flow.
- Managed secrets: TYPEFORM_WEBHOOK_SECRET, REPLY_ENCRYPTION_KEY, RESEND_API_KEY.
  No secret is in public assets or this document. Private files are in
  `~/Library/Application Support/SpaceMusic/typeform-intake`, owner-only. The
  signing files there are inactive replacements; see the current key-state note.
- Resend sending domain verified; open/click tracking disabled.
- Sender: SPACE intake <hello@spacemusic.io>; recipient: hello@spacemusic.io.
- Reply-To is the single email field's supplied address, not an arbitrary
  payload recipient. Alert body includes an authenticated Typeform inbox link,
  submission time and hashed notification reference, not answers or documents.
- Raw-body HMAC verification, exact form/email field IDs, bounded body size,
  timestamp checks, AES-GCM reply-address storage, atomic leases, provider
  idempotency and durable retry are covered by tests.
- Cron runs every five minutes. Automated retries stop before Resend's
  idempotency retention expires. Late failures require manual reconciliation,
  not resetting attempts or sending a new message key blindly.
- Acceptance by Resend clears the encrypted address. `accepted` does not mean
  delivered; a later bounce does not remove the completed Typeform response.

## Evidence, not assumptions

33 automated checks pass: 11 intake DOM tests and 22 worker/runtime/credential
tests. These use simulated provider responses, except the explicit test below.
An independent read-only review found no remaining actionable findings after
the two retry/key-initialization fixes. No unrelated worktree edits were used.

Actual Workers runtime initially rejected `redirect: error`. The failure was
reproduced with Miniflare, fixed to `manual`, and covered by a runtime regression
test. Resend redirects are not followed with credentials.

Synthetic transport event `TEST_ONLY_TRANSPORT_20260915_01` was sent repeatedly
with the same signature/body. Exactly one notification row and one Resend
message were produced. This script DOES NOT create a Typeform response.

- Resend message: 34556685-4c42-47fd-a917-b44cf1b7516d.
- Created: 2026-09-15 18:24:05.928 UTC.
- Verified event: `delivered`, meaning accepted by the recipient's mail server;
  Gmail inbox-vs-spam placement was not inspected.
- D1: accepted, provider ID matched, error cleared, encrypted address removed.
- To and Reply-To both hello@spacemusic.io for this test; expected subject and
  authenticated inbox link confirmed. Seven attempts include the pre-fix
  runtime errors, not seven emails. No customer email was sent.

Preview v2 (`fba7f7e8`) was byte-verified: all 338 public files matched.
24 actual Apply links from seven page families reached the correct standalone
page. Direct /apply, /apply/, query/fragment navigation, the mobile menu and
native empty-email validation were inspected. Native validation prevented
submission and focused email; Tab moved to artist/label. No Formspree test
lead was sent. Four widths (320, 390, 768, 1440) showed no horizontal overflow.
The embed's real `referrerpolicy=no-referrer` attribute was verified.

The old 33-check browser suite was NOT run unchanged: it expects the old form
DOM and includes browser instrumentation outside the approved UI surface.
Programmatic history navigation, no-JavaScript browser interaction, a complete
blocked-Typeform browser scenario and three-run performance comparison remain
unverified. Static fallback and simulated failure cases are covered separately.
Do not label the partial browser coverage as all 33 legacy checks passed.

V3 only removes the short-form fallback that used artist/label as a missing
contact name. The added unit assertion passed. All 338 public preview files
match the candidate, and the actual embedded welcome screen opened correctly.
Apply, privacy, sitemap and robots returned 200. Preview responses have an
X-Robots-Tag noindex header; production counterparts do not. Both sitemaps have
139 URLs. Live Apply still has the original form and its original canonical.

## Post-launch follow-up and limitations

Signed provider delivery, three branch completions, source attribution,
production file verification and SEO routing checks are complete. No claim is
made that the entire historical acceptance matrix passed.

1. Confirm quota warning recipient and a manual daily response-review owner.
   Auto-upgrade remains ON as observed, unchanged by this launch.
2. Register/verify Plausible goals for the new generic intake events. Production
   launched without claiming those reports or qualified-lead counts work.
3. Finish browser branch-back/stale-answer, full blocked-embed/no-JavaScript
   interaction and history-navigation cases. Initial branch-specific skipped
   answers were verified; changing branches after entry is not the same test.
4. Repeat the three-run mobile performance comparison in one environment.
   The fresh PageSpeed API attempt returned 429; no new LCP result is available.
5. Plan a coordinated signing-key rotation if the owner changes the explicit
   decision to retain the exposed existing credential. Do not create another
   mismatch or change unrelated encryption keys as a troubleshooting shortcut.

## Operations and rollback

Typeform completed responses are the authoritative record, not email delivery
or analytics. Review its authenticated response inbox at least daily during
launch (recommended operator: Emil; cadence needs confirmation). Keep owners,
representatives, partnerships, unreviewed leads and qualified leads separate.
Check TEST_ONLY tags before outreach or measurement. Never auto-subscribe a
respondent on the basis of blank/No marketing consent.

For missed alerts, first check the Typeform record, Resend delivery status and
D1 status. Do not delete or reset the original notification to force a resend.
An accepted message can still bounce later. A failed notification needs manual
review in Typeform; there is no automatic operator escalation or delivery-status
webhook yet. Logs contain bounded technical codes, not provider response bodies.

Safe status query (milliseconds converted for display):

```sh
npx wrangler d1 execute space-intake-notifications --remote --command \
  "SELECT status, COUNT(*) AS total FROM notifications GROUP BY status;"
```

Run in `marketing/typeform-intake/notification-worker`. Inspect failed records
privately; never put response data into public artifacts. The local `sender`
secret helper only refreshes the Resend key. Encryption/signing initialization
refuses an existing local OR remote key; rotation is a separate migration, not
a repair for an unknown decryption error.

If marketing cutover fails, redeploy the complete immediate baseline directory
`tmp/pricing-routing-release-20260910` to project spacemusic / branch main, not
the older design or calculator preview. Preserve Typeform responses, Formspree
history, D1 and keys. Disable the Typeform webhook if repeated delivery failures
require an operational pause; reconcile stored responses before re-enabling.

## Primary references

- https://www.typeform.com/developers/webhooks/
- https://www.typeform.com/developers/webhooks/secure-your-webhooks/
- https://www.typeform.com/developers/embed/configuration/
- https://www.typeform.com/developers/embed/callbacks/
- https://resend.com/docs/api-reference/emails/send-email
- https://resend.com/docs/dashboard/emails/idempotency-keys
- https://resend.com/docs/dashboard/domains/tracking

These document mechanisms, not ranking guarantees, legal compliance or measured
conversion gains. The completed production launch is evidenced separately in
PUBLISH-LOG-20260916.md.
