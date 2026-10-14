# Typeform receiver test and notification status

Date: 2026-09-15. Website/Formspree: unchanged. No additional purchase.

## Authorization and scope

The user approved configuring notifications to hello@spacemusic.io and sending
a clearly marked synthetic application to verify response storage and email
delivery. No real catalog, customer financial information or document was used.
The approved business mailbox was used as the test contact address.

One submission was made to the standalone public Typeform, not through
spacemusic.io or Formspree. No duplicate receiver or website code was added.

## Configured notification: NOT ACTIVE

- [Automation](https://admin.typeform.com/accounts/01M25TV2XKR7KESYQS9AKB5BHW/workflows/01M2JZ3JVVGZ6T60R7SS75NS1G)
- Name: SPACE intake - notify hello
- Trigger: form xzx5SBJb submission is Completed, not partial or button click.
- Recipient: hello@spacemusic.io only. This is an internal alert, not a customer campaign.
- Sender displayed in Typeform: notifications@followups.typeform.io.
- Reply-To: Q3, Which email should we reply to? Its saved selection was verified.
- Subject: SPACE: New intake received
- Heading: New SPACE request received
- Body: A new SPACE intake has been completed. Review the complete response in
  Typeform before replying. Sign in to the SPACE Typeform account:
- Linked URL: https://admin.typeform.com/form/xzx5SBJb/results#responses
- Closing: This inbox contains owner, representative and partnership requests.
  A submission is not a qualified lead, a valuation or an offer.
- No All answers variable, royalty amount, catalog details or document link in
  the email body. The existing vendor account footer was not changed.

The saved subject, body, link, recipient and Reply-To were re-opened and checked.
Clicking Activate showed "Unlock Contacts & Automations" and offered a paid
add-on or Growth Flow. The dialog was closed. The automation still shows Draft;
no add-on was purchased and no Typeform notification was sent by this automation.

This limitation is confirmed by Typeform's current documentation: newer accounts
use the paid Contacts & Automations feature for form-submission email alerts.
Legacy Messages is only available for accounts created before May 20, 2026.
Do not try to bypass that entitlement or assume Plus includes this workflow.

The public pricing page lists USD 25/month for 2,400 actions/month. This is not
an account-specific EUR quote; checkout total, tax and renewal must be checked
and separately approved before purchase. No checkout purchase was attempted.

The user was asked whether to investigate a separate integration without this
add-on or activate the add-on themselves. Pending their choice, do not claim
email delivery is implemented or verified.

## Stored synthetic record

- [Response inbox](https://admin.typeform.com/form/xzx5SBJb/results#responses)
- Marker: TEST ONLY - SPACE QA 20260915-01
- Provider Response ID: 9q7fc947q9zwkfp29q7fc9xme295jlki
- Displayed response time: Sep 15, 2026 18:49 (browser/account display; UI does
  not explicitly label timezone, so no independent UTC timestamp is claimed).
- Before test: Responses showed No responses; performance showed 0 submissions.
- After test: Responses [1], response type Completed.
- Tag: TEST_ONLY, manually applied only to this synthetic record and verified.
- User-facing ending: Your review request has been received.
- Final public submit button visibly reads Send request.

Do not delete the test without approval or count it as a lead. It remains in
Typeform for audit; exclude TEST_ONLY in business reporting. The tag does not
automatically remove it from Typeform's aggregate submission count or quota.

## Field reconciliation

Every value below matched the provider's saved response table and detail view.

| Q | Field | Sent and observed |
| --- | --- | --- |
| 1 | inquiry_type | A catalog I represent |
| 2 | contact_name | TEST ONLY - SPACE QA 20260915-01 |
| 3 | contact_email | hello@spacemusic.io |
| 4 | artist_label | TEST ONLY - Example Label |
| 5 | music_url | https://example.com/ |
| 6 | rights_scope | Both |
| 7 | representative_status | I still need to confirm |
| 8 | revenue_status | I can provide an approximate amount |
| 9 | revenue_ltm_amount | 1000.50, preserved as text |
| 10 | revenue_currency | EUR |
| 11 | revenue_basis | Royalties before those deductions |
| 12 | distributor | TEST ONLY - Example Distributor |
| 13 | catalog_notes | TEST ONLY - SPACE QA 20260915-01. Entirely fictional catalog and royalty amount. No real rights are offered. Do not qualify, market to, or contact as a lead. This record verifies intake field persistence only. |
| 14 | organization | Not asked; empty in saved table |
| 15 | organization_url | Not asked; empty in saved table |
| 16 | partnership_message | Not asked; empty in saved table |
| 17 | referral_note | TEST ONLY - QA 20260915-01 |
| 18 | consent_marketing | No |
| Ending | review confirmation | A. Your review request has been received. |

Result: all 15 answered fields matched. All 3 skipped partner fields were empty.
Unconfirmed representative authority did not cause automatic rejection or a
qualification claim. The submitted record contained no invented territory default.

## What is not verified

- Email send, acceptance, inbox delivery, spam classification and Reply-To headers.
  The automation cannot run until entitlement or integration is resolved.
- The connected Gmail tool's profile is a different mailbox, not hello. Reading
  it would not prove delivery to hello; no unrelated inbox was searched.
- Direct unauthenticated access to the administrative response URL was not tested.
- All stored-answer routes, back-navigation branch changes, retries, duplicates,
  network failures, quota exhaustion and retention policies.
- Website embed, source metadata, seller-only Plausible conversion events or
  website SEO regression checks. The website was not changed in this task.

## Next acceptance step

Resolve the notification mechanism without an unapproved recurring charge.
After it is active, run a newly approved or clearly scoped follow-up test and
verify the actual message in hello's inbox against the stored response. Do not
assume this earlier record will be replayed by a later-activated automation.
Only after the remaining cutover gates pass should /apply/ replace Formspree.

## Primary sources

- [Email notifications and account eligibility](https://help.typeform.com/hc/en-us/articles/13610123653396-Send-email-notifications-to-yourself-or-your-team-when-someone-submits-your-form)
- [Automations vs legacy Messages](https://help.typeform.com/hc/en-us/articles/41693387253140-What-is-the-difference-between-using-Automations-and-Messages)
- [Public add-on pricing](https://www.typeform.com/pricing)

Account UI is the authority for the observed paywall; public pricing does not
authorize a purchase or establish the user's localized checkout amount.
