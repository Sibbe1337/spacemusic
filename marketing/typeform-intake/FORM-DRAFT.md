# SPACE intake: Typeform draft

Prepared: 2026-09-15. Language: English.
Latest status: see IMPLEMENTATION-20260915.md. The replacement Apply is in a
Cloudflare preview, and the isolated Resend transport test is delivered. The
Typeform webhook is not connected and the production website is unchanged.
The wording and earlier build observations below remain the form specification.
Status: BUILT IN TYPEFORM; standalone public link observed 2026-09-15 after
the initial unpublished handoff. Three routes tested in editor preview only.
Draft: https://admin.typeform.com/form/xzx5SBJb/create
The user purchased Plus; confirmation verified in the account. No production
embedding or active delivery integration added by this task.
See TYPEFORM-BUILD-LOG.md for observed results and remaining launch gates.

## Purpose and boundaries

Collect enough information to make the next conversation useful, without turning
an initial inquiry into full due diligence. Separate owners, representatives and
partnership inquiries. No automated eligibility decision, revenue floor, offer,
valuation, payment promise or obligation to sell.

The current form does not request a music link, income or rights information.
This explains missing fields in its email payload; it does not prove that every
Formspree submission has been delivered. Stored responses and notification
delivery still need to be reconciled.

Keep the existing /apply/ page and production receiver until the replacement is
approved and verified. This document does not authorize a production change.

## Welcome screen

**Tell us about your catalog**

Request a free initial catalog review, introduce a catalog you represent, or
contact SPACE about a partnership. You do not need to upload documents now.
This request does not commit you to a sale.

Button: **Get started**

Do not promise a completion time until measured in the actual form. The draft
uses a separate "SPACE intake - Inter" theme with a white background and dark
button. The original shared brand theme and the website remain unchanged.

## Questions and stable field references

These are editorial references, not a ready-to-post Typeform API payload. Record
the actual provider field IDs when building. R = required; O = optional.
Use ordinary question types supported in the selected account. Do not assume a
grouped screen, answer-review feature or plan entitlement until verified there.

### 1. Route and contact: all respondents

| Reference | Type | Required | Exact copy and help |
| --- | --- | --- | --- |
| inquiry_type | Single choice | R | **What would you like to discuss?** Options: Selling my own catalog / A catalog I represent / A partnership or another inquiry. No preselected answer. |
| contact_name | Short text | R | **What is your name?** Help: Your contact name, not your artist name. |
| contact_email | Email | R | **Which email should we reply to?** Help: We will use this to follow up on your request. |

Owners and representatives continue to section 2. Partnership inquiries skip
sections 2 and 3 entirely and go to section 4.

### 2. Catalog: owners and representatives

| Reference | Type | Required | Exact copy and help |
| --- | --- | --- | --- |
| artist_label | Short text | R | **Which artist or label is this catalog released under?** Help: Please enter the artist or label, not the distributor. |
| music_url | Website | O | **Where can we listen to the catalog?** Help: A public artist, label or release page is enough. Do not share private download links or account logins. |
| rights_scope | Single choice | R | **Which rights would you like us to review?** Options: Master recording rights / Publishing rights / Both / I need help identifying the rights. Help: Recordings and the underlying songs can have different owners. This is an initial description, not proof of ownership. |
| representative_status | Single choice | R for representatives only | **Has the owner authorized you to discuss this catalog?** Options: Yes / I still need to confirm. Help: We may ask for evidence of authority before reviewing confidential material. |

Do not automatically reject uncertainty or claim that authority is verified.
Do not ask a representative for unrelated client identities or documents here.

### 3. Income: owners and representatives

| Reference | Type | Required | Exact copy and help |
| --- | --- | --- | --- |
| revenue_status | Single choice | R | **Do you know the catalog's royalty income for the last 12 months?** Options: I can provide an approximate amount / I need to check my statements. Help: Use the catalog and rights you want reviewed, not your entire account if it includes other music. |
| revenue_ltm_amount | Short text with regex | Conditional R | **Approximately how much did those rights earn in the last 12 months?** Help: Enter zero or a positive amount, for example 5600 or 5600.50. Use no currency symbol, spaces or thousands separators. A decimal point or comma is accepted. An estimate is fine. This is not a valuation. Show only when an approximate amount is available. |
| revenue_currency | Short text | Conditional R | **Which currency is that amount in?** Help: For example, USD, EUR or GBP. Show only with the amount. No default currency or conversion. |
| revenue_basis | Single choice | Conditional R | **What does that amount represent?** Options: Royalties payable to the owner after distributor or administrator deductions / Royalties before those deductions / I am not sure. Help: Exclude unrelated catalogs. Tell us below if co-owner shares are included. Show only with the amount. |
| distributor | Short text | O | **Who distributes or administers these royalties?** Help: For example, your distributor or publishing administrator. No account access is needed. |
| catalog_notes | Long text | O | **Anything we should know about the rights you want reviewed?** Help: You can mention co-owners, the share you control, territory limits or specific releases. If you only want to discuss existing releases, say so here. Leave out passwords, bank details and confidential documents. |

The initial amount is self-reported, not verified net proceeds, profit or a
qualification result. Any actual review must establish dates, rights, deductions,
currency and ownership share from evidence. No score or offer is calculated.

The provider Number field silently changed -1 to 1 in preview. It was replaced
with required Short Text and `^[0-9]+([.,][0-9]{1,2})?$` answer validation.
Preview now blocks negative, empty and ambiguous thousands-separated input;
zero and one/two decimal places are valid. This answer is TEXT, not a numeric
API field. Preserve the original string; any later numeric conversion must
validate the complete format and normalize the decimal separator explicitly.

If the respondent changes from an amount to "need to check", hidden stale amount,
currency and basis must not be treated as supplied current answers. Verify what
Typeform stores after branch changes; block launch if ambiguity cannot be
resolved in the provider record or downstream mapping.

Ask recording counts, detailed territorial coverage, split sheets and statement
periods in follow-up when needed, rather than requiring them in this intake.
Never carry forward the current form's unconfirmed "EU, US" default.

### 4. Partnerships only

| Reference | Type | Required | Exact copy and help |
| --- | --- | --- | --- |
| organization | Short text | O | **Which organization do you represent?** |
| organization_url | Website | O | **Does your organization have a website?** Help: Please use a public page. |
| partnership_message | Long text | R | **What would you like to discuss with SPACE?** Help: Briefly describe your role and the proposed collaboration. Please do not include confidential client information. |

Partnerships are inquiries, not catalog applications or qualified seller leads.

### 5. Finish: all respondents

| Reference | Type | Required | Exact copy and help |
| --- | --- | --- | --- |
| referral_note | Short text | O | **How did you hear about SPACE?** Help: Optional. You can name a website or someone who referred you. |
| consent_marketing | Optional opt-in | O | **Email me occasional SPACE news and catalog insights.** Help: Optional. You can unsubscribe at any time. Your choice does not affect this request. Unselected by default; omission is not consent. |

Before the final submission:

**Ready to send?**

You can go back to check your answers. SPACE will use your answers to review and
respond to your request. Your answers will be stored through Typeform. Please
read our [Privacy Policy](https://spacemusic.io/privacy/). Do not include
passwords, bank details or confidential documents.

Final button: **Send request**

Use this notice only after the policy accurately describes the implemented
processing. Do not add a mandatory marketing agreement or bundle a sale contract
into submission. Any provider consent control must match the approved notice.

## Ending screens: only after successful submission

Owner or representative:

**Your review request has been received.**

Thank you. We will review your answers and follow up using the email you
provided. If more information is needed, we will explain what to prepare.
This confirmation is not a valuation or an offer to purchase your rights.

Partnership:

**Your inquiry has been received.**

Thank you. We will review your message and reply using the email you provided.

Do not promise an automatic confirmation email until it is configured and
verified. Do not claim a reference is shown unless the actual provider supports
displaying it reliably. Both endings may offer a link back to SPACE.

## Branch map

1. inquiry_type -> contact_name -> contact_email.
2. Owner -> artist_label -> music_url -> rights_scope -> revenue_status.
3. Representative -> artist_label -> music_url -> rights_scope -> representative_status -> revenue_status.
4. Known revenue -> amount -> currency -> basis -> distributor -> catalog_notes.
5. Unknown revenue -> distributor -> catalog_notes.
6. Partnership -> organization -> organization_url -> partnership_message.
7. All branches -> referral_note -> consent_marketing -> final notice -> Send request.
8. Complete owner/representative -> review ending; complete partnership -> inquiry ending.

Keep back navigation available. Verify actual length and keyboard behavior in
preview; shorten optional screens if they add friction without useful answers.

## Explicitly out of this draft

No file uploads, public statement links, payments, partial-response capture,
automatic newsletter subscription, CRM sync, AI scoring, automatic rejections,
auto-upgrades, production embedding or document-verification claims.

## Sources and implementation status

- [Current release](../RELEASE.md): production baseline and preserved SEO surface.
- [Current intake source](../../services/seller_ui/src/App.tsx): submitted fields and current defaults; see submitIntake.
- [Current public privacy policy](https://spacemusic.io/privacy/): mentions Formspree, not Typeform; requires an approved update before switching.
- [Typeform embedding](https://help.typeform.com/hc/en-us/articles/360029249212-Embed-your-form): standard inline embedding and mobile configuration exist; actual implementation pending.
- [Typeform file access](https://help.typeform.com/hc/en-us/articles/360051567012-File-Upload-question): uploads are limited to 10 MB per file; some exports, integrations and messages create publicly accessible file links. This draft excludes uploads.

Question wording, required flags and routing have been checked in the Typeform
editor and preview. Preview does not store responses. A subsequent user-approved
public-form test reconciled all 15 answered fields for one representative with
known income; see RECEIVER-TEST-20260915.md. Notification activation is blocked
by a paid add-on. Other receiver paths, email delivery and embed behavior remain
unverified. LAUNCH-CHECKLIST.md defines the remaining acceptance gates.
