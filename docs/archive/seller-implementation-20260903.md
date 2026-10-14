# SpaceMusic implementation plan

> Historical seller-platform plan, archived 2026-09-28. Do not treat the
> direct-acquisition and payout scope below as the current portal specification.
> Start with the [current project guide](../../README.md).

## Product goal

SpaceMusic acquires royalty-generating catalogs directly from owners in the ambient, sleep, focus, meditation, wellness, lo-fi, and instrumental electronic categories. The primary path is:

`application -> Catalog Passport -> evidence review -> valuation -> 50/75/100% offer -> acceptance -> payout -> receipt -> reporting`

The seller flow and transparent underwriting have priority over marketplace features and speculative audience metrics.

## Delivered vertical slices

- Seller application with consent and referral attribution
- Versioned Catalog Passport with track identifiers, rights shares, territories, sources, history, adjustments, advances, liens, metadata, and fraud status
- Private, hashed-token document upload with size/hash validation, one-time upload tokens, review status, and version history
- Reproducible valuation v0 from verified royalty evidence and operator-supplied benchmark assumptions
- Explicit 50%, 75%, and 100% sale scenarios with dates, rights, ranges, risks, exceptions, and validity
- Seller portal and separate admin compatibility endpoints
- Test-only payout adapter, idempotent payout intents, one ledger entry per successful intent, receipt hash/version, and seller reporting
- Internal reviewer token boundary, status state machine, audit trail, and redaction operation

## Next production gates

1. Replace the SQLite/local-file adapters with an encrypted managed database and private object storage with malware scanning, backups, retention jobs, and access logs.
2. Supply reviewed benchmark inputs and an operator approval workflow. No benchmark or commercial multiple is hard-coded as a market claim.
3. Complete legal, KYC/AML, tax, rights-transfer, payment-service, territory, and GDPR reviews before accepting real catalogs or enabling live payouts.
4. Implement a reviewed Stripe/Wise adapter behind `SPACE_PAYOUT_MODE=live`, including provider webhooks, reconciliation, retry policy, and secret rotation.
5. Run the seller UI and API behind the production gateway with explicit CORS origins, TLS, rate limits, WAF rules, and observability.

## Non-goals

Spotify or other streaming-platform audience APIs are not underwriting inputs. The repository does not promise a best price, investment return, legal outcome, or guaranteed payment date. The test adapter never contacts a payment provider.

## Verification

Run `python3 -m pytest -q`, `ruff check .`, and `cd services/seller_ui && npm test && npm run build`. Use the synthetic fixture only for tests and demos; it is not a market benchmark.
