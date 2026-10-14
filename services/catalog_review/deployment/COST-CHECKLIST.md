# Cost And Procurement Gate

Owner planning allowance: **SEK 1,700/month excluding VAT**, not a vendor hard
cap or a newly calculated FX quote. Absolute new-recurring-infrastructure
approval ceiling: **SEK 2,000/month excluding VAT**. Headroom is SEK 300. Existing
subscriptions, development, legal/security services and Too Lost are excluded.
No auto-scaling, paid reports or distribution spending is approved here.

Preferred stack is Scaleway Paris plus R2 EU/TEM, rather than the earlier small
Render Frankfurt candidate: a 2 GB worker is not a defensible ClamAV/parser memory
budget, and the preferred plan makes independent EU backup placement explicit.
This trades managed application operations for named-operator VM maintenance and
does not provide HA. It does not prove Render cannot work; a resized Render plan
would need a new complete quote and backup-residency evidence.

Record this single complete quote before approval; empty rows block launch:

| Cost component | Required reference quantity | Evidence required |
| --- | --- | --- |
| Paris production API | PLAY2-NANO, 4 GB, full calendar month | Current hourly/monthly quote, disk, IP |
| Paris scan/worker VM | PRO2-XXS, 8 GB, full calendar month | Current quote, disk, signature-update traffic |
| PostgreSQL 17 | DB-PLAY2-PICO, 2 GB, 20 GB encrypted storage | Compute, storage, seven-day backup and restore charges |
| Isolated staging | DEV1-L, 8 GiB, at most 80 running hours/month plus persistent storage/IP | Include real AV test windows and validate combined resource limits; stopped is not free |
| R2 EU primary objects | Pilot bytes and bounded read/write/list operations | EU jurisdiction, storage and operations tariff |
| Paris independent backups | Seven daily DB/document generations plus versions | Encrypted bytes, requests, pruning, restore egress |
| Independent deletion journal | Two durable replicas plus inventory/reconcile operations | Separate retention, no seven-day expiry |
| TEM Paris | Invitation, refresh and predelete notification volume | Send, event/log retention and possible fixed charges |
| Identity | Existing Workspace plus app WebAuthn | No new subscription; verify existing entitlement |
| Monitoring and contingency | Health, metrics, operator alerts, retained logs | Paid ingestion/retention and unexpected usage |

Arithmetic on the approval evidence must use all fixed costs plus quantities
times published unit prices, plus staging and backup restore costs. Convert EUR
and USD subtotals using the operator's dated actual quote/payment FX evidence,
then add an explicit usage/FX contingency. No invented exchange rate is supplied
by this implementation. The resulting approved allowance must fit SEK 1,700-
2,000, and the cost evidence must bind the complete config/release. Verify quotes
again before provisioning; prices and product availability may change.

Set alert thresholds at SEK 1,360 (80% of planning allowance), SEK 1,700 and
SEK 1,800 (90% of ceiling), with projection before month end. These are operator
alerts, not vendor-enforced spending limits. Breach response: stop admitting new
pilot cases, investigate, seek approval. Never silently delete retained evidence,
stop security updates or disable the existing public Apply receiver to save cost.

Official quote inputs (not assertions of a current account-specific price):

- https://www.scaleway.com/en/pricing/virtual-instances/
- https://www.scaleway.com/en/pricing/managed-databases/
- https://www.scaleway.com/en/pricing/storage/
- https://www.scaleway.com/en/pricing/transactional-email/
- https://developers.cloudflare.com/r2/pricing/
- https://render.com/pricing
- https://render.com/docs/regions
- https://render.com/docs/postgresql-backups
