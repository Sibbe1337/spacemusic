# Comparison Motion Preview (idea 2)

Status: in production since September 29, 2026 (deployment 0205d366). Rollback: 55284dbb.

Preview: https://2ea0480d.spacemusic-a6n.pages.dev/ (alias https://motion-20260929.spacemusic-a6n.pages.dev/)
Cloudflare Pages project `spacemusic`, preview branch `motion-20260929`.

## Scope

The existing homepage "Stream it. Or sell it." table animates as it scrolls into
view: the "Keep streaming" column fades back and each "Sell to SPACE" row lights
up in turn (faint brand tint, plus a small dot on desktop).

- One inline `<style id="motion-comparison">` at the start of the section. No new
  text, elements, JavaScript, fonts, images or third-party requests.
- Pure CSS scroll-driven animation (`animation-timeline: view()`); only opacity and
  transform animate.
- Unsupported browsers and reduced motion see exactly the production table.
- Headings, text, links, metadata, canonicals, JSON-LD, sitemap and Apply flow are
  unchanged. Server HTML and the client homepage literal are updated together.

Source: `tmp/editorial-preview-v5-20260916` (current production).
Candidate: `tmp/motion-preview-v3-20260929`. Manifest: `manifest-v3.json`.
Build: `node scripts/build-motion-preview.mjs tmp/motion-preview-v3-20260929 marketing/motion-20260929/manifest-v3.json`

## Revisions

v1 (d7daa49f): dark card, 48 bars sliding right. Owner feedback: laggy and odd looking.
v2 (432ce0ed): light card, 24 bars shrinking left to right. Owner feedback: looks bad
(mid-scroll reads as a broken chart).
v3 (2ea0480d): no chart; animate the existing table instead (owner's chosen direction).

## Verification

`PLAYWRIGHT_CHANNEL=chrome node scripts/test-motion-preview.mjs` — 1,267 checks:
every source file byte-identical or identical after undoing the two versioned
module renames; index.html and the homepage module differ only by the style block; section text identical;
title, description, canonical, robots, H1/H2, JSON-LD and all links identical;
browser checks at 1280/390/320 px, no overflow, no errors, reduced motion still,
client navigation Sell → Home renders the figure. Screenshots `shot-*.png`.

Live: preview returns `x-robots-tag: noindex`; preview homepage and Sell match the
candidate bytes; production homepage, Sell, Calculator, Apply, sitemap and robots
match the production artifact byte for byte.

Owner approved; performance comparison recorded in marketing/RELEASE.md. The pre-existing cookie notice still overlaps content on scroll.
