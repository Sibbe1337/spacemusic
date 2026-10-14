# Valuation v0 policy

The v0 engine is an underwriting aid, not financial advice or a guaranteed price.

## Allowed inputs

- Verified royalty statements
- Distributor exports
- Publisher statements
- PRO or direct-license evidence where the seller is entitled to provide it
- Rights-chain and metadata documents
- Seller-declared ownership, territories, adjustments, advances, liens, and disputes

The engine does not use Spotify, streaming-platform audience endpoints, follower counts, derived listener metrics, or playlist metrics for valuation or commercial offers.

## Reproducibility

Every valuation request must carry an operator-supplied benchmark version and low, median, and high multiples. Those assumptions are persisted in the result; they are not hidden in code. The result records `valuation-v0.1`, confidence, explanations, risk flags, and whether manual review is required.

The repository's synthetic fixture is for tests only. It is not a market benchmark and must not be shown to sellers as a market claim.

## Review gates

Short history, declining revenue, volatility, concentrated revenue, incomplete metadata, incomplete document verification, non-clear fraud review, non-full ownership, adjustments, liens, or disputes create risk flags. A flagged result stays in `UNDER_REVIEW` until an authorised reviewer approves the application or requests more information.

The exact benchmark methodology, risk policy, legal characterization of an acquisition, tax treatment, KYC/AML scope, and cross-border terms require review by qualified legal and financial advisers before production use.
