# Typeform draft build and verification

Date: 2026-09-15. Status: STANDALONE FORM PUBLIC; NOT CONNECTED TO WEBSITE.
Initial handoff was unpublished. See the later status update below.

## Deliverable

- [Editor and Preview](https://admin.typeform.com/form/xzx5SBJb/create)
- Name: SPACE catalog review - DRAFT 2026-09-15
- Form ID: xzx5SBJb
- Workspace: My workspace (rJRipe), account 01M25TV2XKR7KESYQS9AKB5BHW
- At initial handoff, workspace showed 0/10 collected responses and 10 free responses.
- No Share/publish action, plan purchase, CRM connection, lead migration or email
  send was performed by the agent. The user subsequently purchased Plus.
- No production files, deployment, canonical URLs, sitemap or Formspree recipient changed.

The empty user-created form was renamed and built in place. An initial AI
builder attempt failed; questions were imported and then descriptions, required
flags, types, branching and endings were manually checked/configured. The AI
chat can still show an old failure message; that is not a respondent error.

## Later Plus confirmation and public-status check

- The user's Plus purchase was verified on Typeform's account checkout
  confirmation: 1K responses/month, EUR 70 plus EUR 17.50 VAT, EUR 87.50 paid.
  The card details were not copied into this log. Renewal and auto-upgrade
  settings were not inspected or changed.
- The existing Share tab supplied https://form.typeform.com/to/xzx5SBJb.
  Opening it showed the real welcome screen and Get started button. Therefore
  the standalone link is now public despite "DRAFT" remaining in its title.
- No public-form answers or submissions were entered during this status check.
- The Workflow email action opened a new vendor template named "My new
  automation", visibly marked Draft with an Activate button. Its default is
  completed form -> email to respondent, subject "Form submitted". It was
  not activated, configured with an owner recipient or used to send mail.
- Before proceeding, confirm hello@spacemusic.io as the owner-alert destination
  and approve a controlled synthetic receiver/delivery test. Do not confuse
  respondent confirmation with an owner alert or assume either is working.
- Prior free-plan observations below are historical. Recheck actual Plus
  entitlements and current settings before enabling any additional feature.

## Actual provider fields

Latest operational status: see RECEIVER-TEST-20260915.md. On user approval,
the notification was configured but remained Draft behind the Contacts &
Automations paywall. One tagged synthetic response was submitted and reconciled.
Earlier "no submissions" and "no configured recipient" observations above
describe the initial handoff, not this later test.

These IDs were read from the editor/preview DOM. Editorial references are not
configured API refs. Confirm actual response/export mapping before integration.

| Q | Editorial reference | Provider field ID | Type | Required |
| --- | --- | --- | --- | --- |
| 1 | inquiry_type | eb00ad73-e4dd-4e61-b323-56b48331135a | Multiple Choice | Yes |
| 2 | contact_name | 7a65518f-c26e-4e4d-b747-a168808badf9 | Short Text | Yes |
| 3 | contact_email | 3581eeb5-a11f-45bd-88e3-0713d4474afb | Email | Yes |
| 4 | artist_label | f0b6d546-c5e9-4317-a81d-b353ec22d410 | Short Text | Yes |
| 5 | music_url | 2e2a511e-fd03-4a13-811d-247cddaf93bf | Website | No |
| 6 | rights_scope | 49ed7f07-7649-4576-99b9-4fa90016a493 | Multiple Choice | Yes |
| 7 | representative_status | 0ae19b99-fd8b-460d-b7be-4e26d89a79a7 | Multiple Choice | When shown |
| 8 | revenue_status | 68610886-3e2a-48a1-9c0a-9ca04f147f6e | Multiple Choice | Yes |
| 9 | revenue_ltm_amount | 29c79229-b23d-47b3-babe-c606edc10df6 | Short Text + regex | When shown |
| 10 | revenue_currency | 6f18e190-0e8f-432c-87b3-29e6b8fb466b | Short Text | When shown |
| 11 | revenue_basis | c83555f8-1dd8-4a7d-8b40-d736ca401608 | Multiple Choice | When shown |
| 12 | distributor | 619eb1cc-0bb1-43c0-82b0-f01c7d949120 | Short Text | No |
| 13 | catalog_notes | 25b4a0c2-09db-4ed4-acd7-ed26bde1b14b | Long Text | No |
| 14 | organization | 1dc3f5d2-361d-4316-8319-0a8ee69a974d | Short Text | No |
| 15 | organization_url | 3c45174f-8a4a-4b9e-97f6-851503c83c8d | Website | No |
| 16 | partnership_message | 35fff3d9-9b0a-422b-9c2c-a88ee7382bcf | Long Text | When shown |
| 17 | referral_note | fadabdc7-e772-4823-8e21-8c72f7cb5633 | Short Text | No |
| 18 | consent_marketing | eab9f9c3-6941-4399-9770-f3d39cb7e20a | Multiple Choice Yes/No | No |

Welcome: dce4f4c3-1856-4da2-b9da-f43a9f2fc8b7.
Final statement S1: cd143a23-698b-4b15-a3a2-636d5a32dd33.
Review ending A: 2a618924-04ec-413b-93a6-b92abe0d72c1.
Partnership ending B: 3c77673a-9f08-4f4f-bb56-6ee93d48ac19.

## Saved logic

1. After Q3: if Q1 is partnership, Q14; otherwise Q4.
2. After Q6: if Q1 is owner, Q8; otherwise Q7.
3. After Q8: if approximate income available, Q9; otherwise Q12.
4. After Q13: always Q17, skipping partnership-only questions.
5. After S1: if Q1 is partnership, ending B; otherwise ending A.

Other questions continue in order. Typeform confirmed "Your logic has been
saved." No scoring, automatic rejection or minimum annual revenue was added.
Question numbers/counts in preview change with the selected route.

## Preview observations

Only synthetic names and example.com email addresses were used. No customer
records, documents, bank data, passwords or API keys were entered.

| Check | Observed result | Scope/limitation |
| --- | --- | --- |
| Partner, desktop | Contact -> organization/message -> referral/opt-in -> inquiry ending B | No seller rights or income questions; preview only |
| Owner, known income, mobile | Skips Q7; displays amount/currency/basis; skips Q14-16; ending A | Original Number input subsequently replaced; full receiver untested |
| Representative, unknown income, mobile | Shows Q7, allows "I still need to confirm", skips Q9-11, skips Q14-16, reaches A | UI does not verify authority or qualify lead |
| Invalid email | "not-an-email" blocked; corrected example.com address advances | No deliverability proof |
| Empty required name | Validation appears; does not advance | Preview only |
| Optional questions | Music/org links, distributor, notes, referral and marketing can be skipped | No default territories field exists |
| Marketing | Yes/No both initially unselected; No and blank can finish | Blank is not consent; no newsletter integration added |
| Number input defect | Entering -1 advanced and Back showed 1 | Replaced with regex-validated Short Text |
| New amount: -1 | Remains -1 with "Please enter a valid format"; no advance | No silent absolute-value conversion |
| New amount: empty | Cleared with Select All/Backspace; remains on question | Generic format error; instructions describe accepted format |
| New amount: 0 | Advances; Back preserves 0 | No positive revenue floor |
| New amount: 1000.50 / 1000,50 | Both advance; Back preserves original string | Stored as text; future conversion must be explicit |
| New amount: 1,000 | Blocked as ambiguous/invalid format | Thousands separators prohibited in help copy |
| Back navigation | Returns to previous question and preserves entered amount in UI | Branch-change stale answer persistence still untested |
| Privacy notice | Link to https://spacemusic.io/privacy/ visible/clickable | Policy still needs approved Typeform processing update |
| Mobile welcome | White background, dark CTA, readable Inter; no clipping observed | Typeform simulated mobile, not physical device testing |
| Vendor accessibility checker | Color, Alt text, Content and Other all "All clear!" | Not a full WCAG or assistive-technology audit |

The final Statement's custom button did not change the actual Submit label.
The global Language -> "Button to send typeform" message was then changed to
"Send request" and saved. End-to-end routes were tested before this label-only
change; verify its rendered label again during the pre-launch pass.

## Presentation and existing account settings

- New selected theme: SPACE intake - Inter. Inter font, white background, dark CTA.
- Existing Spacemusic brand theme was not edited.
- Welcome completion-time estimate and submission-count badge off.
- Both endings have their own buttons and social-sharing controls off.
- Typeform's vendor branding remains; removing it is not included in the current plan.
- General settings observed: navigation, progress bar, required markers and autosave on.
- Partial response capture, enrichment, spam prevention and duplicate prevention off.
- Cookie-consent control off; applicable consent/storage setup remains a launch review item.
- Existing "Send email when form is signed" control was on with the account address.
  No Signature question exists. This is NOT verified completed-response email delivery;
  it was not configured or used by this task. Review before publication.
- Response auto-upgrade settings, retention, processor terms and all organization-level
  integrations have not been fully audited. Do not infer they are disabled or compliant.

## Launch blockers, in order

1. Owner reviews this unpublished draft and approves final questions.
2. Confirm subscription capacity and required features; approve exact price before purchase.
3. Confirm notification destination (proposed hello@spacemusic.io), sender/reply-to and
   who checks the authenticated response inbox independently of email alerts.
4. Approve and run an isolated receiver/delivery test using a designated test mailbox.
   Reconcile every answer, completion reference and timestamp with the stored record.
   Test retries, network failure, duplicates and branch changes, not just the happy path.
5. Update and approve privacy copy, retention/access arrangements and any consent setup.
6. Implement allowlisted source metadata and seller-only analytics without PII. The
   embed's submit callback alone does not reveal whether the route was a partnership.
7. Prepare /apply/ preview from the verified release, test fallback and existing SEO/
   navigation checks, then obtain production approval. Keep Formspree until this passes.

No automated business metrics, improved conversion or complete delivery is claimed.

## Primary sources

- [Preview does not collect responses](https://help.typeform.com/hc/en-us/articles/8047347611540-Do-test-responses-count-towards-my-response-limit)
- [Answer validation](https://help.typeform.com/hc/en-us/articles/47605590883476-Answer-validation)
- [Branching logic](https://help.typeform.com/hc/en-us/articles/360029116392-What-is-branching-logic)
- [Embedding](https://help.typeform.com/hc/en-us/articles/360029249212-Embed-your-form)
- [URL parameters in embeds](https://help.typeform.com/hc/en-us/articles/360029264632-Using-URL-parameters-with-embedded-forms)
- [Embed callback semantics](https://www.typeform.com/developers/embed/callbacks/)
- [File upload limits and access](https://help.typeform.com/hc/en-us/articles/360051567012-File-Upload-question)
- [Current SPACE privacy policy](https://spacemusic.io/privacy/)

Vendor documentation describes capabilities, not successful setup in this account.
