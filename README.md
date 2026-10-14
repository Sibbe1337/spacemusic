# SPACE Music

Website, private catalog-review portal and isolated research previews.
This is a multi-part repository, not one application that can be deployed from
the root. Read the relevant component's guide before running or publishing it.

## Start here

| What you want to work on | Entry point | Status |
| --- | --- | --- |
| Public website, content, SEO and Apply | [Marketing release](marketing/RELEASE.md) | Published website; release approval is separate from portal work |
| Customer documents, staff review and intake | [Catalog Review](services/catalog_review/README.md) | Implemented pilot code; customer launch remains gated |
| Customer and reviewer interface | [Portal UI](services/catalog_review_ui/README.md) | Same-origin interface for Catalog Review |
| Seller-approved brokerage preparation | [Dealflow preview](experiments/dealflow-preview/README.md) | Local fictional-data demo; sharing and payment disabled |
| Hosted Railway/Vercel design preview | [Cloud preview](services/catalog_review_cloud_preview/README.md) | Read-only synthetic preview, not a customer backend |
| Jev research | [Evaluation lab](experiments/jev-catalog-review/README.md) | Synthetic-only; no customer-data integration |

For all other directories, see the [project map](docs/PROJECT-MAP.md).
For business and operations documents, see the [documentation index](docs/README.md).

## Important boundaries

- `marketing/RELEASE.md` identifies the recorded website release, rollback and
  unapproved candidate. It is not a fresh observation of the live site.
- **`tmp/` contains irreplaceable local release snapshots and regression inputs.**
  Do not delete it, even though its name suggests temporary files.
- `web/` is an unpopulated Git link, not the current website build. Do not
  substitute an unrelated frontend for the published static artifact.
- Catalog Review, the older seller application and design previews are distinct.
  The root Docker Compose stack is for the older services, not the portal pilot.
- Do not deploy the repository root. Use a component's explicit build allowlist.
- Never commit customer files, database copies, credentials or vendor-local state.
  `private/` is excluded from Git; ignore rules are not an access-control system.
- Existing uncommitted work is not backed up by Git. A cleanup is not permission
  to discard it, publish it or remove migrations, release assets or test fixtures.

## Everyday commands

Run from the repository root. These commands do not deploy anything or send leads.
Node 22+ is used for the JavaScript tooling. Python/DB test setup is documented in
the [portal verification guide](services/catalog_review/PILOT-VERIFICATION.md).

```sh
npm run project:check       # Verify important local entry points and release files
npm run clean:check         # List strictly allowlisted disposable caches; no deletion
npm run clean:caches        # Remove only those caches, never tmp/ or node_modules/
npm run test:maintenance    # Verify cleanup safety and project documentation
npm run test:funnel         # Calculator, attribution and intake mock-response tests
npm run test:portal:ui      # Portal interface tests; optional browser gates remain
npm run preview:dealflow    # Local synthetic preview at http://127.0.0.1:4208/
```

Portal backend tests: `python3 -m pytest tests/catalog_review -q` in the configured
portal test environment. A host-only run does not replace Linux scanner/parser,
PostgreSQL 17, image-build or actual provider/restore checks.

For website preservation tests and component dependencies, see the
[script index](scripts/README.md). Do not install or run the older entire stack
just to work on website copy or the portal interface.

## What is retained, not active scope

The older seller/valuation/payout stack remains in `services/`, `libs/`, `schema/`
and `infra/` because its code, CI and tests still reference it. It is not the
current document-pilot architecture and is not safe to delete by age alone.
Original plans are preserved in the [historical archive](docs/archive/README.md),
clearly separated from current instructions.

See [cleanup scope and verification](docs/maintenance/20260928-cleanup.md) for
what changed and what deliberately did not.
