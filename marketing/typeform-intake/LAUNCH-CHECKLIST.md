# Typeform intake: acceptance and cutover checklist

Prepared: 2026-09-15. Updated 2026-09-16: PRODUCTION DEPLOYED.

Current production is 6dea26c1. See PUBLISH-LOG-20260916.md and
IMPLEMENTATION-20260915.md for final evidence and explicit residual test gaps.
The signed webhook is ON; owner, representative and partnership test responses
were reconciled with stored data and delivered internal alerts. The historical
checklist below is a test plan, NOT a claim that every row was completed.

## Current state

- Authenticated Typeform workspace: My workspace, account 01M25TV2XKR7KESYQS9AKB5BHW.
- External form built: https://admin.typeform.com/form/xzx5SBJb/create.
- Initial handoff was unpublished. On the later Plus confirmation turn, the
  standalone form loaded at https://form.typeform.com/to/xzx5SBJb. Not embedded
  on spacemusic.io by this task; do not assume the DRAFT name prevents responses.
- User purchased Plus: confirmation shows 1K responses/month, EUR 70 plus
  EUR 17.50 VAT, EUR 87.50 paid. Auto-upgrade status remains unverified.
- Three routes reach their intended endings in editor preview; see TYPEFORM-BUILD-LOG.md.
- No real lead, royalty document or credential copied into Typeform.
- No Formspree response-store audit completed; do not claim the old service loses responses.
- Notification address approved by user: hello@spacemusic.io. Internal alert
  configured, but activation was blocked by the Contacts & Automations add-on.
  No extra purchase or email send occurred. Existing Formspree recipient unchanged.
- Approval to prepare is not approval to buy, publish, change recipients or migrate leads.
- Automation "SPACE intake - notify hello" now contains the completed-response
  trigger, only hello@spacemusic.io as recipient, a response-inbox link and Q3
  as Reply-To. It remains Draft because Plus alone does not unlock activation.
- One user-approved synthetic public-form submission was stored as Completed.
  All 15 answered fields matched; 3 partner-only fields were empty. The record
  is tagged TEST_ONLY and must be excluded from lead/conversion reporting.
  See RECEIVER-TEST-20260915.md for the reference and field reconciliation.

## Build the unpublished form

- Confirm the intended SPACE workspace and user before creating the form.
- Name it "SPACE catalog review - DRAFT 2026-09-15".
- Copy the approved question wording and implement all three routes.
- Map editorial references to actual provider field IDs. Keep the map with this draft.
- Verify optional questions, numeric validation, skipped answers and back navigation.
- Turn off partial-response collection, lead scoring, response auto-upgrades and
  unrequested integrations. Do not purchase a plan without approval of exact terms.
- Do not place real customer records in the draft or an AI form-builder prompt.
- Confirm plan capacity and required features in the actual account, not from
  assumptions based on a pricing page or a free editor preview.

## Receiver is the record; email is an alert

- Use the provider's completed response ID and timestamp as the authoritative
  submission reference. Verify its exact field name and stability in this account.
- Do not invent a reference from a button click or count email notifications as leads.
- Reconcile every field of each synthetic test against the stored response.
- Alert emails should link to the authenticated response view where supported,
  without financial details or private files. Verify this link requires login.
- Confirm the notification address and sender/reply-to actually used by Typeform.
  Do not promise that notifications come from hello@spacemusic.io by default.
- Keep a documented manual check of completed responses so an email outage does
  not hide a request. Agree an operator and review cadence before launch.
- Distinguish completed seller requests, representative requests, partnerships,
  unreviewed records and qualified leads. Qualification remains manual.
- Confirm response quota, warning recipients and recovery route if the form closes.
  Do not silently opt into paid overages.

## Field migration contract

| Current field | Proposed record | Rule |
| --- | --- | --- |
| firstName | contact_name | Ask the contact name; never replace a blank name with an artist silently. |
| email | contact_email | Store in provider only; no analytics property. |
| artistLabel | artist_label | Only for catalog routes; distributor has a separate field. |
| territories | No default | Unknown until supplied later. Do not convert the old "EU, US" constant into a verified fact. |
| referralId | referral_note | Optional respondent text, never analytics metadata. |
| consentMarketing | consent_marketing | Explicit opt-in only. Blank or skipped means consent not granted. |
| source | form_version/provider | Static system provenance, not a user claim. |
| landing_path | landing_path | Existing allowlisted public path only; unknown stays empty. |
| apply_source_path | apply_source_path | Existing allowlisted public path only; no full URL, query or fragment. |

All new fields remain self-reported. Preserve old historical records in place;
do not migrate or relabel them automatically. Hidden fields are untrusted
attribution metadata, not identity or authorization signals.

## Privacy and analytics gates

- Approve a privacy-policy change describing actual Typeform processing and
  remove inconsistent blanket third-party-sharing language where necessary.
  Verify processor terms, retention/deletion, access and transfer arrangements;
  do not claim EU-only storage or legal compliance without evidence.
- Keep marketing opt-in separate from service correspondence. No marketing send
  for false, blank, skipped or missing consent.
- No upload question in phase one. A later document step requires a separately
  approved storage/access flow and test with a synthetic file only.
- No forwarding of the full browser URL into an embed. Set only explicit,
  allowlisted public landing/source paths using supported configuration.
- Before replacing the form, verify the supported embed event semantics.
  application_submitted must correspond to a completed catalog response, not
  form load, a submit click, an ending redirect or a partnership inquiry.
- If the embed cannot distinguish the routes without exposing answers to
  analytics, leave that event disabled and report provider-completed counts
  separately. Do not pollute the existing seller conversion series.
- Never send Typeform response IDs, names, emails, URLs containing identifiers,
  music links, royalty amounts, answers, tokens or documents to Plausible.
- Blocked analytics must not affect submission. Never POST the same request to
  both Formspree and Typeform as a hidden duplicate backup.

## Test matrix: live acceptance still pending

Selected UI-only checks passed in editor preview; results are in
TYPEFORM-BUILD-LOG.md. One representative/known-income public-form response was
then reconciled field by field; see RECEIVER-TEST-20260915.md. Other paths,
retries, branch-change persistence and delivery acceptance remain unverified.
Do not equate the single happy-path test with comprehensive live acceptance.

Use fictional Example Artist/Example Partner and example.com addresses in
preview. Use an owner-approved real test mailbox only for the isolated delivery
test, with explicit authorization before sending. No production lead tests.

| Test | Acceptance evidence |
| --- | --- |
| Owner, known income | Each answer matches the stored completed response; no representative question. |
| Owner, unknown income | Submission succeeds; no amount or invented currency. |
| Representative, authority unconfirmed | Correct questions and manual-review state; not auto-qualified/rejected. |
| Partnership | No seller income questions; separate ending and no seller conversion event. |
| Zero income | Zero is accepted and stored accurately, not converted to missing. |
| Negative/blank amount | Clear validation; no completion for invalid required input. |
| International name/email | Accepted valid input remains intact in record and authorized notification. |
| Optional fields skipped | Submission succeeds; blank consent is not granted; no phantom default territories. |
| Known -> unknown via Back | Stale hidden income cannot be mistaken for current supplied data. |
| Seller -> partner via Back | Stale seller answers cannot trigger catalog qualification or seller analytics. |
| Double submit and retry | Document provider behavior; no duplicate counted as unique lead; no false success. |
| Connection failure | No false received state; recovery preserves answers where supported. |
| Blocked analytics | Completion works without analytics; no PII-bearing telemetry. |
| Embed blocked or JavaScript off | Existing page text and a usable fallback are present. |
| Phone and keyboard | No clipping/focus traps; labeled inputs, visible focus and working Back/Next. |
| Notification failure | Stored request remains visible and recoverable without an email. |
| Capacity reached | Owner alert and tested fallback; no silent paid upgrade or dead end. |

Do not submit an unpublished preview and assume it persists. First confirm the
vendor preview's storage behavior. If receiver testing requires publication,
obtain approval for a separate synthetic-only test form before that step. A
public but unlinked URL is not private access control.

## Approved cutover, later

1. Preserve the full current verified release and existing Formspree form/history.
2. Build a preview from marketing/RELEASE.md, never an old design prototype.
3. Embed only on /apply/ using supported code; keep surrounding server HTML,
   headings, copy, canonical, metadata, navigation and all 139 sitemap URLs.
4. Include an accessible fallback. Until the switch is approved, the original
   form remains the default. After switching, explain fallback use and avoid
   automatic dual submissions. Test a blocked Typeform host explicitly.
5. Use noindex on the hosting preview, not on production. Measure layout and
   mobile loading behavior; lazy initialization must not cause a blank form.
6. Run existing 33 Apply-navigation checks plus the completed matrix above.
7. Review the actual preview and policy draft with the owner. Confirm subscription,
   recipient, production form ID, retention and fallback before publishing.
8. Deploy only the approved diff. Open /apply/, representative SEO pages and
   fallback live. Do not send a real or fake customer application as a live test.
9. Record deployment, form version, verified behavior and open limitations here.
   Restore the preserved release if intake, routing or content regresses.

## Source references

- [Typeform embeds](https://help.typeform.com/hc/en-us/articles/360029249212-Embed-your-form)
- [Explicit hidden fields](https://help.typeform.com/hc/en-us/articles/360029264632-Using-URL-parameters-with-embedded-forms)
- [File uploads and shared file links](https://help.typeform.com/hc/en-us/articles/360051567012-File-Upload-question)
- [Current public privacy policy](https://spacemusic.io/privacy/)
- [Verified production release](../RELEASE.md)

These references establish available mechanisms, not completed account setup,
verified end-to-end delivery, guaranteed SEO outcomes or improved conversion.
