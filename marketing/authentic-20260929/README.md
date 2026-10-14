# Authenticity rewrite preview

Status: in production since 29 September 2026 (deployment 9a8ee461). Rollback: 0205d366.
Preview: https://fd017e75.spacemusic-a6n.pages.dev/ (branch `authentic-20260929`, noindex).

Owner decisions (29 Sep 2026): invented case studies become labelled illustrative
examples; invented authors become "SPACE Editorial Team"; every external figure is
cited to a source or removed.

## What changed

1,112 reviewed text edits (`edits/*.json`, one file per content area, written by
area agents under `BRIEF.md`, notes in `notes/`) across 113 pages:
- 44+ invented case studies replaced (genre pages, /for/* pages, blog case study and
  partial-rights article); the genre template heading is now "An illustrative example."
- Authors John Doe, Jane Smith, Michael Brown → SPACE Editorial Team, no credentials.
- All stated valuation multiples removed; genre pages show "No fixed multiple".
- About 200 figures removed; about 80 verified and cited in the sentence
  (IFPI, Goldman Sachs, CISAC, SEC filings, Spotify/Deezer/Apple/YouTube official pages,
  US Code, Federal Register, company sites, MBW/Billboard/Variety).
- Factual corrections, e.g. Round Hill did not merge with Concord (it sold its listed
  fund in 2023); Hipgnosis catalog now owned by Sony Music Publishing (July 2026);
  Headspace was not acquired by Amazon; ASCAP is free to join; 2026 US mechanical rate.
- An internal SEO note published as a FAQ on 23 genre pages replaced by a seller FAQ.
- Search titles chosen with Jev (valuation guide, Deezer, major vs independent) and an
  answer line on the calculator (`edits/10-seo-titles.json`).

URLs, links, canonicals, robots, sitemap, H2 counts and JSON-LD types are unchanged.
Titles changed on 5 pages and H1s on 10 (listed in `test-results.json`).

## Build and verification

    node scripts/build-authentic-preview.mjs tmp/authentic-preview-v1-20260929 marketing/authentic-20260929/manifest-v1.json
    ALL_PAGES=1 PLAYWRIGHT_CHANNEL=chrome node scripts/test-authentic-preview.mjs marketing/authentic-20260929/manifest-v1.json

2,135 checks: every file identical to production except reviewed edits and versioned
module names; SEO invariants per page; old text gone from its modules; on all 113
changed pages the server HTML text equals the hydrated text (en-US), no overflow, no
browser errors. Edits are applied by `scripts/authentic-support.mjs`; short finds are
scoped to their own modules/pages.

Jev claims review (experiments/jev-site-review): 707 flagged sentences before, 190 after.
Most remaining strong flags are cited third-party facts and competitor descriptions.

## Needs code changes or owner input (not done by text edits)

- Numeric per-stream table on /guides/what-are-your-streams-worth-2026/ and
  /tools/streaming-calculator/ (numeric fields), "Catalog Value (8x)" genre table, and the
  4x-10x range computed by the streaming calculator and mentioned on /streaming-rates/*.
- 11 source links point to non-existent articles (see notes/compare.md); hrefs were
  deliberately not edited.
- Blog JSON-LD author @type is still Person; "Success Stories" category label.
- Market data page: empty "Not reported" table columns and stat cards; stale source list.
- Genre positioning (all genres vs ambient focus) on comparison pages; Hipgnosis still
  ranked #2 in the best-buyers guide.

## Follow-up v2 (in production since 29 Sep 2026, deployment a090bdaf)

Preview: https://6d8c81f1.spacemusic-a6n.pages.dev/ (branch `authentic-v2-20260929`).
Candidate `tmp/authentic-preview-v2-20260929`, manifest `manifest-v2.json`: v1 edits plus
`20-code.json`, `21-schema-labels.json` and `followup.json` (owner answers, 29 Sep 2026):
- Streaming calculator rebuilt: visitor enters own payout per stream; invented rates and
  the 4-10x range removed; Spotify and Apple statements cited. Streams guide loses the
  per-stream, RPM and "Catalog Value (8x)" columns.
- All dead source links replaced with real sources (0 dead of 84; 12 bot-blocked pages
  verified to exist); mislabeled citations corrected.
- Best-buyers guide: Hipgnosis replaced by Duetti (sourced).
- "All genres" positioning across the site.
- Blog team author is an Organization in schema; "Success Stories" → "Examples";
  market page hides cards, columns and sources without verified data.
- Engine: URL text edits now also update prerendered links (fixes a v1 issue where
  server HTML kept old source URLs until hydration).

2,140 checks on 114 pages passed. Jev claims review: 189 flagged (v1: 190; before: 707).
Open: Round Hill still listed as a buyer (it still runs private funds; owner to decide).
