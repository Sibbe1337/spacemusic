# compare: notes for the owner

## Dead or invented source links (not changed; rule 7 forbids URL edits)
404 on 2026-09-29, in competitorComparisonsExpanded sources lists:
- royaltyexchange.com/how-it-works -> suggest https://royaltyexchange.com/how-auctions-work-sellers
- musicbusinessworldwide.com/the-rise-of-music-royalty-marketplaces/
- billboard.com/pro/music-catalog-sales-explained/
- billboard.com/artist/hipgnosis-songs-fund/ -> suggest https://www.billboard.com/pro/hipgnosis-name-change-music-catalog-company-recognition/
- billboard.com/pro/primary-wave-music-catalog-acquisitions/ (Primary Wave entry is dead code, overridden)
- billboard.com/pro/reservoir-media-music-catalog-growth/
- musicbusinessworldwide.com/companies/reservoir-media/
- musicbusinessworldwide.com/concord-acquires-round-hill-music-royalty-fund/ -> suggest https://www.musicbusinessworldwide.com/concord-acquires-round-hills-uk-listed-music-fund/
- billboard.com/pro/concord-round-hill-music-merger-details/
- variety.com/2023/music/news/round-hill-music-concord-acquisition-1235574628/
- ir.reservoir-media.com (no response)
- hipgnosissongs.com now redirects to recognitionmusicgroup.com (also used in the best-buyers guide table)
Hipgnosis page: add https://www.musicbusinessworldwide.com/done-deal-sony-music-publishing-completes-acquisition-of-recognition-music-groups-catalog/

## Not edited (owned by another area)
Table cells "15-25% of net revenue", "$0.003-$0.005", "$0.007-$0.01" on /compare/major-label-vs-independent and
/compare/spotify-vs-apple-music-royalties are whole literals that also occur inside glossary-osNbpTze.js sentences;
a substring edit would corrupt the glossary. They need a whole-literal edit or coordination with glossary-rates.

## Dead code
competitorComparisonsExpanded still holds the old Primary Wave entry ($2B, $5M+ minimums). It is replaced at runtime
by competitorComparisons-primary-wave (already sourced, checked 2026-09-07), so it was left unedited.
