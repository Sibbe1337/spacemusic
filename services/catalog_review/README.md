# SPACE Catalog Review

Private catalog-document review, not the public marketing website or the older
seller/valuation/payout application. Customer production remains gated; synthetic
tests and preview hosting are not approval to accept real customer documents.

## Start here

- [Pilot verification](PILOT-VERIFICATION.md): implemented scope, recorded tests
  and known operational gaps.
- [Operating decisions](PILOT-OPERATIONS.md): identity, private storage,
  inactivity/erasure and manually admitted pilot customers.
- [Deployment and operations](deployment/README.md): allowlisted containers,
  migration roles and fail-closed launch/restore gates.
- [Remaining integration](deployment/REMAINING-INTEGRATION.md): what still needs
  to be connected and verified before production.
- [Customer/reviewer UI](../catalog_review_ui/README.md): same-origin interface.
- [Dealflow demo](../../experiments/dealflow-preview/README.md): newest local
  fictional-data workflow and its September 25 verification record.

## Module map

| Area | Files/directories |
| --- | --- |
| Domain and request boundaries | `service.py`, `http.py`, `contracts.py`, `security.py`, `access.py` |
| Case state, intake and review | `database.py`, `intake.py`, `intake_http.py`, `review.py` |
| Document handling | `storage.py`, `scanner.py`, `document_validation.py`, `parser_process.py`, `parser_ipc.py` |
| Lifecycle and communications | `lifecycle.py`, `erasure.py`, `mail.py`, `jobs.py`, `workers.py` |
| Staff identity and assignment | `staff/` |
| Optional read-only provider adapter | `providers/`; separate activation gates |
| Optional brokerage preparation | `dealflow.py`, `dealflow_contracts.py`, `dealflow_policy.py`; disabled by default |
| Runtime and deployment | `runtime.py`, `operations/`, `deployment/` |
| Database history and permissions | `schema.sql`, `migrations/`, subsystem schemas and grants |

Migrations and erasure grants are not disposable historical files. Do not remove
them, merge them into a new baseline or enable optional features during cleanup.

## Local checks

From the repository root in the configured portal test environment:

```sh
python3 -m pytest tests/catalog_review -q
node --test services/catalog_review_ui/*.test.mjs
node --test services/catalog_review_preview/*.test.mjs
npm run test:funnel
```

Tests use disposable PostgreSQL fixtures, not the real customer database.
Read the verification guide for dependency/host prerequisites and optional
Linux, PostgreSQL 17 and browser tests. A skipped test is not a passed gate.
No production migration or vendor setup runs as part of these commands.

Use the local dealflow harness for interactive fictional-data testing or the
[isolated cloud preview](../catalog_review_cloud_preview/README.md) for read-only
design review. Neither replaces the production authentication/operating model.

## History

The [original foundation README](HISTORICAL-FOUNDATION.md), [early QA](QA.md)
and [phase 2B QA](QA-2B.md) are retained as historical checkpoints. Current launch
decisions belong to the pilot guides above, not older statements that a module
was still missing at a previous milestone.
