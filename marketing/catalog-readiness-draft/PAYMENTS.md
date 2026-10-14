# Payments, privacy and release gates

9 September 2026. Implementation specification only. No Stripe objects, invoices,
payment links, submissions or credentials were created or retrieved.

## Smallest safe payment flow

Use a hosted one-time [Stripe Payment Link or customer-specific invoice](https://docs.stripe.com/payment-links)
after a human confirms scope and capacity. No subscription, marketplace split,
Connect account, custom card form or new website backend is needed for this pilot.
Prefer the customer-specific invoice if order matching with a reusable link
cannot be made reliable. Confirm any extra invoicing/tax fees before pricing.

The current task has no callable Stripe connector. Account, balance, charges,
customer history, live eligibility, products and tax registrations are unverified.
Earlier references to sandbox are historical context, not a current account check.

Before launch verify the legal seller/account, account country, live payment
eligibility, payout capability, bank account, receipt/support identity and the
actual hosted live URL. Never put a live secret key in client code, repo or chat.
Do not test live using a real card; [Stripe's testing guidance](https://docs.stripe.com/testing)
requires simulated transactions in the test environment.

## Product configuration draft

| Field | Proposed value / gate |
| --- | --- |
| Name | SPACE Catalog Readiness Report - scoped pilot |
| Mode | One-time, quantity one, no optional upsells |
| Amount | Owner must approve. €99 is the pilot hypothesis; not a live price. |
| Tax | Total customer price and correct treatment confirmed before acceptance. Model uses a 25% inclusive scenario only. |
| Description | One scoped report on supplied master-recording royalty evidence; not an independent valuation, legal review or offer. |
| Customer data | Billing/contact fields legally needed; no royalty data, documents or passwords in Checkout. |
| Order reference | Opaque non-personal reference; private order register maps it to the accepted scope. Do not expose customer/catalog names in URL parameters. |
| Delivery | Approved private channel; agreed date begins only after successful payment and complete accepted inputs. |
| Terms | Dedicated report terms and privacy disclosure, not the unchanged free-review offer policy. |
| Confirmation | Explain payment and next-step status accurately. Never show 'report ready' from a redirect alone. |

## Manual fulfillment control

For each scoped order, a human opens the authenticated Stripe Dashboard and
matches the successful live payment to the order reference, amount, currency
and product. Record its payment identifier privately. Pending, failed, canceled,
refunded or unmatched payments do not start work. Confirm payment status, not
an email, screenshot or customer-facing return URL. [Stripe fulfillment](https://docs.stripe.com/checkout/fulfillment).

Deduplicate by payment identifier and order reference before delivery. If two
payments were taken for one order, resolve with the customer and refund the
unintended duplicate rather than delivering twice. Check for refunds/disputes
before sending. A dashboard refund can be pending; confirm completion and tell
the customer accurately. Do not promise that all processor costs are recovered.

If fulfillment is automated later, validate signed webhooks and amounts, handle
asynchronous payment success/failure, retries, duplicate events and an idempotent
fulfillment record. This pilot does not claim those systems exist.

## Test matrix to execute after access and approval

These tests are **not performed** by the local preview or its unit tests.

| Case | Required result |
| --- | --- |
| Sandbox success | Correct product/amount/currency and order match; no real funds. |
| Decline, canceled checkout | No paid status or work started; clear route to retry. |
| 3DS required / failed | Only successfully completed authorization reaches paid state. |
| Pending asynchronous method | Do not deliver until payment success is confirmed. |
| Double click / two checkouts | One scoped order; accidental duplicate is detected and resolved. |
| Return page not visited | Successful order remains discoverable in Dashboard; no lost delivery. |
| Forged return URL | Does not change order status or unlock a real document. |
| Wrong amount/currency/reference | Hold for manual reconciliation. |
| Refund / duplicate refund attempt | Track status and do not refund twice. |
| Analytics blocked | Payment and manual order register work independently. |
| Receipt / support / tax | Correct legal identity and total; reviewed by responsible operator. |

## Legal and tax launch blockers

Have the responsible accountant/adviser confirm merchant identity, eligible
countries, buyer status, service classification, VAT/sales tax and price display.
[Skatteverket](https://www.skatteverket.se/foretag/moms/saljavarorochtjanster/forsaljningtillandraeulander/saljatjanstertillandraeulander.4.76a43be412206334b89800010696.html)
explains why buyer status and location matter. A PDF delivered by email is not
enough to decide the tax category. Do not assume every artist is B2B or force
a business declaration to avoid consumer rights.

For consumers, confirm precontract information, withdrawal/cancellation route,
the current online cancellation requirements and durable confirmation. If work
starts during a withdrawal period, the correct request/acknowledgment must be
handled; merely delivering a PDF does not justify an automatic no-refund rule.
[Konsumentverket](https://www.konsumentverket.se/lagar/lagen-om-distansavtal-och-avtal-utanfor-affarslokaler/).
Keep statutory rights intact. This document is a launch checklist, not legal advice.

## Privacy and security launch blockers

Approve a private file-transfer/storage channel, named reviewers, MFA, access
permissions, processor agreements and any international transfers before
collecting financial or contractual documents. Keep data outside public Pages,
Git, analytics, payment metadata and AI prompts. Avoid sensitive material in email
subjects. Ordinary email is not automatically an approved secure document channel.

Document the lawful basis, purposes and privacy notice for the reporting service.
Do not silently reuse reporting evidence for acquisition underwriting or marketing;
make the separation and any separately requested review explicit. Apply data
minimization and a defined deletion schedule. [IMY principles](https://www.imy.se/verksamhet/dataskydd/det-har-galler-enligt-gdpr/grundlaggande-principer/).

Proposed working-file retention is 30 days after delivery/correction closure,
subject to approval and legal holds; statutory accounting/payment records need
their own schedule. Do not promise this deletion until it is operational, including
backup handling. A local noindex preview is not suitable for private customer data.

## Protect the current business and SEO

This draft is a separate local artifact, not a deployment snapshot. No production
entry point, title, canonical, content, Apply receiver, event or sitemap is edited.
Do not upload the preview folder over the Cloudflare marketing site.

After separate approval, prefer a small invitation-only pilot before adding an
indexable product page. If a public page is warranted, stage only its addition
against `marketing/RELEASE.md`, preserve every existing URL, leave free content
accessible, and verify links, metadata, mobile, no-JS and the 33 Apply checks.
Never transfer this preview's noindex settings onto production. Use a full
verified predecessor for rollback, not this concept as the site root.
