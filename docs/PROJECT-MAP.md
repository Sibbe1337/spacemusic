# Project map

Inspected 2026-09-28. This maps local files and recorded status, not a live
cloud-resource inventory or an approval to launch a product.

## Active work

| Directory | Responsibility | Start here |
| --- | --- | --- |
| `marketing/` | Website source layers, content, release manifests, SEO evidence and intake notification Worker | [Release record](../marketing/RELEASE.md) |
| `scripts/` | Website builders, preservation checks and project maintenance | [Command index](../scripts/README.md) |
| `services/catalog_review/` | Private portal API, intake, identity, documents, erasure, optional provider and dealflow code | [Portal guide](../services/catalog_review/README.md) |
| `services/catalog_review_ui/` | Customer/reviewer/staff UI assets and tests | [UI guide](../services/catalog_review_ui/README.md) |
| `tests/catalog_review/` | Synthetic database, authorization and lifecycle regression tests | [Verification](../services/catalog_review/PILOT-VERIFICATION.md) |
| `docs/` | Product decisions, operating boundaries and historical documentation | [Document index](README.md) |

Catalog Review's `deployment/` and `operations/` contain guarded pilot deployment
recipes. They are different from the root Docker Compose and older Helm setup.
Deployment/config examples do not mean production invitations are enabled.

## Previews and experiments

| Directory | Purpose | Boundary |
| --- | --- | --- |
| `apps/chatgpt-space/` | ChatGPT MCP app and local widget preview | Fictional fixtures only; no portal connection or deployment. [Guide](../apps/chatgpt-space/README.md) |
| `experiments/dealflow-preview/` | Interactive brokerage preparation with a disposable test database | Local loopback only, fictional records |
| `experiments/jev-catalog-review/` | Offline/synthetic model evaluation | Default offline; live synthetic requests require explicit opt-in |
| `experiments/reviewer-workspace-preview/` | Separate reviewer UI design prototype | Not the deployed authenticated portal |
| `services/catalog_review_cloud_preview/` | Isolated Railway/Vercel read-only preview | No real authentication, uploads, mail or customer database |
| `services/catalog_review_preview/` | Original synthetic catalog-review prototype | Some assets remain shared by portal packaging; do not remove |

The [experiments index](../experiments/README.md) links their individual guides.
Preview role switches, simulated records and test credentials must never become
production login mechanisms.

## Older, still referenced

| Directory/files | Why retained |
| --- | --- |
| `services/spacemusic/`, `services/seller_ui/` | Earlier seller/valuation flow; existing API/UI tests and Compose references. Website scripts also import seller UI's installed tooling. |
| `services/admin_ui/` | Separate older admin app with uncommitted work, CI and tests |
| `services/offers/`, `services/payouts/`, `services/valuation/`, `services/docgen/`, `services/event_consumer/`, `services/api_gateway/` | Earlier distributed architecture; imported by tests and referenced by Compose/Helm |
| `libs/`, `schema/`, `fixtures/` | Shared modules, event schemas and fixtures; not interchangeable with customer data |
| `infra/`, root `docker-compose.yml` | Earlier service infrastructure; not the current portal pilot deployment |
| `.github/workflows/ci.yml` | Existing older-stack CI; not proof that the portal production gates passed |
| `package.json`, `package-lock.json` | Existing root dependencies plus convenience commands; no dependency removal in this cleanup |
| `web/` | Unpopulated Git link; not a website release source |

Retained means **not proven unused**, not endorsed for production. Deleting a
service requires checking runtime imports, tests, build contexts, CI and restore
procedures together. A service's age is insufficient evidence.

## Local artifacts and evidence

- `tmp/`: complete website snapshots, preserved predecessors, QA files and
  tool environments. Production and rollback paths are in `marketing/RELEASE.md`.
  Regression manifests reference older snapshots too. This directory is not
  globally ignored or included in the cache cleaner.
- `output/`, `.playwright-mcp/`, root screenshots and `design-qa.md`: local
  deliverables and review evidence. Retain them unless their owner approves
  archiving; a screenshot is not automatically disposable.
- `competitor-profiles/` and dated `marketing/` directories: research and release
  history. A dated filename does not establish that the material is unused.
- `node_modules/`: dependencies, not source. Some website checks use tooling
  installed in `services/seller_ui/node_modules`; do not prune it in a general
  cleanup.
- `.wrangler/`, `.vercel/`, `.railway/`: local provider state. Ignored but left
  intact; never print credentials or upload these with a source bundle.
- `private/`: excluded customer/operator material, outside cleanup traversal.
- `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`: the only cleanup categories
  enabled by `npm run clean:caches`, subject to content and tracking checks.

The project checker reports missing local release artifacts rather than fetching
or rebuilding them. A fresh clone may lack those artifacts until a verified
snapshot is restored; it must not silently deploy another build instead.
