# Approval, publication and measurement plan

Prepared 8 September 2026. **No approval assumed. No publication, outreach or recording performed.**

## Review inventory

This is the review of the completed **draft materials**, not a claim that implementation or every requested integration-based research step is complete. The unnamed SEO project, market approval, keyword volume/difficulty and prompt-level AI report remain unavailable as described in [REVIEW.md](REVIEW.md).

| ID / destination | Draft copy and sources | Images and links | Decision needed |
| --- | --- | --- | --- |
| A. https://spacemusic.io/calculator/ | H1, introduction, multiple-field helper and calculation explanation in REVIEW.md. Verified against live tool, Apply and policy; invented $24,000 example is labeled. Existing title/meta retained. | No image required. Preserve Apply and guide links; proposed document/policy links 1 and 3 are ready for review. Link 2 waits for D. | Approve exact copy and which link changes belong in the first release. No form or calculation changes. |
| B. https://spacemusic.io/guides/music-catalog-valuation-2026/ | H2 clarification and short interpretation of the [Duetti index](https://www.duetti.co/music-finance-index), not a new multiple table. Keep H1/title/meta/URL and existing substantive text. | Add one primary-source citation. Link 4 waits for E. No image. | Approve narrow factual clarification, not a broad rewrite of the recently published guide. |
| C. https://spacemusic.io/compare/space-vs-royalty-exchange/ | Correct quick verdict, provider-scope and matching comparison claims against [SPACE policy](https://spacemusic.io/pricing.md) and [Royalty Exchange deal options](https://royaltyexchange.com/creators/catalog-deal-options). | No logos/screenshots needed. Preserve useful existing destinations and review CTA. | Approve the corrected comparison language; verify table, verdict, FAQ and schema consistency before publishing. |
| D. https://spacemusic.io/compare/partial-sale-vs-full-sale/ | Workflow Draft 1: ownership denominator, retained interests, setup, example, contract questions and limits. Copyright Office and current SPACE sources. | Current template; document/offer checklist links and existing Apply action. Enables calculator link 2. | Approve a revision at the existing URL, not a new landing page. |
| E. https://spacemusic.io/compare/selling-masters-vs-selling-publishing/ | Workflow Draft 2: separate schedules and income example. Copyright Office, Spotify, identifier guidance and current SPACE sources. | No image; existing Apply action, document checklist and valuation guide. Enables guide link 4. | Approve revised explanation and removal/correction of unsupported superiority claims. |
| F. https://spacemusic.io/compare/catalog-sale-vs-catalog-loan/ | Workflow Draft 3: compare scope, cash, repayment questions and limitations. SPACE/beatBread sources; hypothetical figures are not product terms. Title/H1 correction justified by the misleading “without losing it” promise. | Existing Apply action must remain clearly a sale review, not a loan application. Enables offer-checklist link 6. | Approve comparison and title/H1, then check meta/table/schema for the same assurance. |
| G. https://spacemusic.io/blog/music-catalog-sale-documents-checklist/ | One next-stage sentence only, shown with current paragraph in DISTRIBUTION-DRAFTS.md. | Link 5 to the existing offer checklist. No new image. | Approve internal link, not another document article. |
| H. https://spacemusic.io/blog/music-catalog-offer-checklist/ | One structure-comparison sentence only. | Link 6 only after F is live and verified. No new image. | Approve dependent internal link. |
| I. External editorial messages | Two individualized drafts: rightsHUB reconciliation and LANDR recording/composition distinction. Sources and rejected prospects listed in DISTRIBUTION-DRAFTS.md. | Only existing public supporting pages; no customer records. | Separately approve sender, contact route and each message. No payment for ranking links. |
| J. Two-minute video | Opening, transcript, timed real-screen plan and linked description in DISTRIBUTION-DRAFTS.md. | All footage still required. Preview and analytics-disabled calculation recording setup do not yet exist for this refresh. | Approve script, then recording, then final media before upload. |

**Do not bundle unrelated repairs into approval.** About-page genre exclusivity, old streams-worth calculator claims, the unsupported legacy case-study outcome and the `/blog/` fallback are separately flagged observations. They are not silently changed by approving A or B.

### Recommended sequence, not an authorization

1. Approve and implement A, plus links 1 and 3. Preserve the working application and instrumented calculator behavior.
2. Approve and implement B and C, separately verifiable at their existing addresses.
3. Review D, E and F individually. Publish each approved revision before adding its dependent inbound links. G can be published independently; H depends on F.
4. Consider the two editorial messages only after their evidence and sender/contact routes are approved. No need to wait for a new article; the cited checklists already exist.
5. Record the approved screens and transcript, then obtain final video approval.

This sequence prioritizes the strongest traffic evidence and genuine factual corrections. It does not predict a conversion rate, keyword volume or ranking outcome.

## Publication gate

**Supported path known from the repository:** the release record identifies Cloudflare Pages project `spacemusic`, production branch `main`. No write-capable SEO publishing integration was exposed in this task. Do not describe a publication as completed through one. At approval time, check available supported publishing access and proceed only through a verified path; if unavailable, report that publishing is blocked rather than inventing a deployment.

Current [release record](../../RELEASE.md), read 8 September:

- Verified snapshot: `tmp/journey-v4-20260907` with 299 public files plus `_headers` and `_redirects`.
- Recorded production deployment: https://6c66c5dd.spacemusic-a6n.pages.dev.
- Recorded earlier rollback: `tmp/funnel-stage4-v2-20260907`, https://7c1307d4.spacemusic-a6n.pages.dev.
- 139 sitemap URLs. The three workflow drafts use existing URLs, so this package needs **no sitemap expansion**.

These are observations from the release record, not a new test of the earlier deployment. Re-read the record at implementation because production may have changed after this audit. The immediate rollback for any new release must be the complete verified production version immediately before that release, not automatically an older snapshot named above.

### Before preview

- Preserve the full prior release, route configuration, headers, assets and a file-hash manifest. Record the immutable deployment URL and Git/release identifiers available at that point.
- Use the guarded release builder and versioned modules documented in the repository; never deploy an old design preview or replace the static marketing site with an unrelated backend.
- Map every approved text edit to both server-delivered HTML and corresponding client content. Reconcile visible FAQs and structured data with the approved body. Preserve meaningful existing content topics; correct unsupported statements rather than quietly deleting sections.
- Freeze existing canonical URLs, robots directives, redirects, sitemap entries, article identity/date history and unrelated metadata. Update a reviewed/modified date only for an actual approved content revision, not a fabricated original publication date.
- Preserve the standalone Apply fix, questions, receiver, private source metadata and success-only `application_submitted` event. No new endpoint, CRM, required field, pricing product or market-multiple default.
- Draft files in this research directory are not website assets. Do not include this private review pack, analytics observations or baseline files in the public release.

### Preview checks required after implementation

- Run existing 33 Apply-navigation checks and mocked success/error/double-click/retry/blocked-analytics/blocked-storage scenarios. No test lead is sent to production.
- Check calculator arithmetic, empty/invalid entries, 0 income, 0 and 100% shares, out-of-range percentages and receipt deductions. `1000 × 12 × 4 × 0.5 = 24000`; no second years multiplier or range is introduced.
- Verify changed copy with and without JavaScript, title/description/canonical, structured data, table/FAQ consistency and the presence of existing relevant sections.
- Verify mobile layouts, keyboard/focus behavior, form feedback and destination links. A destination returning 200 is insufficient if it contains a homepage fallback or wrong canonical.
- Compare a three-run mobile performance baseline and three after-runs in the same environment. Investigate a median-LCP deterioration exceeding both 10% and 250 ms before release. No new performance result is claimed by this draft review.
- Compare the entire sitemap set: all 139 existing URLs retained. Review changed-file and metadata diffs to ensure unrelated pages have not changed.

### Public release and rollback

Publish only the specified approved batch after preview checks pass. Preserve its predecessor. Open **every changed public URL** in a real browser after publication, and check a fresh server response for status, intended copy, canonical and links. Confirm that browser/client behavior does not replace the approved server content with stale text.

Also verify Apply navigation from each affected conversion page without sending a production application. Recheck HTTPS/canonical behavior for affected variants without changing unrelated redirect policy. Record actual timestamps, deployment identifiers and check results. If critical behavior fails, restore the previous complete verified release and verify it again.

Technical safeguards reduce deployment risk but cannot guarantee that Google's rankings or traffic will remain unchanged.

## Draft change log

This table records **proposals**, not completed changes. Public-page checks in the evidence manifest describe the existing site on 8 September only.

| URL / scope | Publish date | New deployment | Live verification of proposed edit | GSC baseline, 9 June–6 September |
| --- | --- | --- | --- | --- |
| `/calculator/` | Not published | None | Pending approval/implementation; current page captured 200 | 140 clicks, 1,377 impressions, position 14.1 |
| `/guides/music-catalog-valuation-2026/` | Not published | None | Pending; current page captured 200 | 17 clicks, 7,012 impressions, position 8.5 |
| `/compare/space-vs-royalty-exchange/` | Not published | None | Pending; current page captured 200 | 0 clicks, 104 impressions, position 8.6 |
| Three workflow comparisons | Not published | None | Pending; current destinations captured 200 | Partial-sale page: 0 clicks / 8 impressions / 10.4, no exposed queries. Other two exact-page baselines not collected; collect before publication. |
| Two checklist link edits | Not published | None | Pending; both current articles captured 200 | Newly published 7 September, after this baseline. No exposure opportunity during this 90-day window; do not fabricate a historical comparison. |
| Outreach and video | Not sent / not recorded / not published | Not applicable | No public result | Do not attribute future visits or conversions to drafts. |

Before publication, add each actual change, predecessor, timestamp, test result and verified URL to the live release log. No release log was updated by this research task.

## Equal-period follow-up specification

No follow-up automation or monitoring job has been created. The following is a comparison specification for use after an approved publication.

### Search performance

Let **T** be the actual publication calendar date in the Search Console daily-report timezone. Record that timezone with the export; use the same timezone on both sides. Exclude T to avoid a mixed old/new page day.

| Checkpoint | Before | After | Availability rule |
| --- | --- | --- | --- |
| 28-day readout | T−28 through T−1, 28 complete days | T+1 through T+28, 28 complete days | Wait until the latest required day appears in the complete daily report; exclude preliminary real-time data. |
| 56-day readout | T−56 through T−1, 56 complete days | T+1 through T+56, 56 complete days | Same filters and availability rule. |

The initial 90-day report is a prioritization baseline, **not** the denominator for a 28-day before/after percentage. Pages published recently may have too little comparable history; label that explicitly and use descriptive post-launch counts instead of a misleading uplift.

Freeze the main series as `sc-domain:spacemusic.io`, Web, all countries, all devices and all appearances, with an exact URL filter. Keep slashless variants separate unless reporting an explicitly defined combined series in both periods. Never add unrelated page and query summaries together.

Freeze exact query cohorts before looking at the after-period:

- Calculator: `how much is a music catalog worth`, `music catalog valuation`, `how to value a music catalog`.
- Valuation guide: `music catalog valuation multiples 2025 2026`, `what's the average acquisition multiple for jazz catalogs`, `music catalog valuation`.
- Royalty Exchange comparison: `sell royalty`, with `royalty marketplace` separately marked ambiguous intent.
- Company-name searches: separate brand-form bucket; keep ambiguous `space music inc` separate from confirmed company demand.

Report page totals alongside, but not as if they belonged to those exposed query rows. Keep anonymized/omitted queries and small counts in the limitations. The saved [baseline JSON](gsc-baseline.json) includes additional exact rows for reference.

If US targeting is approved, create an additional **US-only** before/after series with identical page/query/device filters. Do not compare all-country before to US-only after. The same applies to a mobile-only analysis; capture its matching baseline before drawing conclusions.

For each series report clicks, impressions, CTR and average position, absolute differences and denominators. Percentage changes from zero are undefined. A changed average position or CTR may reflect a changed query mix, not a fixed set of rankings improving. Record major releases or other interventions during the period.

### Applications and qualification, separately

Plausible goal reporting was observed, but there is no verified private accepted/qualified-lead dataset in this audit. A reported `application_submitted` event must correspond to the existing successful receiver response; a legacy `Form: Submission` event is not proof of an accepted or qualified application.

Measure received unique applications from a private, deduplicated receiver record, then manually review contactability, rights and documented income. Use lead reference, received date, permitted source path, review status, reason and qualification date. Keep **unreviewed** separate from **reviewed and not qualified**. Do not put names, emails, documents or financial amounts into analytics or this public-content pack.

Report received applications, reviewed applications, qualified applications and unreviewed applications as separate counts. State whether a qualification rate uses all received applications or only reviewed applications; show both with their denominators if helpful. Do not call an application-to-review delay a fall in lead quality.

The new measurement was introduced on 7 September, so a pre-instrumentation period is not directly comparable to a post-instrumentation period. Staff traffic, blocked analytics and repeat visits can also separate dashboard events from actual unique leads. Use equal complete Plausible periods in its recorded site timezone, and reconcile against the private receiver rather than claiming universal analytics capture.

### Measured results versus possible explanations

**Measured:** same-filter counts and rates, page/query observations, accepted receiver records and completed qualification reviews when available.

**Possible explanations, not proven causes:** clearer assumptions, new internal links, Google result changes, seasonality, country/device mix, tracking changes, other releases or editorial coverage. A before/after comparison alone does not isolate the effect of this copy refresh. Do not turn a small count difference into a guaranteed percentage benefit.

### Remaining data gates

- Confirm the SEO service/project URL before claiming its integrations, articles or AI scans were inspected through that service.
- Confirm the primary target market before presenting country-specific keyword prioritization as final.
- Obtain supported keyword-volume/difficulty access or an export; no figures can be supplied from the blocked provider today.
- Obtain prompt-level AI report exports with scan dates, engine names and cited pages before reporting cross-engine coverage.
- Obtain private application and qualification access before reporting business outcomes. Public analytics events alone are insufficient.
