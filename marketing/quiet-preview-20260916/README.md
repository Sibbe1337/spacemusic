# Quiet homepage direction: preview only

Current preview (genre revision v3): https://c5c52c03.spacemusic-a6n.pages.dev/

Previous homepage preview (v2): https://f95be3af.spacemusic-a6n.pages.dev/

Branch alias: https://codex-quiet-home-20260916.spacemusic-a6n.pages.dev/

Built and checked 2026-09-16. This is a homepage design direction for user review, not a production release. Other routes deliberately retain the v5 design. Do not infer approval to roll this design across the site.

## Genre revision v3

The user requested a radical improvement of the genre grid. The revision replaces the 3-by-3 grid with an editorial directory beside the existing all-genres explanation. Existing audience notes follow below. Every text node, all nine genre destinations and both other section links remain unchanged. No new image, font or script dependency was added.

- Artifact: `tmp/quiet-home-v3-20260916`; manifest `build-manifest-v3.json`; revision `10a8b6d4e02b`.
- 2,943 checks pass, including an assertion that homepage content outside the selected section is identical to v2. Independent review: no findings.
- Browser rendering inspected at 1280, 879 and 390px; overflow also checked at 320 and 768px. All nine mobile rows fit without horizontal overflow.
- Keyboard Tab retains a visible focus outline; Enter on Lo-Fi opens the original destination. Individual-review link opens the unchanged Apply page. No forms submitted.
- Live: 386 artifact files match, all 139 sitemap URLs respond 200 with preview noindex, production canonicals preserved. Production's 338 public files still match the original production snapshot.
- The preview app's existing startup scroll reset can override an initial hash URL. The delivered browser tab is positioned on the genre section; the public link opens the full homepage.

The remainder documents the original v2 direction and its reproduction history.

## Baseline and scope

- Baseline: `tmp/growth-preview-v5-20260916`, manifest `marketing/growth-20260916/build-manifest-v5.json`, revision `52842f5a03ff`.
- Candidate: `tmp/quiet-home-v2-20260916`, manifest `build-manifest-v2.json`, revision `34539748aef2`.
- Production remains `tmp/typeform-intake-release-v3-20260915`; `marketing/RELEASE.md` was not changed.
- Inspiration: the white background, restrained Inter typography, spacing and pale-blue action on https://776.one/. This is an adaptation, not a clone.
- Existing review sidebar becomes three bento surfaces below the centered hero. No generated pictures, new claims, removed text, removed links, new fonts or animation dependencies.
- CSS is scoped to the homepage. Existing HTML and client-rendered homepage are transformed together. New assets are versioned; previous assets remain available.
- Apply and all baseline non-HTML files are byte-identical. Other page bodies, SEO metadata, structured data, sitemap and hosting configuration are preserved. Preview noindex is supplied by hosting, not baked into production HTML.

## Verification

- `test-quiet-preview.mjs`: 2,934 checks passed, including exact homepage text/link multisets and SSR/client equality.
- Independent read-only review: no findings; 59-module import validation reported no errors or warnings.
- Hosted preview: 386 public files match the prepared artifact exactly.
- All 139 sitemap destinations return 200; all 137 HTML destinations retain production canonicals and receive preview noindex.
- Production: all 338 public files still match the verified production snapshot.
- Browser: mobile menu, Apply navigation (without submission), Home return, FAQ Enter interaction, calculator and Sell navigation checked. Calculator example returned $24,000 for 1000 x 12 x 4 x 50%.
- Viewports: 320, 390, 768 and 1280 CSS pixels checked for document overflow; no overflow. Mobile hero/bento and paired desktop reference/candidate screenshots reviewed. Temporary viewport overrides reset.
- No browser errors observed; expected Plausible exclusions for localhost/preview were logged.

No production leads were submitted. No full historical 33-test Apply suite, Lighthouse median-LCP comparison or ranking/conversion measurement was claimed for this visual preview. A production release needs separate approval and its own release gates.

## Reproduce

```sh
node scripts/build-quiet-preview.mjs marketing/growth-20260916/build-manifest-v5.json tmp/quiet-home-v3-20260916 marketing/quiet-preview-20260916/build-manifest-v3.json
node scripts/test-quiet-preview.mjs marketing/quiet-preview-20260916/build-manifest-v3.json
node scripts/check-growth-preview.mjs https://f95be3af.spacemusic-a6n.pages.dev
node scripts/verify-release-files.mjs tmp/quiet-home-v2-20260916 https://f95be3af.spacemusic-a6n.pages.dev
node scripts/verify-release-files.mjs tmp/typeform-intake-release-v3-20260915 https://spacemusic.io
```

The previous preview remains available at https://70c85abf.spacemusic-a6n.pages.dev/. Preview rollback is simply returning to that immutable URL; production was never switched.
