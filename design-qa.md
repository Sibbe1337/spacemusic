# Quiet homepage design QA

## Whole-site extension, September 16, 2026

Preview: https://db999946.spacemusic-a6n.pages.dev/; artifact `tmp/quiet-site-seo-v4-20260916`. Production not promoted. This section supersedes the homepage-only scope limit below; prior evidence remains historical.

The approved direction now covers all 137 pre-existing HTML pages plus one new independent-label funding guide. Shared CSS preserves existing content and behavior; only the separately documented Duetti factual refresh and new contextual links change existing visible copy. 1,439 design preservation assertions and 7,951 final SEO/privacy assertions pass. All 139 prior sitemap URLs remain (140 with the new guide).

Reviewed screenshots for 16 page families/representative pages, including Sell, article/guide, comparison, glossary, tools and Apply. Mobile screenshots at 390px and tablet at 768px; narrow DOM checks across nine routes at 320px and six routes at 768px have no horizontal overflow. Headings use Inter. No claim of visual inspection of all individual URLs. Mobile menu/Apply/Typeform welcome and fallback checked without submitting a lead; calculator example verified. New article TOC, canonical and client metadata verified live.

Resolved reviewer findings: old dark CTA contrast and footer email input visibility. Also corrected inline dashboard typography, invisible range tracks, escaped apostrophes in the new article TOC, and overly large Apply top spacing caused by selector specificity. Final read-only content/build review had no actionable findings.

All 140 hosted sitemap destinations return 200 with original production canonicals and preview noindex. All 429 hosted preview files match the artifact after a successful repeat of an initially interrupted network check. Production's 338 public files still match its recorded release. PageSpeed API returned HTTP 429; comparable performance runs and owner approval remain production gates. No ranking, conversion or performance uplift is claimed. Full details and known inherited content issues: `marketing/quiet-site-20260916/README.md`.

Date: 2026-09-16

Final result: passed for the scoped homepage direction preview. Production release not approved or attempted.

## Latest revision: genre directory v3

Implementation: https://c5c52c03.spacemusic-a6n.pages.dev/; artifact `tmp/quiet-home-v3-20260916`, revision `10a8b6d4e02b`.

User comment targeted the nine-link genre grid. It is now a two-column editorial section with larger genre names, complete-row links, descriptions, restrained actions and an all-genres introduction. Audience explanations are retained below. On mobile the introduction and directory stack. This is a deliberate structural revision, not a pixel copy of the supplied screenshot.

Visual review: desktop 1280 x 720; user's viewport 879 x 919; mobile 390 x 844. Additional DOM overflow checks at 320 x 740 and 768 x 900 passed. The 768px introduction fits inside the tested height. Screenshots remain in the task tool results, not a filesystem artifact.

Keyboard Tab/Enter tested between genre destinations with visible focus. Lo-Fi destination and Apply link verified without form submission. Nine rows remain fully visible, with no tabs, collapsible content or JavaScript-dependent reveal. Console showed no errors.

2,943 automated checks pass. All original text, anchors, metadata and structured data preserved; SSR/client markup identical. Homepage body outside the selected section is identical to v2. Independent reviewer found no issues; changed CSS rules are confined to the selected section. All 386 hosted files match. All 139 sitemap destinations respond 200 with preview noindex and original canonicals. Production's 338 files remain unchanged.

No production release, new analytics claims or performance benchmark is implied. The existing startup hash-scroll reset is not changed by this scoped design revision. Prior v2 evidence follows.

## Evidence and comparison

- Source: https://776.one/, inspected live in the browser.
- Implementation: https://f95be3af.spacemusic-a6n.pages.dev/.
- Local artifact: `tmp/quiet-home-v2-20260916`, revision `34539748aef2`.
- Paired desktop screenshots were captured together at 1280 x 720 CSS pixels, device pixel ratio 1. Source and implementation were both at the top, with no cookie overlay.
- Mobile hero and bento screenshots were reviewed at 390 x 844 CSS pixels, device pixel ratio 1.
- Screenshots are displayed in the task's tool results. No filesystem screenshot paths were exposed or invented. Chrome screenshots were clipped using document coordinates to avoid scaling the full browser surface.
- IAB viewport overrides did not change the actual viewport; responsive checks used Chrome with DOM-confirmed dimensions instead.

## Design decisions

- Match the reference's restraint, not its exact business copy or portfolio structure: white background, Inter 500, grey body copy, pale-blue primary action and generous negative space.
- Reference H1 is 40px; SPACE desktop H1 is 42px, with existing two-line copy preserved. Mobile H1 is 31px at 390px and narrower.
- Keep SPACE top navigation and secondary calculator link for task continuity. The reference's floating bottom navigation is intentionally not copied.
- Use three bounded surfaces for the existing catalog, rights and decision explanations. No decorative generated product imagery or artificial data.
- Preserve longer content below the hero; use quieter type and row-based genre links instead of deleting text.

## Issues resolved

- P2: v1 bento container was left-aligned. v2 adds automatic horizontal margins. Desktop DOM and screenshot confirmed a centered 1064px outer container.
- Responsive capture mismatch was a browser-tool issue, not a CSS fix: actual dimensions and document-relative crops were checked before accepting the mobile screenshots.

## Functional and preservation checks

- 2,934 automated assertions passed. Homepage text and linked-anchor multisets are identical to the baseline; server/client homepage markup matches.
- No horizontal document overflow at widths 320, 390, 768 and 1280.
- Mobile menu opens/closes; Apply destination displays the existing guided-review interface. No form data entered or submitted.
- Native FAQ opens with Enter. Visible focus outlines remain available.
- Calculator navigation and 1000 x 12 x 4 x 50% = $24,000 tested.
- Sell navigation retains its existing body; returning home restores the quiet design.
- No browser errors observed. Analytics logged expected localhost/preview exclusions.
- Independent code review found no issues in the scoped delta.
- Hosted 386-file candidate and 338-file production snapshots verified without mismatches.
- 139 sitemap destinations verified, with production canonicals and preview noindex.

## Limits

This is a visual direction preview, not a claim that all site pages now share this design. Other pages and Apply intentionally remain unchanged. The existing footer social placeholders are inherited, not newly fixed. Full assistive-technology testing, historical Apply test suite, field performance and conversion/ranking effects have not been revalidated. A production rollout requires user approval, full performance comparison and normal release checks.
