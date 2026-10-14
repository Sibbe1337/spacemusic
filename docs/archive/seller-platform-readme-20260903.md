# SpaceMusic

> Historical seller-platform description, archived 2026-09-28. This is not
> the current portal or release guide. Paths below refer to the repository root.
> Start with the [current project guide](../../README.md).

SpaceMusic is a seller-first platform for reviewing and acquiring royalty-generating music catalogs in ambient, sleep, focus, meditation, wellness, lo-fi, and instrumental electronic categories.

The repository now contains a working seller vertical slice: application, Catalog Passport, evidence upload and review, transparent valuation v0, 50/75/100% scenarios, acceptance, test payout, ledger, receipt, partner attribution, and seller reporting.

## Run the seller API locally

From the repository root:

    python3 -m pip install -r requirements-dev.txt
    python3 -m pip install -r services/spacemusic/requirements.txt
    SPACEMUSIC_DB_PATH=/tmp/spacemusic.db SPACE_PAYOUT_MODE=test uvicorn services.spacemusic.main:app --reload --port 8005

Run the seller UI separately with `cd services/seller_ui && npm install && VITE_SPACEMUSIC_API_URL=http://127.0.0.1:8005 npm run dev`. A Docker Compose development stack is also provided for the API and UI.

The local adapter stores the SQLite database at `SPACEMUSIC_DB_PATH` and private document files at `SPACEMUSIC_DOCUMENT_DIR`. Set `SPACEMUSIC_INTERNAL_TOKEN` before using internal admin/review routes.

## Product boundaries

Valuation uses seller-supplied, verified royalty and rights evidence plus an explicit versioned benchmark request. It does not use Spotify or streaming-platform audience APIs. No real payment is made in test mode; live mode fails closed until a reviewed provider adapter is supplied.

Read the implementation details in `docs/seller-platform.md`, `docs/valuation-policy.md`, and `docs/compliance.md`.

## Tests

    python3 -m pytest -q

The test suite covers domain valuation, rights/risk flags, seller flow, document review, payout idempotency, ledger behavior, receipt generation, API auth, event-boundary serialization, and legacy service compatibility.

## Existing services

The repository retains the existing offers, payouts, docgen, event-consumer, infrastructure, and admin UI surfaces. The admin UI remains separate from the seller API. Its in-progress user changes are intentionally preserved.
