# SpaceMusic release gates

> Historical seller-platform checklist, archived 2026-09-28. These are not
> the current Catalog Review launch gates. Start with the
> [current project guide](../../README.md). Paths below refer to the repository root.

This checklist reflects the current seller-acquisition implementation. It replaces
the earlier Spotify-first and provider-placeholder plan.

## Delivered

- [x] Seller application with one-time seller token
- [x] Versioned Catalog Passport with rights, territories, sources, ownership, and risk fields
- [x] Private evidence upload with size and SHA-256 validation
- [x] Internal document review and validated application status transitions
- [x] Deterministic royalty-only valuation v0 with explicit benchmark version and multiples
- [x] 50%, 75%, and 100% offer scenarios with currency, validity, rights, and exceptions
- [x] Offer acceptance, termsheet response, test payout, durable ledger entry, and receipt PDF
- [x] Idempotency conflict protection for payout amount, currency, application, and recipient reference
- [x] Seller reporting, support request, timeline, internal review, partner attribution, and redaction endpoints
- [x] Seller UI covering application through receipt and reporting
- [x] Protected internal routes, signed download links, audit events, and fail-closed live payout mode
- [x] Shared Redis fanout for multi-instance offers SSE
- [x] CI checks for backend, seller UI, and Helm charts

## Required before production

- [ ] Replace SQLite and local document files with an encrypted managed database and private object storage
- [ ] Add malware/content scanning, backups, access logging, secrets management, and tested retention/deletion workflows
- [ ] Review benchmark methodology, risk policy, acquisition/finance characterization, and seller-facing terms with legal and financial advisers
- [ ] Complete KYC/AML, sanctions, tax, withholding, copyright, privacy, and cross-border decisions
- [ ] Implement and independently review a production payout adapter; keep `SPACE_PAYOUT_MODE=test` until then
- [ ] Configure production CORS, internal secrets, email, monitoring, alerting, and incident response
- [ ] Run migration rehearsals, load tests, and a rollback exercise in the target environment

## Verification

Run from the repository root:

```text
python3 -m pytest -q
ruff check .
cd services/seller_ui && npm test -- --run && npm run build
```

The synthetic fixture in `fixtures/` is test data only. It is not a market benchmark
and must not be presented to sellers as a pricing claim.
