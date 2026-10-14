# Too Lost confirmation request

Unsent draft for owner review. No recipient is assumed, no request submitted,
and this document does not amend the registered application or agreement.

Subject: SPACE Catalog Review: approved use case and sandbox clarification

Hello Too Lost Developer Team,

We are preparing SPACE Catalog Review, a voluntary, read-only connection for
artists and labels who want us to review their existing music catalog. SPACE
may be a potential buyer. We would use the supplied information for human-led
review, not automatic offers, eligibility decisions or rights verification.

Our first release would let the account owner authorize access, confirm the
connected account, select existing releases and supply supporting documents.
Future releases would not be automatically included. We would not change
distribution, create releases, download audio or initiate royalty payments.

Before connecting any customer account, could you confirm:

1. Is user-initiated import of release metadata and reported royalty history
   for this purpose within the approved use case, including necessary paginated
   retrieval and bounded storage? What volume and historical coverage are allowed?
2. Which calculations and reconciliations may we perform? We propose dated
   source summaries, missing-period disclosures and comparisons with documents
   the same customer supplies, without automated valuation or decisions.
3. Separately, would a one-time paid, manually reviewed Catalog Readiness Report
   delivered only to that account owner require an amended approval? The free
   acquisition review would remain available; payment would not buy an offer.
   We would not describe the report as independent while SPACE may be a buyer.
4. What are the permitted storage and retention rules for normalized records,
   supporting snapshots and derived reports, including on disconnection or
   revocation? What must be deleted, and when?
5. What approval is required for our hosting, database, private storage and mail
   processors? The production provider/region list will be supplied for review
   before launch. No data will be sent to other buyers or used for AI training.
6. Our sandbox app registration now lists authorization at
   `https://sandbox.toolost.com/oauth/authorize`, token exchange at
   `https://sandbox.toolost.com/oauth/token` and the registered callback
   `https://spacemusic.io/api/integrations/toolost/callback`.
   We intend to request only `read:profile`, `read:releases` and `read:sales`,
   although the app-level allowlist is broader. Does this reduced scope set
   cover the proposed workflow, and how are missing grants communicated?
   Could you confirm access/refresh token expiry, refresh-token rotation and
   revocation support? We have not yet implemented or tested the callback.
7. For `/sales/overview`, how is currency represented and what exactly does
   `total` mean: gross, net, payable or another reported basis? How are periods,
   partial months, corrections, refunds and release-level allocation defined?
8. Where can we export the current official OpenAPI specification? Are there
   sandbox fixtures that demonstrate pagination, missing history, mixed
   currencies and token lifecycle behavior?
9. Which ordinary low-volume sandbox functional tests are authorized? We will
   not run load, penetration, vulnerability or benchmark testing against your
   systems without prior written permission.

We currently have a local prototype containing synthetic data only. No live
connection, customer data import or paid report has been activated. We would
appreciate written confirmation of the initial purpose and a separate decision
on the optional paid-report use case before either is launched.

Best,
Emil
SPACE

## Basis

The questions derive from the user-supplied API Developer Agreement dated
September 17, 2026, the sandbox registration excerpt supplied September 18,
and the API documentation inspected during planning:

- https://developer.toolost.com/docs
- https://developer.toolost.com/docs/api
- Local approved plan: `docs/toolost-launch-plan-20260917.md`

This draft requests clarification; it does not assert that any unanswered
commercial or technical point is already authorized.
