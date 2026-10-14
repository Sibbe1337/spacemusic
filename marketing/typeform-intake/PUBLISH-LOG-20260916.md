# Typeform intake production release

Published: 2026-09-16, approximately 06:00 UTC (08:00 Europe/Stockholm).
Authorization: owner explicitly requested deployment and use of the existing
signing configuration. No plan, add-on or payment purchase was made.

## Release boundary

- Live: https://spacemusic.io/apply/
- Deployment: https://6dea26c1.spacemusic-a6n.pages.dev
- Project/branch: spacemusic / main.
- Package: `tmp/typeform-intake-release-v3-20260915`.
- Tested preview: https://d4f64dbd.spacemusic-a6n.pages.dev/apply/
- Immediate rollback: `tmp/pricing-routing-release-20260910`, deployment
  https://a74ea86c.spacemusic-a6n.pages.dev.
- 338 public files plus `_headers` and `_redirects`; former assets retained.
- Content changes: guided Apply intake and matching SSR/client privacy notice.
  Other HTML changes only the versioned entry-module reference.
- No old design drafts, payments, paid reports, customer datasets, unrelated
  backend changes or private configuration were uploaded with the public site.

The official locally versioned Typeform SDK loads only after Start. The original
Formspree receiver remains an explicit fallback, never an automatic second send.
The notification Worker is separate from website routes. Completed Typeform
responses remain the record even when an alert fails. No automatic customer
email, valuation, qualification, offer or marketing subscription was enabled.

## Verification

- Before publication all 333 baseline public files still matched production.
- All 338 immutable-preview files matched the candidate. A fresh guarded rebuild
  was byte-identical to V3; 335 existing files retained, five assets added.
- 11 intake DOM tests and 22 Worker/runtime/credential tests pass. These 33 tests
  are not the historical 33 Apply-navigation browser checks.
- After publication all 338 public files matched spacemusic.io byte-for-byte.
- All 139 sitemap URLs passed HTTP status, canonical, H1 and robots checks.
  The sitemap and hosting control files are unchanged. No production noindex.
- All 24 pricing.md routing checks pass; llms.txt canonical, plain-text MIME,
  redirect, bot-UA and unrelated-route checks pass.
- Production Apply loads the intended form xzx5SBJb. The actual frame has
  no-referrer policy and disable-tracking, with allowlisted paths only.
  No page errors were recorded in the inspected production Apply tab.
- Production privacy content renders the Typeform/Cloudflare/Resend/Google
  disclosure and retention wording. Server content also matches the package.
- Earlier preview evidence: 24 real Apply links across seven page families,
  native fallback validation and four widths without horizontal overflow.
  Latest mobile owner completion also had no overflow at the tested width.

## Real synthetic form evidence

All test contacts used hello@spacemusic.io, example.com and fictional information.
All four stored QA responses are tagged TEST_ONLY. Exclude them from leads and
outreach. The three active-webhook tests each have one accepted D1 send attempt,
no error and a cleared encrypted reply-address field.

| Route | Completed UTC | Typeform response | Resend message | Verified result |
| --- | --- | --- | --- | --- |
| Partnership | 2026-09-16 05:25:18 | aw7xbzskirtnmaaw7xbjxnpox44y9u24 | a5230e35-edab-4f4b-89b1-ddff037730d8 | Eight answers match; seller fields absent; 202 after signing repair; delivered |
| Owner, unknown income | 2026-09-16 05:51:26 | 3205ob89lfp7uoxujie4ae73205ob845 | eafcc185-f74f-4d54-ad80-a41c78ef8c70 | Eleven answers match; amount/currency/basis and representative fields absent; 202; delivered |
| Representative, zero income | 2026-09-16 05:59:23 | st7h0fejro9zu75qist7hmnrloilc6cb | 00b3d214-a068-44cb-9a01-4a37f78b2ad1 | Fifteen answers match; amount is string 0, EUR, net basis, authority unconfirmed; 202; delivered |

The last test entered through the preview homepage: both hidden paths persisted
as `/`. Direct Apply tests correctly have landing `/apply/` and empty referring
path. Marketing consent is No. Typeform shows Completed and the intended ending.
The website displayed Request received only after the provider completion.

Partnership re-delivery after rollback returned 202 at 05:47:28 UTC without
changing its provider ID or send-attempt count. Resend delivered means recipient
mail-server acceptance, not inspected inbox-versus-spam placement. Alerts go only
to hello@spacemusic.io and contain an authenticated response-inbox link, not the
royalty answers. No Formspree test lead or real customer message was sent.

The earlier September 15 representative response
`9q7fc947q9zwkfp29q7fc9xme295jlki` verifies known decimal income storage, not the
later webhook. The direct transport test is also not a Typeform completion.

## Active key configuration

Worker version: `2779ef5d-d7ab-44d8-96c5-a981d3824d1b`, code 20260916-v2.
The owner explicitly retained the original signing credential after exposure
was explained. A Wrangler rollback restored just that signing version from the
uncompleted rotation; Typeform already held the matching configuration. HMAC
verification stays enabled. Encryption and Resend credentials are unchanged.

The inactive local replacement was renamed to
`~/Library/Application Support/SpaceMusic/typeform-intake/typeform-webhook-secret.unused-rotation-20260916`.
The staged `.rotation-20260916` file is also inactive. The conventional local
key path is absent; do not run rotation or transport helpers assuming it matches
production. Do not print credentials. A future rotation must coordinate both
ends and verify a provider-origin delivery without losing the queued responses.

## Explicit limitations and operating checklist

- Plausible goals/reporting for intake_started/intake_submitted are unverified.
  These are generic intake events, not qualified seller leads. Completion
  records and manual qualification must be reported separately.
- Full historical browser matrix, branch-back stale answers, history navigation
  and complete blocked-embed/no-JavaScript browser interaction are not verified.
  Static fallback and mocked failure cases are tested separately.
- A fresh PageSpeed API request returned 429. No new three-run LCP comparison,
  performance improvement, ranking effect or conversion lift is claimed.
- Typeform response auto-upgrade was already ON and was left unchanged. Warning
  recipient, capacity recovery and a confirmed daily review operator remain
  operational follow-ups. Suggested operator is Emil, not a confirmed assignment.
- Review Typeform's completed response inbox daily during launch. Do not depend
  only on email. Investigate failures using the existing response and notification
  reference; do not reset idempotency or duplicate the request to force an alert.
- No automatic bounce escalation, customer acknowledgement, upload step, paid
  report or fully automated catalog-review backend is part of this release.

## Rollback

After checking the correct Cloudflare account, deploy the complete immediate
baseline, not an older design snapshot:

```sh
npx wrangler@4.132.0 pages deploy tmp/pricing-routing-release-20260910 \
  --project-name spacemusic --branch main --commit-dirty=true
```

Retain Typeform submissions, D1, Formspree history and existing credentials.
Reconcile responses arriving during rollback. Do not restore the inactive
signing-only version. If the webhook must be paused, record the pause and review
stored responses before re-enabling it. Verify public files and SEO again.
