# Compliance checklist

This repository implements technical controls and does not determine SpaceMusic's legal obligations.

## Implemented technical controls

- Separate seller-token and internal-token access boundaries
- HMAC-hashed bearer tokens rather than raw token persistence
- Single-use upload tokens and signed, expiring document/receipt links
- SHA-256 and size checks for uploaded documents
- Document versions and review status
- Status transition validation
- Audit events for application, passport, document, offer, payout, and redaction actions
- Idempotency-key uniqueness for payout intents and one ledger entry per intent
- Test payout adapter with live mode failing closed
- Personal-data redaction operation for an internal retention/deletion workflow

## Must be decided outside this code

- Whether a transaction is an acquisition, financing, licence, or another regulated activity
- Rights-transfer language, warranties, indemnities, and seller disclosures
- EU copyright transparency and remuneration obligations
- KYC/AML, sanctions screening, payment-service licensing, and tax reporting
- International territory and withholding-tax treatment
- Data retention periods, lawful basis, processor agreements, data-subject workflows, and incident response
- Production provider contracts and security review for object storage, email, payments, and document scanning

Do not enable live payouts until those decisions and the production adapter have been separately reviewed and tested.
