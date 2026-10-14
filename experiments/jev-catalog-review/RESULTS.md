# SPACE Jev experiment: measured checkpoint

24 September 2026. **Continue evaluation; do not enable customer-data processing.**

## What actually ran

Jev `jev-1.13.0` was called through TypeSafe's real API. Twenty synthetic catalog
cases were evaluated three times with unchanged prompts and reference labels:
60 requests, 240 repeated classifications, but only 20 unique cases. This is a
small development smoke test, not 240 independent observations or a production
accuracy estimate. No customer email, contract, statement, name or API token was
included in model input.

| Run | Reference-label agreement | Median API latency | p95 API latency | Estimated API fee |
| --- | --- | --- | --- | --- |
| Simple lexical rules, offline | 65/80 | Not comparable with remote inference | Not comparable | USD 0 API fee |
| Jev, first run | 79/80 | 255.84 ms | 447.39 ms | USD 0.001013922 |
| Jev, repeat 2 | 78/80 | 248.17 ms | 297.38 ms | USD 0.001013922 |
| Jev, repeat 3 | 78/80 | 250.63 ms | 304.26 ms | USD 0.001013922 |
| Ordinary LLM | Not run; no configured comparator API key | Not measured | Not measured | Unknown |

Every Jev run completed 20/20 requests. Estimated combined Jev fee: **USD
0.003041766**, based on 72,423 reported input tokens at the vendor's published
USD 0.042/million rate. This excludes development, hosting, document ingestion,
review time and any account-specific charges; it is not an invoice. No LLM
cost-saving or speedup multiplier has been measured.

## Important disagreements

**s11, contradictory seller intent:** Jev returned unknown role instead of the
author's seller reference in all three runs, at confidence 0.75-0.77. An
independent code/rubric reviewer found both readings defensible: the global
instructions tell the model to use unknown for unresolved contradictions, while
the reference assumes seller intent survives a contradiction about rights.
The original labels and denominator remain unchanged. This is a rubric ambiguity,
not a demonstrated model error. It also changes the generated draft checklist:
five seller-specific questions are replaced by one intent-clarification question.
Those counts do not establish that Jev caused five unsafe omissions.

**s13, Spanish sale scope:** the text offers all publishing rights while retaining
masters. Jev selected full in the first run, but partial in both repeat runs,
with low confidence (0.31 and 0.40). This is a concrete instability that makes
automatic routing or customer messaging inappropriate. One Spanish and one
Swedish case cannot establish multilingual reliability.

All 20 document-type classifications matched references on every run. This says
nothing about authenticity, complete chain of title or accuracy of financial
statements. A scanned file would still require the existing bounded document
processing pipeline; the test used short synthetic text, not PDFs or spreadsheets.

## Product decision

- A reviewer-only intake/document sorting assistant is worth testing further.
- Retain all original documents and keep unclear or low-confidence fields visible
  to the reviewer. No model-based evidence deletion or automatic rejection.
- Keep numerical reconciliation, currency/period checks and duplicate-source
  handling in deterministic code. No valuation or ownership verification here.
- Clarify the next rubric version, obtain independently reviewed labels, and add
  fresh held-out multilingual/adversarial examples before claiming quality gains.
- Run the ordinary LLM comparator on the same versioned cases once its separate
  credentials and account pricing are available. Do not substitute fabricated
  model results or reuse unrelated application credentials.
- Measure actual review time and useful follow-ups before connecting anything
  to the portal. No financial return or conversion improvement was measured.

TypeSafe's published policy describes US hosting/processing. A DPA exists but
does not establish an EU-only deployment. The approved portal residency decision
is unchanged; genuine customer processing remains blocked pending an approved
provider/residency/retention arrangement and separate integration approval.

## Verification and preservation

- 54 experiment tests passed, including native response validation, secret
  redaction, pinned synthetic input, call limits, no automatic retries, malformed
  responses, private key permissions and retained critical documents.
- 30 existing funnel/Typeform/cloud-preview test entries passed, including the
  local browser preview check. The scenario entry also runs its internal checks.
- Marketing and portal source hashes match their pre-experiment values. No
  production deployment, route, schema, sitemap, Apply receiver or customer UI
  was changed. Existing preview tests regenerated local ignored build artifacts.
- The repository-wide whitespace check reports pre-existing issues in unrelated
  admin UI files. They were not modified as part of this work.
- Independent review found and prompted fixes for an exported-runner corpus
  bypass, upstream usage metadata passthrough and ambiguous latency reporting.
  Regression tests cover those fixes. Re-review confirmed all three resolved and
  reported no remaining concrete P1/P2 findings in the checked scope. This is not
  a full production security audit.

## Reproducible evidence

- [Offline rules report](results/d3fbb0ec-8c9c-461b-99e6-28de3ec268c4/REPORT.md)
- [First live Jev report](results/b641995c-6a1c-4e97-91c2-d2a1b81c28e5/REPORT.md)
- [Two repeat runs](results/949be298-9b6b-4f88-84fc-5d13f80b726a/REPORT.md)
- Each report has adjacent `results.json` with labels, native confidence, tokens,
  timings and hashes. Run folders are local, private and Git-ignored.
- Corpus SHA-256: `a5302b2919c7a1b698073564fbf7869b057f93f8c97bb170f7b8191ba868f11c`
- Prompt version: `2026-09-24-v1`. Local runtime: Node `v26.9.0`.

## First-party references

- [Jev model, limits and price](https://docs.typesafe.ai/models)
- [Known numeric, multilingual and adversarial limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- [Confidence semantics](https://docs.typesafe.ai/confidence)
- [Privacy policy](https://typesafe.ai/legal/privacy-policy)
- [Data processing agreement](https://typesafe.ai/legal/data-processing)
