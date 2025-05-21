# SPACE Implementation Plan (Executable v1.0)

*Author: Platform PMO · Date: 2025‑05‑21*

---

## 0. Purpose

Det här dokumentet är den **enda sanning** som styr implementationen av SPACE‑plattformen enligt “Operation Supernova+”‑blueprinten.  Alla Jira‑epics, sprint‑mål och Go/No‑Go‑gates härleder direkt till planens artifacts.

---

## 1. Key Dates

| Milestone                       | Datum        | Gatekeeper    |
| ------------------------------- | ------------ | ------------- |
| Repo + IaC bootstrap klar       | 30 Maj 2025  | CTO           |
| Offert‑API “hello world”        | 6 Juni 2025  | Tech Lead     |
| Valuation pipeline PoC          | 13 Juni 2025 | Data Lead     |
| Första live‑deal betald (pilot) | 4 Juli 2025  | CPO           |
| Prod Go‑Live “Supernova”        | 26 Juli 2025 | Steering Comm |

---

## 2. Workstreams & Leads

| WS                   | Scope                                | Lead     | SL Channel  |
| -------------------- | ------------------------------------ | -------- | ----------- |
| **Core Platform**    | API‑gateway, offers DB, Celery infra | Sofia B. | #space-core |
| **Valuation & ML**   | Stats fetcher, model, rule‑engine    | Jakob L. | #space-ml   |
| **DocGen & PDF**     | Term‑sheet templating + S3           | Karin E. | #space-core |
| **Payouts & Ledger** | Stripe, Wise, double‑entry           | Johan M. | #space-fin  |
| **Admin‑UI & Ops**   | React dashboard, Auth0               | Dana F.  | #space-ops  |
| **Infra & SRE**      | Terraform, Helm, Linkerd             | Ulrik T. | #space-sre  |

---

## 3. Phase Timeline (WBS‑100)

### Phase 1 · Foundation (v0.1 dev‑stack) · 22 maj – 7 jun

1.1 Create monorepo scaffolding
1.2 Setup GitHub Actions baseline (CI‑lint, pytest)
1.3 Provision dev EKS via Terraform
1.4 Docker‑compose local stack (PG + Redis)
1.5 Cursor prompts P‑01→P‑03 executed, PR merged

**Exit criteria:** `/offers` POST returns 202, row in Postgres.

### Phase 2 · Valuation & DocGen MVP · 8 jun – 28 jun

2.1 Spotify API client + cache
2.2 ML model v0 (rule × 4).
2.3 Celery worker autoscale
2.4 Term‑sheet PDF template & hash
2.5 Magic‑link email via Mailgun
2.6 Playwright e2e happy‑path

**Exit criteria:** PENDING→OFFER\_READY in < 10 s; PDF url saved.

### Phase 3 · Payment & Compliance · 29 jun – 19 jul

3.1 Stripe Treasury integration
3.2 Wise fallback + circuit breaker
3.3 Ledger DB & Grafana Cash‑dash
3.4 OPA policies, Gatekeeper
3.5 ISO27k evidence scripts

**Exit criteria:** payout.status SUCCEEDED; latency SLO met 24 h.

### Phase 4 · Go‑Live & Hardening · 20 jul – 26 jul

4.1 Blue‑green rollout via ArgoRollouts
4.2 Chaos‑cron test pass
4.3 FinOps cost‑alert configured
4.4 Public status‑page online
4.5 Steering Committee sign‑off

**Exit criteria:** First 10 real deals paid in < 24 h window.

---

## 4. Deliverables Checklist per Story (DoD)

* [ ] **Code** adheres to `.cursor-rules` (folder, naming, typing).
* [ ] **Unit tests** ≥ 90 % cov (pytest‑cov).
* [ ] **E2E test** if route exposed.
* [ ] **Docs** added to `docs/runbooks/` or ADR.
* [ ] **Helm values** & Secrets path updated.
* [ ] **SLO metric** exported (Prom).
* [ ] **Jira ticket** in “Done”.

---

## 5. Risk Registry (Top‑5)

| ID  | Risk                 | Probability | Impact | Mitigation                            |
| --- | -------------------- | ----------- | ------ | ------------------------------------- |
| R‑1 | Spotify API rate‑cap | M           | H      | 15‑min Redis cache + nightly preload  |
| R‑2 | Stripe payout delays | L           | H      | Wise fallback + circuit breaker       |
| R‑3 | Cursor folder drift  | L           | M      | CI rule‑lint + PR template check      |
| R‑4 | Model overvalues     | M           | M      | Guardrail max multiple 5× L12M        |
| R‑5 | Terraform drift prod | L           | H      | Atlantis auto‑apply block w/ approval |

---

## 6. Monitoring Dashboards

* **Latency & throughput** – Grafana `offers` board (JSON 12345).
* **Payout pipeline** – board 12346.
* **Cost per offer** – board 12347.
* **Chaos & uptime** – board 12348.

---

## 7. Communication & Change‑mgmt

* **Daily stand‑up** 09:00 CET (#space‑core).
* **Demo Friday** 15:00 CET, Zoom.
* **Release note** PR template auto‑posts to #space‑release.

---

## 8. Sign‑off

| Role     | Name                 | Sign |
| -------- | -------------------- | ---- |
| CTO      | \_\_\_\_\_\_\_\_\_\_ |      |
| CPO      | \_\_\_\_\_\_\_\_\_\_ |      |
| Head SRE | \_\_\_\_\_\_         |      |

---

*EOF*
