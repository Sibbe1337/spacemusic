# Pilot Operations Runbook

## Launch Is Still Closed

No procurement or deployment is authorized by these files. Obtain named legal
entity/organization number and operator, provider/location evidence, current
all-in quote, real integrations, independent security review, recovery drill and
explicit five-customer free-pilot approval. Capture content hashes/reviewer/time
in a read-only launch manifest outside application backups. Evidence expires in
at most 90 days; every action rechecks current generation and runtime observations.
An operator attestation is not cryptographic proof of a vendor location.

Use Scaleway Paris fr-par-1: dedicated 4 GB API VM, dedicated 8 GB scanning/worker
VM, managed PostgreSQL 17 with 20 GB encrypted block storage and verified seven-day
backup geography. These are operator-managed machines, not HA. Patch OS/kernel,
container runtime, Python, parsers and ClamAV; review pinned releases and rebuild.
Budget time for incident response and restarts. Backups do not provide uptime.

Use `review.spacemusic.io` and `review-staging.spacemusic.io` only. Dedicated local
TLS proxy, no public API container listener, strict forwarded-header trust,
host-only Secure HttpOnly cookies, no cookie Domain shared with marketing and no
CORS. Review proxy body limits (25 MiB plus bounded protocol overhead), upload
timeouts and headers; proxy configuration/certificates/DNS remain operator work.

Staging must have separate database, roles/credentials, buckets, OAuth callback,
cookie host, generation and launch evidence. Synthetic staging never imports
customer snapshots and cannot use live mail bindings. The approved staging
choice is DEV1-L (8 GiB), with at most 80 running hours per month, not a 2 GB VM.
The [official instance datasheet](https://www.scaleway.com/en/docs/instances/reference-content/instances-datasheet/)
confirms that memory capacity. Measure the combined API/AV/parser peak and retain
the networkless parser boundary before accepting a shared staging host. If that
topology cannot meet its resource limits, require a revised approved quote rather
than silently adding another VM. Stopped compute can still incur disk/IP charges.
Do not borrow production secrets to save staging cost.

## Memory, Isolation And Monitoring

The 8 GB worker VM reserves 4 GiB for ClamAV, 1.5 GiB networked worker, 768 MiB
parser and 256 MiB signature updater, leaving roughly 1.5 GiB for OS/overhead.
One parser request at a time; clamd one scan thread; disable concurrent signature
database reload to avoid doubled database memory. Bound stream, expanded scan,
archive recursion and parser CPU/memory. Malware scanning is AV only, not proof
that a PDF/XLSX/CSV is safe to parse. The isolated parser's verified Linux boundary
is required; worker-side `network_isolated=true` is not acceptable evidence.

Start only the trusted signature updater for its separately approved network
access. It holds no documents or portal secrets; scanner mounts signatures read
only. Clamd SelfCheck reloads updates. Readiness must fail on absent/older-than-24h
signatures, engine error, OOM, missing Unix socket or parser isolation failure.
PING alone proves neither signature freshness nor safe parsing.

Collect real bounded checks outside request handlers: DB connectivity and role/
RLS rights, complete migration plan hash, service Settings origin/generation,
OIDC/JWKS readiness, WebAuthn UV policy, TEM delivery/bounce reconciliation, private
EU R2 capability, fresh AV signatures, parser boundary, retention job progress and
both deletion-journal replicas. Refresh evidence at most every 30 seconds.
Do not make an external provider request per HTTP request, and do not turn probe
errors into healthy responses. Metrics must contain counts/latencies, not document
names, email addresses, query strings, tokens or request bodies.

Before pilot prove alerts to the named operator for readiness loss, failed jobs,
backup age >26h, journal mismatch, signature age, pool saturation, disk >75%, OOM,
mail uncertain/bounce backlog and projected cost. Monitoring stack/config and
real probes are not supplied or claimed live by this package.

## Storage, Mail And Identity

Require an EU-jurisdiction R2 bucket, not a weur location hint. Use only the
account-specific HTTPS EU endpoint, distinct private environment buckets, scoped
server credentials, no public ACL/domain/r2.dev access. Verify actual jurisdiction
in vendor evidence before any customer document. R2 object durability is not an
independent backup. Never delete an object to compensate for an uncertain remote
put or DB commit; reconcile using the service's idempotency protocol.

Use Scaleway TEM Paris for new portal notifications, metadata-minimal content,
no document attachments. Verify DPA, account region, message/log/backup retention,
delivery and bounce handling. Preserve the durable uncertain-send state before
the single send attempt; do not blindly retry acceptance timeouts. Existing Apply
Typeform/Resend remain unchanged and may process outside the EU.

Use existing Google Workspace OIDC with exact issuer/audience/nonce/PKCE and
preapproved staff subject, then application WebAuthn user verification. Hosted
domain is not an authorization list. Register primary and backup credentials,
supervised enrollment/recovery, role/assignment checks and offboarding revocation.
No extra IdP subscription is assumed. Workspace control-plane/authentication
processing is not asserted entirely EU; document that boundary. EU storage claims
cover NEW portal stored customer data only, not all mail recipients/identity
processing or the existing intake chain.

## Seven-Day Backups And Restore

1. Configure managed PG daily backups with seven-day retention; verify where they
   and service logs are stored. Keep an independently restorable, client-encrypted
   daily logical database export in Paris object storage as well. Encryption keys
   and generation authority must not live only in the backed-up database/VM.
2. Back up private document bytes (including PDFs, XLSX and CSV), not just DB rows
   or R2 keys, to an independent Paris versioned bucket. Use immutable capture
   batches with object digest, opaque workspace/object identifier, capture time
   and exact version ID. A consistent capture manifest references a completed DB
   snapshot; fail the batch if referenced bytes are missing. Never place names or
   document content in operational manifests. Copying remains bounded/streamed.
3. Keep seven days of completed backup generations. Explicitly prune expired
   captures, all noncurrent versions and delete markers; also abort incomplete
   multipart uploads. Provider lifecycle is a safety net, not an exact seven-day
   deletion guarantee. Observe deletion completion and provider propagation;
   report overdue copies rather than declaring an exact hard retention bound.
4. The deletion journal is independent of rolling application backups, stored in
   both R2 EU and Paris with restricted append/reconcile access. Record stable
   source suppression first so an older pre-intake DB restore cannot re-admit the
   same source. Inventory **both source and workspace keys across both replicas**,
   including a source-only record from a partial write. `contains(workspace)`
   alone is insufficient. Call `reconcile(workspace, source=None)` to complete
   missing keys/copies from any durable record; False means no record, not a
   completed erasure. Stop on corrupt, conflicting or unavailable evidence.
5. Every approved erase removes active objects and addresses their independent
   backup versions according to the approved erasure policy. Existing versions
   may already have been erased: restore inventory must exclude journaled objects
   and treat confirmed absence as expected, never resurrect them from another
   replica. Do not expire suppression journal entries with seven-day snapshots;
   coordinator owns the pseudonymous journal retention/legal policy.
6. Restore into a fenced, isolated environment with invitations, intake and mail
   disabled. Obtain a fresh externally held generation before loading backups.
   Read current journal inventory independently of restored state; apply the
   union of durable suppression records, reconcile both replicas/keys, erase or
   suppress restored rows/blobs and all source-only matches. Reconcile current
   inventory again at cutover under a write fence to avoid a concurrent erase
   race. Reapply complete checked migrations/grants and verify RLS.
7. Invalidate all customer/staff sessions, invitations and stale delivery/worker
   leases under the new generation, preserve suppression source-digest key
   compatibility, and keep uncertain sends non-retryable. Confirm all retained
   object hashes and that erased versions cannot be served. Only a collector
   bound to the new config/generation and latest durable journal watermark may
   return objects_verified and source_tombstones_reconciled True. Counts alone
   are not a completeness proof; an append-only inventory epoch/manifest is
   needed where journal object storage has no sequence API.
8. Record actual recovery time and lost-data interval from the drill. Daily
   backups imply up to roughly 24h data loss unless verified PITR improves it;
   no RTO promise before measurement. Obtain fresh launch approval and reopen
   only after all gate checks pass. Keep old backup generations inaccessible and
   enforce their original expiry rather than restarting a seven-day clock.

These are implementation constraints and runbooks, not a completed backup or
restore scheduler. No fake journal watermark or dummy object verification may
be used to open the gate. Coordinator owns inactivity/predelete notice semantics
and the complete erasure plan.

## Official Sources

- https://www.scaleway.com/en/docs/managed-databases/postgresql-and-mysql/how-to/create-a-backup/
- https://www.scaleway.com/en/docs/object-storage/how-to/enable-versioning/
- https://www.scaleway.com/en/docs/object-storage/how-to/create-a-lifecycle-rule/
- https://developers.cloudflare.com/r2/reference/data-location/
- https://developers.cloudflare.com/r2/buckets/object-lifecycles/
- https://www.scaleway.com/en/transactional-email-tem/
- https://docs.clamav.net/manual/Usage/Configuration.html
- https://developers.google.com/identity/openid-connect/openid-connect
