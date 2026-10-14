# SpaceMusic seller platform

## Approved-flow integration (local only, September 10)

The approved seller journey now has a separate integration foundation in
`services/spacemusic/portal/`. Run `python3 -m services.spacemusic.portal.app --local`
and open `http://127.0.0.1:4194/`. It uses example.com identities, a local test
mailbox, expiring single-use sign-in links, HttpOnly sessions, private local
evidence, authenticated ownership checks and persisted clarification messages.

This entrypoint does not mount the legacy API below, enable automatic valuations
or expose payouts. Production startup is intentionally blocked until managed
storage, mail delivery, malware scanning and real reviewer access are integrated.
The existing public Formspree Apply form and all marketing SEO files remain
unchanged. See `services/spacemusic/portal/README.md` for tests, limitations and
the launch checklist. The purely visual prototype remains separately in
`marketing/seller-journey-preview/`.

## Local flow

The seller vertical slice is served by `services.spacemusic.main:app`.

1. `POST /seller/applications` creates an application and returns a one-time seller token.
2. `PUT /seller/applications/{id}/passport` stores a versioned Catalog Passport.
3. `POST /seller/applications/{id}/documents` creates a one-time upload URL. The upload is stored privately and becomes `UPLOADED`.
4. An authenticated internal reviewer calls `POST /internal/applications/{id}/documents/{document_id}/review` and chooses `VERIFIED` or `REJECTED`.
5. `POST /seller/applications/{id}/valuation` accepts explicit, versioned benchmark assumptions and creates 50%, 75%, and 100% scenarios.
6. A scenario with no unresolved review flags can be accepted. A flagged valuation remains `UNDER_REVIEW` until an internal reviewer changes the status to `OFFER_READY`.
7. `POST /seller/applications/{id}/payout` requires `Idempotency-Key` and uses the test adapter when `SPACE_PAYOUT_MODE=test`.
8. A successful test payout creates one durable ledger entry and a versioned receipt PDF. The seller can access the receipt through a short-lived signed URL.
9. `POST` and `GET /seller/applications/{id}/royalty-reports` support annual or periodic seller reporting after closing.

The separate seller UI lives in `services/seller_ui`. Run it with `npm install && npm run dev`; set `VITE_SPACEMUSIC_API_URL` to the API origin. Benchmark variables (`VITE_BENCHMARK_VERSION`, `VITE_BENCHMARK_LOW`, `VITE_BENCHMARK_MEDIAN`, and `VITE_BENCHMARK_HIGH`) are intentionally unset by default. An operator must provide reviewed assumptions before the seller can request valuation from the UI.

The public application status state machine is:

`SUBMITTED -> DATA_REQUIRED -> UNDER_REVIEW -> OFFER_READY -> ACCEPTED -> PAID`

Rejection is terminal. Status transitions are validated in the store rather than accepted as arbitrary strings.

## Authentication and storage

Seller tokens are returned once and only their HMAC digest is stored. Upload tokens are single-use. Download tokens are signed with an expiry and never expose a filesystem path. Internal routes require `SPACEMUSIC_INTERNAL_TOKEN` and return `503` when the secret is not configured.

SQLite and local files are development adapters. Production requires an encrypted managed database, private object storage, secret management, malware/content scanning, backup policy, access logs, and a reviewed deletion/retention process.

When the offers service is deployed with more than one instance, set `OFFERS_SSE_REDIS_URL` to the shared Redis instance. Without it, SSE is explicitly a single-instance development fallback.

## Admin compatibility

`GET /internal/applications` and `GET /internal/deals` return the same underlying seller applications. The latter also includes a compact `deals` projection for the existing admin UI. The admin UI remains a separate surface from the seller portal.
