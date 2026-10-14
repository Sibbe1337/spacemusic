# Pricing Resource Routing

Status: published September 10, 2026 after owner approval, approximately 09:07 UTC.
Production: https://a74ea86c.spacemusic-a6n.pages.dev.
Verified preview: https://4fa0530e.spacemusic-a6n.pages.dev.
Current release: `tmp/pricing-routing-release-20260910`.
Immediate rollback: `tmp/calculator-review-v2-20260909` / deployment `3654f780`.
See `PUBLISH-LOG.md`. No Search Console submission was made.

## Observations: September 10, 2026

- `/pricing.md`: HTTP 200, `text/markdown; charset=utf-8`, no canonical Link
  response header. It is the existing offer-policy resource, not an HTML page.
- `/pricing` and `/pricing/`: HTTP 200 with homepage HTML and the homepage
  canonical in the server response. Neither is an established pricing page.
- `/pricing.md/`: the same unintended homepage fallback.
- HTTP and www variants of the exact Markdown URL already redirect to HTTPS,
  non-www. The live sitemap has 139 URLs and already includes `/pricing.md`.
- The published `llms.txt` links to that Markdown resource deliberately.

These observations do not verify Google's selected canonical, backlink metrics,
spam scores, duplicate-content harm or a two-to-four-week improvement forecast.

## Published Change

Append an exact `/pricing.md` rule to the existing `_headers`:

```text
/pricing.md
  Link: <https://spacemusic.io/pricing.md>; rel="canonical"
```

Append `/pricing.md/ /pricing.md 301` to `_redirects`. Preserve existing
`llms.txt` rules. Do not insert HTML into Markdown, create `/pricing`, change
internal links, or replace the Markdown URL in the sitemap. Leave unrelated
extensionless fallback routing for a separately scoped review.

The guarded builder copies the latest verified snapshot to a fresh directory.
All 333 public files, including Apply, content, metadata, assets, sitemap and
robots, must remain byte-identical. Only the two hosting control files change.

```sh
node scripts/build-pricing-routing-draft.mjs tmp/pricing-routing-draft-20260910
node scripts/check-pricing-routing.mjs LOCAL_OR_PREVIEW_ORIGIN
node scripts/check-llms-routing.mjs LOCAL_OR_PREVIEW_ORIGIN
node scripts/verify-release-files.mjs tmp/pricing-routing-draft-20260910 LOCAL_OR_PREVIEW_ORIGIN
```

Before any approved deployment, recheck `marketing/RELEASE.md` and compare all
public files to production. A preview must be checked before production; after
publication repeat both routing tests and all 139 sitemap checks. Preserve the
previous complete release as rollback. No indexing or ranking guarantee applies.

The builder is deliberately pinned to its original September 9 source and now
refuses the updated release pointer. It is a historical reproducibility guard,
not a general-purpose future release builder. Start future work from the current
verified release above and explicitly preserve both hosting configuration files.

## Checks Completed Locally

- Builder preserved all 333 public files and all 139 sitemap entries. Four
  negative tests rejected source overwrite, nested output, ancestor output and
  an existing output directory.
- The verified source snapshot still matches all 333 production public files.
- Local Cloudflare Pages runtime parsed two header and two redirect rules.
  All 21 pricing routing cases passed, including GET/HEAD, query preservation,
  four user-agent strings and nine unaffected routes.
- Existing `llms.txt` routing checks passed. All 333 local public HTTP responses
  match the draft byte-for-byte, with no new content assets.
- Existing production SEO checks passed for 139 sitemap entries. That checker
  skips HTML canonical checks on non-HTML resources; it does not establish that
  the missing pricing header is already fixed. The new targeted check does.
- Runtime: cached Wrangler 4.32.0, using its supported 2025-08-16 compatibility
  date fallback. This is local runtime validation, not deployed-edge validation.

At the initial draft stage no deployment was made. After owner approval, the
identical candidate passed hosted preview checks and was deployed to production.
Both uploads reused all 333 public assets and uploaded only hosting rules.
Preview and production each passed all 33 Apply-navigation checks with zero
browser errors or submissions. Production passed 24 targeted pricing checks,
the existing llms.txt checks, all 333 HTTP file comparisons and 139 sitemap
checks. See the publish log for scope and limitations. No analytics conversions
or form submissions were generated. Search Console's selected canonical and
ranking effects remain unverified.

## Sources

- [Google canonical documentation](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls): HTTP Link headers support non-HTML documents; an HTML head element is not appropriate for this Markdown resource.
- [Cloudflare Pages headers](https://developers.cloudflare.com/pages/configuration/headers/): exact-path response headers for static assets.
- [Cloudflare Pages redirects](https://developers.cloudflare.com/pages/configuration/redirects/): narrowly scoped permanent redirects.
- [Live offer policy](https://spacemusic.io/pricing.md) and [live sitemap](https://spacemusic.io/sitemap.xml): current resource, content and destination.
