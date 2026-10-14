# First-Party Marketing Fonts

These are unchanged WOFF2 files fetched from the exact Google Fonts CSS
requests previously imported by the production marketing stylesheet on
2026-09-07. The visual design, font families, variable weight/optical-size
settings, font-display behavior and Unicode coverage have not been changed.

- Fraunces: weights 500-700, optical-size axis 9-144, three subsets.
- Plus Jakarta Sans: weights 300-700, four subsets.

`manifest.json` records the request user agent, original URLs, file hashes,
license sources and Latin subsets used for homepage preloads.
`*.google.css` preserves the provider declarations. `fonts.css` changes
only each font file URL to its fingerprinted, first-party asset path.
The font binaries are not modified, recompressed or resubsetted.

Both fonts use the SIL Open Font License 1.1. The copyright and complete
license notices are included in `fraunces-OFL.txt` and
`plus-jakarta-sans-OFL.txt`, and are copied beside the production fonts.

`scripts/vendor-marketing-fonts.mjs` is the initial download/provenance
script and refuses to overwrite this directory. Production builds are
offline and hash-checked by `scripts/build-home-font-release.mjs`; they do
not fetch a potentially changed version from Google Fonts.

See `marketing/performance/README.md` for deployment and benchmark details.
