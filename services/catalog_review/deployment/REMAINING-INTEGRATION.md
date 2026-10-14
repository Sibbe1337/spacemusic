# Engineering Handoff: Not Deployment-Ready

The safe bootstrap is implemented, but `runtime.build_dependencies` is not.
It is an **engineering gap**, separate from external vendor/legal approval.
No `operations/dependencies.py` containing a pretend implementation is supplied.
The coordinator can expose a reviewed implementation at the single allowlisted
symbol. The following code must still be completed and tested before selecting it.

| Remaining code | Required behavior |
| --- | --- |
| Mounted-secret loader | Explicit `/run/secrets` files only; bounded size, required field/type checks, no logs/repr of secrets, no ambient SDK credential discovery. Separate API/worker, migration, erasure and backup identities. |
| Concrete adapter assembly | Build `PooledDatabase`; explicitly credentialed, bounded-timeout boto3-compatible HTTPS clients for `R2BlobStore` and two `S3JournalReplica` instances (EU R2 and Paris); bind `ReplicatedDeletionJournal`, Unix `ClamAVScanner` and `UnixSocketDocumentParser`. No network calls during module import. |
| Identity assembly | Build non-test `StaffSettings`, shared-pool staff repository, bounded `GoogleOIDCTransport`, `GoogleOIDCVerifier` and `StaffService`; implement JWKS refresh lifecycle, strict callbacks, real WebAuthn verification and preapproved identities. |
| Core/intake/mail assembly | Build approved core Settings, `ReviewService` with stable source-digest key and deletion journal, immutable `TypeformMapping`, bounded signature-checked `IntakeService`, `TEMTransport` and `MailDispatcher` with active-workspace/journal checks. Supply the same bound instances to `compose_portal`, not duplicate stores or test factories. |
| Real collectors | Concrete bounded background probes for every REQUIRED_ADAPTERS key, using actual observations and real timestamps. Observe AV signature age, parser process/container isolation and IPC, migration checksum, RLS privileges, identity/JWKS, mail reconciliation and storage/journal reachability. No constant-green records. |
| Restore authority/inventory | External generation and authenticated inventory/watermark bound to the restored release. Enumerate source AND workspace tombstones from both replicas, reconcile partial writes, suppress pre-intake restores, verify remaining object versions and session invalidation. Only then publish current `RestoreState`; no manufactured sequence numbers. |
| Single ASGI gate integration | The coordinator has implemented `compose_portal(..., wrap_guard=True)`, with a safe default. The future trusted builder must explicitly pass `wrap_guard=False` and return inner ASGI so build_runtime applies exactly one outer gate. No further inner-mode refactor is needed; dependency assembly remains unimplemented. Do not silently unwrap an app or substitute fake status. |
| Builder/job lifecycle | Return `RuntimeDependencies(adapters, app_builder, restore_provider)`. Builder receives config, adapters, require_invitations, gate, status_provider and uses the explicit inner ASGI contract above. Wire `PilotJobs` to guarded dispatch/dispatch_retention/refresh_retention and a bounded real scheduler. Choose its explicit worker entrypoint; compose currently hard-stops. Close clients/pools/tasks on shutdown and on partial construction failure. |
| Backup/erasure execution | Client-encrypted consistent seven-day DB/document backup batches, independent versions, observed pruning and fenced restore automation. Separate erasure-role process and source-first journal reconciliation; not the API worker credential. Coordinator owns erasure semantics. |
| Container/proxy verification | Cache the pinned base images and full hashed amd64 wheelhouse; build and inspect allowlists, vulnerability review, exact imports, Unix ownership, nonroot sandbox, memory/OOM and signature lifecycle. Implement/review local TLS proxy configuration and actual monitoring/alerts. |

Already completed: strict operations configuration; manifest/runtime/restore
gates; bounded pool; checksummed full pilot migration runner; scoped erasure role
checks; guarded mail dispatch; exact server-webhook origin exception; allowlisted
bootstrap; default-deny recipes; separate networkless parser/ClamAV composition;
offline unit/Compose tests and a real PostgreSQL 17.9 migration/pool/RLS smoke.

External launch blockers remain legal entity/organization number, named operator,
current complete price approval, processor/location/DPA evidence, actual delivery/
identity enrollment, successful restore drill and explicit customer invitation
approval. Completing code does not satisfy these gates or authorize procurement.
