# Connected portal verification

Historical baseline. The later pilot implementation and its remaining launch
gates are recorded in [PILOT-VERIFICATION.md](PILOT-VERIFICATION.md).

September 18, 2026. Phase 2B continues the approved Catalog Review plan.
Distribution is deferred. This is a synthetic integration, not a launch sign-off.

## Executed checks

Final run on September 18: 362 backend/integration tests, 50 connected UI/client
tests and 61 original-preview/public-funnel regression tests passed, with no
failures or skipped tests. These totals include parametrized unit cases, not
473 independent production security checks. Ruff checks and formatting passed.

- Backend, HTTP, storage/scanner protocol and browser tests:
  `python3 -m pytest tests/catalog_review -q`.
- Connected UI/client failure and privacy tests:
  `node --test services/catalog_review_ui/*.test.mjs`.
- Original preview and existing public funnel/intake regression checks:
  `node --test services/catalog_review_preview/*.test.mjs marketing/funnel/scenario.test.mjs marketing/funnel/tracking.test.mjs marketing/typeform-intake/intake.test.mjs`.
- Ruff core/import checks:
  `python3 -m ruff check services/catalog_review tests/catalog_review --select E4,E7,E9,F,I`.

The browser check launches an installed Chromium with a fresh temporary profile.
Its requests to `https://review.test` are intercepted and passed through an
authenticated temporary loopback test transport to the real ASGI app. The app
uses real disposable PostgreSQL and the unprivileged RLS runtime role. No browser
request is allowed through to an external site. The test transport is not a
deployment entrypoint and its fixture controls are not application endpoints.

The test uses existing bundled Playwright and installed Chrome. For another
workstation, set `SPACE_TEST_NODE_MODULES` and `SPACE_TEST_CHROME`. It does not
install a browser or reuse a personal browser profile. Screenshots are generated
inside the pytest temporary output directory, with synthetic content only.
The final desktop/mobile captures are also retained in
`output/catalog-review-20260918/`; they are test screenshots, not a public portal.

## Exercised journey

1. Email-style navigation opens a static shell without consuming its invitation.
   The fragment is removed from the address before an explicit keyboard action
   exchanges it for a Secure/HttpOnly session cookie.
2. The owner saves selected release metadata and declared rights to PostgreSQL.
   Unknown ownership is null, not an invented zero. Future music stays excluded.
3. A synthetic CSV uploads once into test quarantine. A fake scanner advances
   it for this test only. The owner selects it and saves the draft revision.
4. Submission commits, but the browser loses the response. Retry uses the same
   request ID and obtains the existing submission, not a duplicate or new version.
5. A separately assigned reviewer fixture with MFA asks a question. The owner
   replies in the portal. A committed reply's response is deliberately lost;
   after refresh shows that answer, an accessible retry sends exactly the same
   request ID and body. A second question can then be answered. These immutable
   records stay separate from the snapshot, without duplicate replies.
6. A server-side expiry clears private DOM, forms and in-memory state. No raw
   documents, question text or tokens enter browser storage or analytics.

Desktop (1365 px) and mobile (390 px) screenshots were inspected. The approved
Inter/wordmark/editorial styling is reused; neither viewport has horizontal
overflow in the tested journey. This is not a full screen-reader, cross-browser
or production accessibility certification.

## Failure and security checks

- Existing membership/MFA, RLS and immutable-record startup checks now cover
  review questions and replies too. Foreign question IDs do not reveal content.
- Concurrent question/reply requests create one record; reusing IDs with changed
  bodies or another author fails. Questions are capped at 20 per workspace.
- Recovery has uniform responses for absent, mismatched, active and unavailable
  workspaces. It never returns a login token, authenticates a caller or claims an
  email was delivered. A usable invitation is not invalidated by recovery.
- Uploads enforce the actual streamed 25 MiB ceiling, not just Content-Length.
  Tests cover missing/understated lengths, timeout, two concurrent upload slots
  and capacity recovery after rejection/completion. These are per-process test
  controls; deployment still needs ingress/global resource limits.
- Identical upload replay works after submission; new files remain forbidden.
  Unknown store/DB acknowledgements never trigger destructive cleanup. Proven
  rollback cleanup is limited to objects whose creation was acknowledged.
- Downloads require current membership on every read, valid immutable bytes and
  accepted status, and use attachment/octet-stream/no-store/nosniff responses.
- Client tests cover denied/expired access, offline/HTML responses, slow response
  bodies, stale responses after logout, conflicts, lost acknowledgements, XSS,
  explicit deletion confirmation and bfcache/page suspension clearing.
- R2 adapter tests inject a fake SDK transport. ClamAV tests inject sockets; no
  bucket, provider, malware scanner daemon or external API was contacted.

## Independent review

Backend review found that upload replay was rejected after submission. The fix
keeps authorization first, resolves an exact existing request, and rejects only
new writes after submission. A permanent regression covers both cases. The
review also requested stream/concurrency/timeout regressions, now present.

Frontend follow-up review found private state remaining after a mutation 404,
and an unresolved reply blocking later replies after a successful refresh showed
its committed answer. All 404 responses now conservatively clear private state,
including missing documents/questions. A same-ID reply retry stays accessible
even after its answer appears. A conflicting immutable answer requires a fresh
authoritative read and explicit discard of only the unresolved message; equal
body text is never accepted as proof of success. Targeted unit regressions and
the real browser/database lost-reply sequence pass after these corrections.
An independent spot-check reran both original reproductions, the conflict path
and all 50 UI/client tests, with no unresolved findings in that scope. The full
362-test backend/browser run was executed by the implementing agent, not the
independent reviewer. Neither review is production-readiness certification.

## Preservation

The following path/content baselines match before and after this tranche. The
measurement walks depth-first, sorting entries within each directory with
JavaScript `localeCompare`, and hashes each relative file path followed by its
bytes. It is a local preservation check, not a production crawl or ranking
guarantee.

| Directory | Files | SHA-256 aggregate |
| --- | --- | --- |
| marketing | 2171 | `fd8e0d8d9b7e3ce899f651716bae9134e6360282033a0dad5b0e235921b48c21` |
| tmp/editorial-preview-v5-20260916 | 546 | `a9e7d0c3d391b83ffd5c2808be4cfa3de049ca5deadb6001c217d8230628f364` |
| services/spacemusic/portal | 30 | `f6e8c0c56b3dc3fb8b22eb4bf821f88207ac0910beeaddda2410405b5f4227b6` |

All 141 sitemap URLs remain. No production, DNS, Apply/Typeform, Resend, Stripe,
Too Lost or marketing change was made. The repo contained unrelated changes;
none were reverted or included in a commit. Schema changes ran only in new,
temporary databases, never as a migration against an existing environment.

## Still blocks customer launch

Actual staff identity/MFA enrollment, regional processor/hosting approval,
secret rotation, real invitation delivery, private bucket configuration, AV
daemon policy and bounded document parsers are not verified by these tests.
Complete erasure and restore/deletion-journal reconciliation are not implemented.
Signed production intake forwarding and read-only Too Lost OAuth/import are
still separate launch work. No production dependency/security certification,
paid report permission, checkout or distribution service is claimed.

The test origin/domain gates remain in code. Upload routes are disabled unless
a store is explicitly injected. Do not relax these gates to turn a passing test
suite into a public launch. See `DEPLOYMENT-PROPOSAL.md` for the approval sequence.
