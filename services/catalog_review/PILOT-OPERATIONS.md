# Approved Pilot Operating Decisions

September 18, 2026. Supersedes the earlier Render/Frankfurt candidate proposal.
This is an implementation specification, not evidence of resources purchased
or an approved final supplier quotation.

| Component | Approved pilot configuration |
| --- | --- |
| Portal/API | Scaleway Paris PLAY2-NANO, 4 GB, review.spacemusic.io |
| Scan worker | Separate PRO2-XXS, 8 GB, one concurrent scan |
| Database | Managed PostgreSQL 17, DB-PLAY2-PICO, 20 GB, private TLS |
| Staging | Separate project/secrets, DEV1-L, at most 80 running hours/month, review-staging.spacemusic.io |
| Documents | Private R2 bucket with explicit EU jurisdiction |
| Document backup | Separate versioned Scaleway Paris bucket |
| Portal mail | Scaleway TEM, separate sender subdomain; preserve Gmail/root MX |
| Secrets and operational logs | Scaleway Secret Manager and Cockpit; no customer content in logs |
| Pilot | 3-5 manually approved customers; server admission ceiling of five |
| Retention | 90 days of real inactivity; notice 14 days before; backup history at most seven days |

Planning estimate: approximately SEK 1,700/month excluding VAT, subject to a
complete refreshed quote and the approved SEK 2,000 planning ceiling. Neither
amount is a supplier-guaranteed billing cap. Include staging, backup copies,
object operations, traffic, logs, mail and currency contingency. Maintenance and
existing subscriptions are excluded. This topology requires server maintenance
and is not highly available. Do not provision until the final total is approved.

Primary references to verify when preparing the final quotation:
[Scaleway compute](https://www.scaleway.com/en/pricing/virtual-instances/),
[managed databases](https://www.scaleway.com/en/pricing/managed-databases/),
[R2 jurisdiction](https://developers.cloudflare.com/r2/reference/data-location/).
The names above are the user's configuration choice, not independently confirmed
current stock/pricing or an assertion that all processing is EU-only.

## Data Boundaries

Portal customer data, documents, backups and operational logging require verified
EU residency. Existing Typeform/Formspree and Resend are separate processors and
remain untouched; do not advertise the entire funnel as EU-based. Region labels
alone do not prove support, metadata, backup or control-plane handling.

Register portal mail on a distinct sender subdomain. Do not delete or replace
the current Google MX/SPF/DKIM records. Use separate stage/production keys and
separate constrained erasure credentials, never a migration-owner application
login. Keep the deletion journal outside application backup/restore history.

## Sequential Release Gates

1. Confirm legal company name, organization number, accountable operator and
   supervised staff-recovery authority, supplier terms/DPA and itemized final cost.
2. Provision synthetic staging only with separated projects, secrets, storage,
   mail boundaries, TLS and current patched/pinned images.
3. Verify real invitation outcomes, mandatory passkeys, quarantine/parsing,
   counters/limits, monitoring and reconciliation against installed services.
4. Restore an older backup after deleting synthetic cases. Apply the external
   journal and revoke old generations before opening any route or worker. Verify
   all live-prefix objects and backup versions, not only lifecycle settings.
5. Independent security review; remediate critical findings. Preserve the public
   Apply flow and all 141 sitemap URLs.
6. Deploy closed production, invitations off. Check alarms, delivery, backup,
   actual restore, rollback and legal/support copy. Admit at most five customers
   manually only when the server gate's real evidence is complete.

Too Lost runs on a separate track: rotated secret, callback at the relevant
portal origin, verified read scopes, sandbox results and separate production
approval. No callback bridge through marketing. It does not block documents.

Distribution, payments, automatic valuations and marketing edits are excluded.
No security, ranking or uptime guarantee is made.
