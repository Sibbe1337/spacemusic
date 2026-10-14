# Catalog Review operating decisions

**Superseded by [PILOT-OPERATIONS.md](PILOT-OPERATIONS.md).** The owner selected
Scaleway Paris and approximately SEK 1,700/month, subject to final cost approval.
The Render/Frankfurt alternative below is retained only as historical research.

September 18, 2026. Planning record, not a purchase order or deployment approval.

## Owner decisions

| Decision | Status |
| --- | --- |
| Existing SPACE review design | Approved; reuse Inter, wordmark and editorial layout |
| EU storage requirement | Approved; verify coverage per processor before customer data |
| New portal operating budget | SEK 2,000/month excluding VAT planning ceiling; aim for SEK 1,000-1,500 |
| Exclusions from this infrastructure budget | Existing subscriptions, Too Lost fees, development, legal and independent security work |
| Purchases, vendor contracts and higher spend | Separate approval still required |
| Distribution / white-label business | Deferred by owner; not part of this implementation |
| Paid reports and payments | Not launched; separate scope, permission and economics approval |
| Public website, Apply and SEO | Preserve; no replacement or production deploy in this tranche |

## Candidate infrastructure, not provisioned

Consider a small isolated API, worker and managed PostgreSQL in Frankfurt, with
private EU-jurisdiction object storage. Render lists Frankfurt for services and
datastores. Region selection alone does not establish the location of backups,
logs, support access or control-plane data. Those are approval gates, not assumed
properties. [Render regions](https://render.com/docs/regions)

Render's published reference sizes are USD 25/month per 2 GB service, USD 19/month
for a 1 GB PostgreSQL instance, and USD 25/month for a Pro workspace. One API, one
worker, one database and Pro therefore form a USD 94/month reference before disk,
object operations, mail, identity, monitoring, other usage and taxes. This is not
a complete quote or an FX conversion to SEK. The scan worker's memory and actual
usage still need measuring; the small configuration is not an HA guarantee.
[Pricing](https://render.com/pricing)

Paid Render PostgreSQL has point-in-time recovery; the documented Pro recovery
window is seven days. Backup geography and an actual restore/deletion-journal
drill still need verification. Availability of backups is not proof of recovery.
[Backup documentation](https://render.com/docs/postgresql-backups)

For R2, require an **EU-jurisdiction bucket**, not a best-effort `weur` location
hint. Use the account-specific EU endpoint with a private bucket, scoped server
credentials and no public delivery. This controls object storage jurisdiction;
it does not establish EU residency of every Cloudflare service, log or metadata
path. Object durability is not a separately verified backup strategy.
[Data location](https://developers.cloudflare.com/r2/reference/data-location/)

No infrastructure, keys, DNS, billing alerts or automatic scaling was configured.
The SEK ceiling is an owner spending rule, not a verified vendor hard cap. Before
ordering, include staging costs, usage assumptions, currency buffer, scan memory,
mail/identity costs and a clear operator. Budget recovery must never silently
delete evidence or disable the existing public Apply receiver.

## Important processor gaps

| Component | Known evidence | Remaining decision |
| --- | --- | --- |
| Existing Resend notifications | Resend says stored customer data is in the US; an EU sending region does not change storage location | Do not claim this is EU-only. Leave existing workflow untouched; separately choose an approved portal mail processor |
| Existing Typeform intake | Standard primary hosting is US; EU hosting is offered on specified enterprise/custom plans | The earlier Plus receipt is not proof of current EU hosting. Verify account and data path before any EU-only end-to-end claim |
| Transactional portal mail | Scaleway TEM is a candidate, not selected or connected | Confirm processing/log/backup locations, retention, DPA, delivery/idempotency behavior and price |
| Staff identity and secrets | No production provider configured | Named reviewer MFA, key rotation, regional data handling, offboarding and emergency access |
| Too Lost | Sandbox app registration supplied, no production or paid-report clearance verified | Confirm approved purpose, production access, data location/retention and token semantics |

Sources: [Resend data location](https://resend.com/security/gdpr),
[Typeform data hosting](https://help.typeform.com/hc/en-us/articles/360029581691-What-happens-to-my-data),
[Scaleway TEM](https://www.scaleway.com/en/transactional-email-tem/).

The EU requirement is not silently relaxed. If current intake cannot meet the
agreed boundary, propose an approved migration with reconciliation and fallback;
do not replace Typeform or move mail just to make a checklist look complete.

## Launch sequence

1. Confirm processor/data-location answers, legal identity, retention and operator.
2. Obtain a complete quote and owner provisioning approval within the budget.
3. Provision isolated synthetic staging; pin supported runtimes and dependencies.
4. Connect real identity, mail, storage and scanning; verify quarantines, bounded
   parsers, inbox delivery, reconciliation, key rotation, restores and erasure.
5. Verify the read-only Too Lost adapter with authorized sandbox tests only.
6. Integrate signed intake forwarding without replacing today's working receiver.
7. Run independent launch review; seek explicit approval for a small free pilot.

No distribution, automatic offers, valuation guarantees, payouts or paid orders
are added by accepting this document or completing local tests.
