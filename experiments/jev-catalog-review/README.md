# SPACE Jev evaluation lab

Isolated synthetic-only experiment, 24 September 2026. No production integration,
deployment, customer data, database, portal imports, new dependency or paid plan.
Node 22+ and the standard library only. This directory is outside the portal's
explicit production image COPY list and is not imported by the website or portal.

## Question being tested

Can Jev improve intake/document classification and draft follow-up checklists
relative to simple lexical rules and an ordinary language model?

The 20 fictional cases contain 80 labelled decisions: seller/buyer/broker/partner
intent, offered/sought rights, transaction scope and document type. They include
negation, contradictory intent, unreadable material, a document prompt-injection,
overlapping statements, unspecified currency/basis, non-earnings audience data,
and one Swedish and one Spanish example. No real leads were copied or anonymized
to make these cases. The small multilingual sample is a smoke test only.

Reference labels are author-created development expectations, not independently
adjudicated or held out. The rules baseline is intentionally elementary and
English-focused; beating it is not evidence of beating a production classifier.
Do not tune prompts on these cases and report the resulting score as generalization.

## Run locally

From the repository root:

```sh
node --test experiments/jev-catalog-review/evaluation.test.mjs
node experiments/jev-catalog-review/run.mjs
```

The default is entirely offline, even when credentials are configured. Reports
include all models' availability, but there is no fake Jev or LLM benchmark lane.
Protocol simulations appear in unit tests only, never in reported model accuracy.

## Configure Jev without exposing a secret

Run this in an interactive terminal; input is hidden and never placed in a command
argument, shell history, report, source file or chat:

```sh
node /Users/emilsoujeh/spacemusic/experiments/jev-catalog-review/secrets.mjs
```

The helper writes an owner-only (0600) file in an owner-only (0700) directory:
`~/Library/Application Support/SpaceMusic/jev-evaluation/typesafe-api-key`.
It refuses to overwrite an existing file. This is local file protection, not an
encrypted vault. A process running as the same user can read it. Do not commit,
share or include it in a deployment. Rotation is manual and should revoke the old
key at TypeSafe first. The lab can also read `TYPESAFE_API_KEY` from its process
environment, but never discovers or loads `.env` files.

The comparator reads only `OPENAI_API_KEY` from its process environment. It does
not reuse Codex account credentials, other application keys or browser sessions.

## Live synthetic evaluation (explicit opt-in)

```sh
node experiments/jev-catalog-review/run.mjs --provider jev --live-synthetic --repeats 3
node experiments/jev-catalog-review/run.mjs --provider llm --live-synthetic --repeats 3
node experiments/jev-catalog-review/run.mjs --provider all --live-synthetic
```

Each individual-provider run permits 1-3 repeats, at most 60 remote attempts.
`all` permits one repeat and interleaves available providers by case, reversing
their order on alternate cases. Missing keys remain explicitly unmeasured.
Run comparisons near each other and keep runtime, corpus and prompt hashes equal.
Do not compare cached/offline timings with remote timings as a model speedup.

Only this reviewed, hash-pinned corpus is accepted; the CLI has no file, URL,
database or free-text input option. Each request strips reference labels, tags and
critical-document annotations. Edited corpus files fail closed until reviewed and
the SHA-256 is deliberately updated. This prevents accidental live-data input;
it is not a security boundary against someone modifying the lab source itself.

Exact fixed HTTPS origins, pinned model versions, one simultaneous request,
24,000-byte request cap, 256,000-byte response cap, 15-second request deadline,
redirect rejection, and no automatic retries apply. A provider's first error stops
its run, including subsequent repeats. An uncertain timeout may still be billed.
These bounds limit traffic, not a supplier-guaranteed monetary ceiling.

## Comparison contract

- Jev: native Choice questions, pinned `jev-1.13.0`; validates model, question IDs,
  all option probabilities, probability sums, chosen maximum, finite confidence
  and usage. Missing/invalid responses are failures, not repaired answers.
- LLM: `gpt-4.1-mini-2025-04-14`, temperature 0, strict JSON labels, same input and
  rubrics, max 2048 completion tokens, store false. Refusal/truncation/schema drift
  are failures. No invented probability or confidence is compared with Jev.
- Rules: transparent, deliberately simple lexical baseline without model calls.
- Every model result is a reviewer draft, never an automatic customer action.
  Presence/type classification does not authenticate a document or prove ownership.

Reports are checkpointed after each result into a new private `results/<run-id>/`
directory (ignored by Git). Previous runs are not overwritten. Reports retain
labels, model version, aggregate tokens, timings, safe errors, draft questions,
source IDs, corpus/request hashes and reference mismatches, not raw provider bodies
or keys. The corpus is synthetic and contains no operational customer information.

Accuracy counts failed and unrun decisions in the denominator; also inspect the
completion count, field/language breakdown, missing/extra checklist questions and
individual disagreements. p50/p95 cover successful calls only; attempt duration
and failures are separate. Do not call these figures full product latency.
The diagnostic Jev confidence threshold (0.9) is uncalibrated for this task and
never permits automatic action. Human review-time savings are unmeasured.

Jev cost is estimated from reported input tokens at USD 0.042/million; output is
free according to vendor docs checked 2026-09-24. No fee claim is made for LLM
usage until current account pricing is verified. A run with failed calls has
unknown complete cost. Rules have no API charge but still require compute and
maintenance. Cost savings cannot be claimed without comparable measured runs.

## Safety boundaries and go/no-go

All supplied documents remain in every review bundle, even if the model says
irrelevant/unknown. This tests deterministic retention, not legal risk detection.
Unknown currency, period, gross/net semantics and overlapping exports are not
resolved or totalled. No financial conclusion is permitted, even for a perfect
classification score. There is no buyer sharing, valuation or customer rejection.

Document ranking/context compression and buyer matching are deferred. This lab
has no real tenant authorization; it must never be mounted as a portal endpoint.
Any future integration must authorize the current case BEFORE retrieval/model
evaluation and recheck deletion/revocation, retain required adverse evidence, and
have a working manual fallback. A classifier is not an access-control mechanism.

Before a real-data trial, require independent music-rights review of reference
labels, a broader held-out multilingual set, explicit handling of high-confidence
errors, paired real workflow-time measurements, and operator approval. No small
synthetic score proves safety. Also resolve provider DPA, processing location,
subprocessors, retention/backups, permitted use and deletion obligations.

TypeSafe's published privacy policy says hosting/processing in the US. Its DPA
includes international-transfer provisions, not an EU-only guarantee. The portal's
EU-only decision is unchanged. No live customer data may be submitted to this lab.
The document pilot must remain independent of Jev availability.

## Sources checked 2026-09-24

- https://docs.typesafe.ai/api
- https://docs.typesafe.ai/models
- https://docs.typesafe.ai/confidence
- https://docs.typesafe.ai/model-jaggedness/jev-1.13
- https://typesafe.ai/blog/introducing-system-one-models-and-jev
- https://typesafe.ai/legal/privacy-policy
- https://typesafe.ai/legal/data-processing
- https://typesafe.ai/legal/mca
- https://developers.openai.com/api/docs/guides/structured-outputs

Vendor performance multipliers are not SPACE results. No API exchange, accuracy,
speedup or cost benefit is claimed until an actual live report records it.
