# SPACE deal preparation preview

Local acceptance environment, 25 September 2026. Brokerage preparation first;
buyer subscriptions and contact-data resale are not implemented.

## Run

From the repository root, with the portal test dependencies and a local PostgreSQL
installation available:

```sh
python3 experiments/dealflow-preview/serve.py
```

Open `http://127.0.0.1:4208/`. The server creates a disposable database through
the existing test fixtures. Stopping it discards the synthetic case. It binds
only to loopback and rejects other Host/Origin values. Do not tunnel or deploy
this harness, enter customer material, or reuse its test identities.

## Try the workflow

1. Start as Reviewer. All six checks are initially missing. A fictional buyer
   mandate and fictional EUR receipts are supplied, not real market criteria.
2. Open each evidence check. Select Reviewed, cite `evidence.csv`, and explain
   the finding. This synthetic fixture does not establish anyone's ownership.
3. Save the version. Once the documented criteria match, select the document
   proposed for sharing and prepare a presentation.
4. Switch Demo role to Catalog owner. Read the exact presentation, check its
   recipient, limitations and document list, then approve or decline it.
5. As Reviewer, see approval recorded while delivery remains disabled.
6. As owner, revoke the approval. A new review or changed evidence also makes
   the existing presentation stale; a new presentation and approval are needed.

The Catalog workspace links intentionally show a preview-boundary page. The
normal authenticated application uses its existing workspace/conversation.
The synthetic role selector exists only here, never in production assets.

## What is real code

- `services/catalog_review/dealflow.py`: case-scoped, versioned manual reviews,
  fixed evidence policy, bounded buyer criteria, immutable packages and decisions.
- `services/catalog_review/migrations/008_dealflow.sql`: append-only, forced-RLS
  records included in case export and restricted erasure.
- `services/catalog_review_ui/dealflow.*`: normal same-origin, CSRF-protected
  reviewer/owner UI. Native controls and existing local SPACE/Inter assets.
- Feature off by default (`ReviewService(dealflow_enabled=False)`). Existing
  production composition does not enable it. Only the isolated harness opts in.

No synthetic settings should be copied to a deployed composition. A later rollout
must opt in server-side after existing launch gates are met, apply migrations
with the migration role, update narrowly scoped runtime/erasure grants, and run
authenticated staging/restore checks. Rollback disables the feature and retains
its audit records; do not delete the tables as an application rollback.

## Deliberate boundaries

No automatic valuation, royalty aggregation, FX conversion, buyer interest claim,
payment, success-fee collection, external email, document transfer, public package
link, Jev customer processing or new marketing pages. A human records source
findings; the system does not prove ownership. Buyer matches use only recorded
rights, transaction type, optional annual-net requirement/currency and freshness.
Genre, territories, proof of funds, conflicts and deal-specific terms still need
manual confirmation. A per-case mandate is not a global CRM or verified buyer list.

The growth panel is a draft worklist, not a new traffic engine or measured funnel.
See `docs/dealflow-growth-pilot-20260925.md` before proposing public changes.

## Regression commands

```sh
python3 -m pytest tests/catalog_review -q
node --test services/catalog_review_ui/*.test.mjs
```

Full tests need the staff test dependencies. Linux parser containment, actual
PG17 and two-container IPC need their own existing test environments; a macOS
test run does not replace them. No real lead or provider credentials are needed.
