# Catalog Review Operations

Implementation and local verification only. Nothing here provisions resources,
reads vendor accounts, authorizes uploads, or opens production invitations.
Shared core, SQL and test fixtures are owned by the coordinator and other agents.

## Integration Contract

`operations.bootstrap:create_app` is the container entrypoint. With no explicit
factory selection it serves health only, and readiness is **503**. Selecting a
factory does not bypass launch gates. The only accepted selection is:

```text
REVIEW_RUNTIME_FACTORY=services.catalog_review.runtime:build_dependencies
```

The coordinator must implement `build_dependencies(*, config)` in that module.
It returns `operations.bootstrap.RuntimeDependencies(adapters, app_builder,
restore_provider)`, not an ASGI app. No arbitrary module or mounted Python file
can be selected. Missing, invalid or failed assembly stays closed. This symbol
and real mounted-secret assembly are not implemented by the operations package.

`app_builder(*, config, adapters, require_invitations, gate, status_provider)`
must return the inner ASGI application. The coordinator now supports
`runtime.compose_portal(config=..., gate=..., status_provider=..., service=...,
document_store=..., staff=..., intake=..., wrap_guard=False)` for this trusted
builder. The default `wrap_guard=True` stays safe for standalone composition.
The builder must select False explicitly so build_runtime owns the single outer
operations gate; do not use fake probes or silently extract a wrapper's
application attribute. The inner-ASGI hook is implemented; concrete dependency
assembly and real collectors still are not.
Use the supplied guarded mail dispatcher and invitation callback in jobs too.
Do not use `create_test_app`, test Settings, preview applications, or the legacy
blind-retrying invitation worker. Scope, secret loading, shutdown and connection
cleanup belong to the real composition root. An assembly failure after opening
a resource must close that resource there.

Each adapters entry is `AdapterBinding(value, mode, probe)`. Required names and
methods are defined in `operations.runtime.REQUIRED_ADAPTERS`: database, rls,
migrations, core_origin, identity, webauthn_uv, mail, storage, scanner, parser,
retention, journal. Journal includes `reconcile(workspace, source=None)`, as well
as `contains`, `suppresses`, `record`. Optional `typeform_intake` requires
`receive_typeform`. Production requires `mode="live"` for every binding. Explicit
`synthetic_staging=true` accepts only synthetic bindings, never real sending mail.

`probe()` returns `ProbeResult(healthy, checked_at, generation, config_sha256)`.
Use bounded background observations no older than 30 seconds. A boolean, file
flag, stale success, exception or missing adapter cannot make readiness green.
Python cannot prove adapter authenticity; reviewed composition code and actual
integration tests are mandatory. Do not refresh a timestamp without a new check.

`restore_provider()` returns `RestoreState(generation, session_generation,
journal_head, replayed_through, verified_at, objects_verified,
source_tombstones_reconciled)`. The last field defaults to false. See RUNBOOK.md:
counts invented from `contains(workspace)` are not a journal watermark, and
source-only partial tombstones must be inventoried and reconciled. A durable,
independent inventory/watermark collector is still required.

`GuardedApplication` admits a server webhook only at exact POST
`/api/intake/typeform`, with no query, no Origin and no Sec-Fetch-* headers, and
only with a bound signature-verifying handler and healthy probe. The handler
must verify the original bytes/signature. GET callback state/code/nonce checks
remain inside the coordinator's callback. There is no blanket API exception,
CORS allowance, shared marketing cookie domain, or readiness bypass.

## Configuration And Migrations

`OperationsConfig.from_mapping` rejects extra fields and locks environment,
HTTPS host, Paris region/zone, private/Paris database destination, runtime role,
EU R2 endpoint, separate bucket names, fixed policy, and external generation.
Examples are intentionally invalid placeholders. Configuration contains mounted
secret **paths**, never credentials. `config.fingerprint` binds evidence to it.

`PooledDatabase(config.database)` implements core `transaction(workspace_id)`;
max 1-8 connections, bounded checkout, TLS verify-full, statement/lock timeouts,
startup RLS/role checks, rollback and DISCARD ALL between leases. Construct after
fork; drain before `close()`. Unknown commits are never retried or compensated by
deleting remote objects. An outage still requires application-level deadlines.

`load_plan(root)` is baseline plus sorted core migrations only.
`load_pilot_plan(root, staff_runtime_role="review_runtime",
include_providers=False)` reads original SQL in place: baseline, sorted core
migrations, intake-schema.sql, staff/schema.sql, optionally providers/schema.sql.
It assembles grants last and checksums the rendered staff-role selection and
mandatory core/staff erasure grants. Staff erasure grants target the dedicated
`review_erasure` role, never the API role. Core numbering must stay below 8000; extension anchors
are immutable. Later core migrations can append after anchors were applied.
The optional provider schema does **not** enable Too Lost. Its SQL is not included
in the default image; extending the image allowlist requires review.

Both production migration commands always use the full pilot plan:

```sh
python -m services.catalog_review.operations migration-plan --config /run/config/operations.json
python -m services.catalog_review.operations migrate --config /run/config/operations.json --expected-plan-sha256 APPROVED_SHA256 --migration-passfile /run/secrets/migration-pgpass
```

The second command is a separate approved job, not API startup. Roles/database
must already exist. `review_migration` owns schema but must not be superuser or
BYPASSRLS. `review_runtime` must not own tenant tables or manage roles/databases.
`review_erasure` is mandatory: LOGIN, NOINHERIT, NOSUPERUSER, NOBYPASSRLS,
NOCREATEROLE, NOCREATEDB, no role membership. Its credential is never mounted in
API/scan-worker containers. Grants remain tenant RLS scoped except explicitly
trusted global intake indexes. Separate staff role is optional, not the default.

The runner validates approved digest before connecting, locks the migration job,
checks ledger drift, and applies pending SQL/grants in one transaction. SQL is
trusted release code, not a sandbox; no explicit commits or nontransactional
side effects. Do not adopt a pre-existing untracked schema by editing the ledger.
After uncertain commit, inspect durable ledger with an operator before retrying.

## Recipes And Verification

API and parser target CPython 3.13.13, Linux amd64; staff/local operations tests
use an isolated Python 3.12 environment. On an arm64 workstation the production
recipes require amd64 emulation. PostgreSQL 17 smoke uses the cached native arm64
image. Do not represent either as a native arm64 production image build.

Dependencies have exact transitive pins and SHA256 hashes. Parser versions match
`parser_process.PARSER_DEPENDENCIES`; JWT/WebAuthn/HTTPX pins match staff. The
reviewed wheelhouse is an explicit named build context, mounted read-only during
installation with `--no-index --require-hashes --only-binary=:all:`. Compose sets
build network none and pull policy never. Cached base images and complete wheels
are prerequisites; BuildKit base resolution may still require registry metadata
unless the digest is available locally. No automatic downloads are permitted for
the offline check. Missing cache means blocked, not a successful build.

Dockerfile-specific deny-by-default context allowlists exclude tests, fixtures,
simulators, secrets and the repository at large. The preview stylesheet is the
only preview asset copied. No entire repository is mounted into a container.

`compose.api.yaml` requires an explicitly approved profile; its default bootstrap
is closed. `compose.worker.yaml` deliberately exits until a reviewed real job
entrypoint is supplied. Parser and ClamAV have network_mode none and Unix sockets;
the networked DB/R2 worker is a different container. Signature updates use their
own networked process with no document, socket or credential access. Volume
ownership, daemon startup, stale signatures and real socket permissions still
need image-level verification. No ClamAV daemon was installed or started here.

Read-only checks (no containers started):

```sh
docker compose -f services/catalog_review/deployment/compose.api.yaml --profile approved-api config --no-interpolate
docker compose -f services/catalog_review/deployment/compose.worker.yaml --profile approved-worker --profile approved-signature-updates config --no-interpolate
python -m pytest -q tests/catalog_review/test_operations*.py
REVIEW_RUN_PG17_SMOKE=1 python -m pytest -q tests/catalog_review/test_operations_pg17.py
```

The opt-in PG17 test never pulls: it runs only cached postgres:17, temporary data,
synthetic roles, loopback-only host publication, no repository/customer mounts,
and removes its own container/volumes. It applies the full pilot plan, reruns the
checksum ledger, verifies extension grants, tenant RLS, inserts, pool cleanup and
rollback. Existing core-fixture tests remain native PostgreSQL 14, not 17.

## Verification Checkpoint And Owned Files

2026-09-18: **215 owned tests passed**, with the PG17 opt-in enabled, in
`/private/tmp/space-catalog-operations-venv` (Python 3.12). Native fixture:
PostgreSQL 14.18; Docker smoke: PostgreSQL 17.9 arm64. Ruff checks passed. Both
Compose configurations rendered successfully. Temporary PG17 containers were
removed. No vendor calls, procurement or production deployment occurred.
Packaging checks cover every ASSETS resource, the production HTML variant,
repository-local Python imports/glue, and all default pilot SQL inputs. PG17 also
verifies staff erasure grants and the real assignment-erasure participant.

Production image builds and the full production lock installation remain
unverified: pinned Python/ClamAV base images and boto3 1.43.97 are not in the
offline cache. No image pull or ClamAV daemon startup was performed. The isolated
test environment is not represented as a complete production-lock environment.

Only these new files were written by the operations task:

```text
services/catalog_review/operations/
  __init__.py __main__.py asgi.py bootstrap.py config.py gates.py
  migrations.py pool.py runtime.py
services/catalog_review/deployment/
  Dockerfile.api Dockerfile.api.dockerignore
  Dockerfile.parser Dockerfile.parser.dockerignore
  Dockerfile.scanner Dockerfile.scanner.dockerignore
  requirements-api.lock requirements-parser.lock
  compose.api.yaml compose.worker.yaml clamd.conf freshclam.conf
  production.example.json staging.example.json launch-manifest.example.json
  runtime-policy.json README.md RUNBOOK.md COST-CHECKLIST.md
  REMAINING-INTEGRATION.md
tests/catalog_review/
  test_operations_bootstrap.py test_operations_config.py
  test_operations_database.py test_operations_deployment.py
  test_operations_gates.py test_operations_pg17.py test_operations_runtime.py
```

## Source References

- https://www.postgresql.org/docs/current/libpq-ssl.html
- https://www.postgresql.org/docs/current/sql-discard.html
- https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS
- https://www.psycopg.org/docs/pool.html
- https://docs.docker.com/build/building/best-practices/
- https://docs.docker.com/compose/compose-file/05-services/#network_mode
- https://pip.pypa.io/en/stable/topics/secure-installs/
