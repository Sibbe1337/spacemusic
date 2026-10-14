# Authenticity rewrite: brief for each content area

SPACE (spacemusic.io) is a direct buyer of royalty-generating music catalogs. Much of
the site's older content was AI-generated and contains invented customer cases,
invented people and credentials, valuation multiples stated as fact, and unsourced
figures. The owner decided (29 Sep 2026):

1. Invented case studies are replaced by clearly labelled illustrative examples.
2. Invented authors become "SPACE Editorial Team" with no credentials.
3. Every external figure is either verified against a source and cited, or removed
   by rewriting the sentence without it.

SEO matters: the pages rank. Keep URLs, links, structure, headings and keywords.

## Your job

Produce `marketing/authentic-20260929/edits/<your-area>.json`:

```json
{"area": "…", "edits": [
  {"find": "exact old text", "replace": "new text", "reason": "fabricated case | unsourced figure removed | figure sourced | multiple removed | author | competitor fact sourced | policy", "sources": ["https://…"]}
]}
```

Then run `node scripts/authentic-check.mjs <your-file>.json` from the repo root
(`/Users/emilsoujeh/spacemusic`) and fix until it reports `0 missing`. Read any WARN.

Your input list is `marketing/authentic-20260929/work/<your-area>.json`: sentences a
model flagged (scores are probabilities; 0.5+ = flagged). It is a starting point, not
a complete list and not a verdict. Read the full content of your pages in the module
source (paths given in your task) and fix everything in scope, including unflagged
problems of the same kind. Leave sentences that are fine.

## Rules

1. Never invent anything: customers, deals, prices achieved, buyers, quotes, people,
   credentials, statistics, dates, or sources.
2. Invented SPACE case studies or outcomes → an illustrative example. Start it with
   "Illustrative example, not a SPACE transaction:". Use simple hypothetical inputs
   (catalog size, annual royalties) and explain which factors a review looks at
   (rights ownership, revenue history and consistency, metadata, concentration,
   documentation). No buyer, no multiple, no price achieved, no deal timeline, no
   outcome. For structured case-study objects, rewrite every field value so the set
   reads as one hypothetical (e.g. catalogSize "Hypothetical: 60 tracks", annualRevenue
   "Hypothetical: $20,000 a year in documented royalties", outcome = what a review
   would check and that any offer depends on individual review).
3. Valuation multiples or price ranges presented as fact ("4-8x annual revenue") →
   remove the number and describe the drivers qualitatively; point to individual
   review. Keep a multiple only if a primary public source states it; then name the
   source in the sentence.
4. Other external figures (market sizes, follower counts, per-stream rates, company
   facts, competitor fees, dates) → verify with WebSearch/WebFetch against a primary
   or reputable source (company filings, press releases, official help pages, the
   platform's own reports, established trade press). If verified: keep it (update if
   outdated), name the source in the sentence ("according to Spotify's Loud & Clear
   report"), and put the URL in `sources`. If you cannot verify it quickly: rewrite the
   sentence without the figure, keeping the useful point. Do not spend long on one fact.
5. Competitors: only facts their own site or filings support, phrased as "X's website
   states…" when appropriate. Neutral tone. No disparagement.
6. Authors: fake bylines/bios → "SPACE Editorial Team"; bio: "SPACE Editorial Team
   writes SPACE's guides on catalog sales, rights and royalties." No credentials.
7. SEO: do not change URLs, links, or slugs. Change a page title, meta description or
   heading only if it contains an invented or unsourced claim, minimally, keeping the
   main keyword. Keep paragraphs roughly the same length and keep topical keywords.
8. SPACE's own terms are in `tmp/motion-preview-v3-20260929/pricing.md`. Anything
   about SPACE's process, fees or timing must match it exactly. Restating it is fine.
9. Style: English, plain, specific, short sentences. No hype words ("booming",
   "massive", "skyrocketing"), no "not X but Y", no em-dash asides, no emoji.
10. Mechanics: `find` must be an exact substring of a decoded JS string literal in the
    listed module(s) (unescape JS escapes; the module is minified, strings are plain).
    The replacement applies everywhere the text occurs on the site, so make `find`
    specific (a whole sentence or whole field value). Items noted "HTML text" have a
    leading +/− icon in HTML only; search the module without it. Keep edits within your
    area's modules. If the same text appears in pages outside your area, say so.
11. Template literals with variables (e.g. `${a}`) can be edited with an edit that has
    `"template": true`; `find`/`replace` are then the literal's source text including
    `${a}`. Also add plain edits for the expanded text in HTML if needed; the checker
    and the build verify that server HTML and hydrated text agree.
12. `"htmlOnly": true` limits an edit to prerendered HTML (for text that exists only
    in rendered form).
13. `"href": true` replaces a link URL: `find` is the exact old URL, `replace` the new
    one. It changes the URL in JS strings (exact match only) and in HTML hrefs.
14. Only write your edits JSON (and optionally `notes/<your-area>.md`). Do not edit
    site files, run builds, deploy, or touch other areas' files.

## Report back (short)

Counts: edits; case studies replaced; figures verified and cited (list claim → source);
figures removed; titles/meta/headings changed (list them); anything the owner must
decide or provide; any text shared with other areas.
