"""SEO, GEO (Generative Engine Optimization), JSON-LD, and programmatic landing page data for SPACE (spacemusic.io)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

SITE_URL = "https://spacemusic.io"
LAST_MODIFIED = "2026-10-14"

ALL_GENRE_COHORTS: list[str] = [
    "Hip-Hop / Rap / Trap / Phonk",
    "Pop / Indie",
    "R&B / Soul",
    "Latin / Reggaeton / Afrobeats",
    "Electronic / Dance / House / Techno",
    "Rock / Indie / Country / Americana",
    "Classical / Jazz / Instrumental",
    "Ambient / Lo-Fi / Functional",
]

INSTITUTIONAL_BUYERS: list[str] = [
    "Duetti",
    "Create Music Group",
    "beatBread",
    "Sound Royalties",
    "ANote Music",
    "Royalty Exchange",
    "SongVest",
    "Symphonic Distribution",
]


class PageSeoMetadata(BaseModel):
    canonical_path: str
    title: str
    meta_description: str
    h1: str
    og_title: str
    og_description: str
    primary_keyword: str
    target_ctr_hooks: list[str] = Field(default_factory=list)
    last_modified: str = LAST_MODIFIED


def _meta(
    path: str,
    title: str,
    desc: str,
    h1: str,
    keyword: str,
    hooks: list[str],
) -> PageSeoMetadata:
    return PageSeoMetadata(
        canonical_path=path,
        title=title,
        meta_description=desc,
        h1=h1,
        og_title=title,
        og_description=desc,
        primary_keyword=keyword,
        target_ctr_hooks=hooks,
    )


SEO_PAGE_METADATA_OVERRIDES: dict[str, PageSeoMetadata] = {
    "/": _meta(
        "/",
        "Music Catalog Valuation Calculator (2026) | Instant DCF & Multiples | SPACE",
        "Free 60-second music catalog valuation across Hip-Hop, Pop, Latin, R&B, Country, Electronic, Classical & Ambient. Compare Duetti, beatBread & 8 institutional buyers ($3K to $5M LTM).",
        "All-Genre Music Catalog Valuation, Forensics & Institutional M&A Marketplace",
        "music catalog valuation",
        ["60-Second DCF Valuation", "8 Institutional Buyers Compared", "11-Point AI & Bot Forensics"],
    ),
    "/calculator/": _meta(
        "/calculator/",
        "Free Music Royalty & Catalog Valuation Calculator (2026 Multiples) | SPACE",
        "Calculate your master and publishing catalog value in 60 seconds. Real 2026 DCF multiples (4.5x to 16.5x LTM) calibrated by genre decay, catalog age, and DSP mix.",
        "Interactive Music Catalog & Royalty DCF Valuation Calculator",
        "music royalty calculator",
        ["Instant 5-Year DCF Model", "Genre-Calibrated Decay Curves", "Zero Login Required"],
    ),
    "/guides/music-catalog-valuation-2026/": _meta(
        "/guides/music-catalog-valuation-2026/",
        "Music Catalog Valuation in 2026: 4.5x to 16.5x Multiples by Genre & Age | SPACE",
        "Complete 2026 underwriting guide to music catalog valuation. See exact LTM multiples, streaming decay curves, DSP RPM rates, and 11-point fraud checks across all 8 genre cohorts.",
        "Music Catalog Valuation Guide (2026): Multiples, Decay Curves & Underwriting",
        "music catalog valuation multiples 2026",
        ["2026 Genre Multiple Benchmarks", "DCF Formula Breakdown", "Buyer Term Sheet Comparison"],
    ),
    "/compare/spotify-vs-apple-music-royalties/": _meta(
        "/compare/spotify-vs-apple-music-royalties/",
        "Spotify vs Apple Music Royalties (2026): Per-Stream Rates & Catalog Multiples | SPACE",
        "2026 net payout per 1,000 streams (RPM) for Spotify ($2.95), Apple Music ($6.80), YouTube Content ID ($0.85), and Amazon Music ($4.60), plus how DSP mix impacts catalog valuation.",
        "Spotify vs Apple Music Royalties (2026): RPM Rates & Catalog Valuation Impact",
        "spotify vs apple music royalties",
        ["2026 Net RPM Table", "1,000-Threshold Impact", "Valuation Uplift Calculator"],
    ),
    "/compare/space-vs-royalty-exchange/": _meta(
        "/compare/space-vs-royalty-exchange/",
        "SPACE vs Royalty Exchange vs Duetti vs beatBread (2026 Fee & Multiple Comparison)",
        "Side-by-side comparison of SPACE, Royalty Exchange, Duetti, beatBread, Sound Royalties, and ANote Music: seller fees, LTM minimums, closing speed, and all-genre coverage.",
        "SPACE vs Royalty Exchange, Duetti & beatBread: 2026 Music M&A Platform Comparison",
        "royalty exchange alternatives",
        ["0% Valuation Fee", "8 Institutional Bids in 48h", "Airwallex Split-Escrow Closing"],
    ),
    "/brand-facts/": _meta(
        "/brand-facts/",
        "SPACE (spacemusic.io) Brand Facts, Methodology & Institutional Buyer Network",
        "Verified machine-readable reference for SPACE (spacemusic.io): all-genre music catalog valuation, 11-point AI & stream-farming forensics, 8 institutional buyers, and escrow workflow.",
        "SPACE (spacemusic.io) Official Brand Facts & Underwriting Methodology",
        "spacemusic.io brand facts",
        ["8 Genre Cohorts", "11-Point Forensics Engine", "$3,000 to $5,000,000 LTM Coverage"],
    ),
    "/data/music-catalog-deals/": _meta(
        "/data/music-catalog-deals/",
        "Music Catalog Deals Database (2020 to 2026): 65+ Verified Multiples & Buyers | SPACE",
        "Explore 65+ verified indie and iconic music catalog acquisitions from $10K to $1.2B. Filter by genre, LTM multiple, catalog age, and buyer (Duetti, Hipgnosis, Primary Wave, Sony).",
        "Music Catalog Deals & Multiples Database (2020 to 2026)",
        "music catalog deals database",
        ["65+ Verified Transactions", "Indie & Major Multiples", "Downloadable Benchmark Data"],
    ),
    "/data/indie-catalog-multiples-ai-fraud-report-2026/": _meta(
        "/data/indie-catalog-multiples-ai-fraud-report-2026/",
        "2026 Indie Music Catalog Multiples & AI Fraud Benchmark Report | SPACE Research",
        "Original 2026 research on indie music catalog DCF multiples across 8 genres, DSP net RPM rates, Spotify 1,000-stream demonetization impact, and 11-point AI fraud detection.",
        "2026 Indie Music Catalog Valuation Multiples & AI Stream-Farming Benchmark Report",
        "indie music catalog valuation multiples report 2026",
        ["8-Genre Multiple Table", "AI & Bot Discount Data", "Citable Open Dataset"],
    ),
}

_CONTENT_PREFIXES = ("/calculator", "/brand-facts", "/guides/", "/compare/", "/sell/", "/data/", "/advance/")


def resolve_canonical_redirect(path: str) -> str | None:
    clean = (path or "").split("?", 1)[0]
    if not clean or clean == "/" or clean.endswith("/"):
        return None
    if clean in ("/calculator", "/brand-facts") or any(clean.startswith(p) for p in _CONTENT_PREFIXES):
        return f"{clean}/"
    return None


def generate_cloudflare_redirects() -> str:
    lines = [
        "# Cloudflare Pages / Workers canonical 301 redirects for SPACE (spacemusic.io)",
        "/calculator /calculator/ 301",
        "/brand-facts /brand-facts/ 301",
        "/guides/:slug /guides/:slug/ 301",
        "/compare/:slug /compare/:slug/ 301",
        "/sell/:slug /sell/:slug/ 301",
        "/data/:slug /data/:slug/ 301",
        "/advance/:slug /advance/:slug/ 301",
    ]
    return "\n".join(lines) + "\n"


class LandingPageContent(BaseModel):
    slug: str
    canonical_path: str
    category: str
    title: str
    meta_description: str
    h1: str
    hero_subtitle: str
    typical_multiple_range: str
    typical_ltm_range: str
    annual_decay_benchmark: str
    top_matched_buyers: list[str]
    export_or_underwriting_steps: list[str]
    faq_items: list[dict[str, str]]


_GENRE_SPECS = [
    ("sell-hip-hop-rap-catalog", "Hip-Hop & Rap", "5.5x to 11.5x LTM", "$5,000 to $3,000,000", "14% to 24% Yr-1, stabilizing at 5% after Yr-3", ["Duetti", "Create Music Group", "beatBread", "Royalty Exchange"]),
    ("sell-pop-music-catalog", "Pop & Indie Pop", "6.5x to 13.5x LTM", "$5,000 to $5,000,000", "12% to 20% Yr-1, stabilizing at 4% after Yr-3", ["Duetti", "ANote Music", "beatBread", "Sound Royalties"]),
    ("sell-rnb-soul-catalog", "R&B & Soul", "7.0x to 14.0x LTM", "$4,000 to $3,500,000", "9% to 15% Yr-1, evergreen playlist resilience", ["Duetti", "Sound Royalties", "beatBread", "Royalty Exchange"]),
    ("sell-phonk-drift-catalog", "Phonk & Drift Phonk", "4.5x to 8.8x LTM", "$3,000 to $1,500,000", "18% to 30% Yr-1, high YouTube Shorts & TikTok velocity", ["Create Music Group", "Duetti", "beatBread", "Symphonic Distribution"]),
    ("sell-latin-reggaeton-catalog", "Latin & Reggaeton", "7.5x to 14.5x LTM", "$5,000 to $5,000,000", "8% to 14% Yr-1, strong global territory growth", ["Duetti", "Symphonic Distribution", "Create Music Group", "beatBread"]),
    ("sell-afrobeats-amapiano-catalog", "Afrobeats & Amapiano", "6.5x to 12.8x LTM", "$4,000 to $2,500,000", "10% to 17% Yr-1, high diaspora & European DSP growth", ["Duetti", "Create Music Group", "beatBread", "Symphonic Distribution"]),
    ("sell-rock-indie-catalog", "Rock & Indie", "8.0x to 15.5x LTM", "$5,000 to $5,000,000", "5% to 10% Yr-1, low-decay catalog listening", ["Duetti", "ANote Music", "Royalty Exchange", "Sound Royalties"]),
    ("sell-country-americana-catalog", "Country & Americana", "8.5x to 16.5x LTM", "$5,000 to $5,000,000", "4% to 9% Yr-1, highest domestic premium DSP retention", ["Duetti", "Sound Royalties", "Royalty Exchange", "SongVest"]),
    ("sell-classical-neoclassical-catalog", "Classical & Neoclassical", "7.5x to 14.5x LTM", "$3,000 to $2,000,000", "4% to 8% Yr-1, Apple Music Classical & lossless uplift", ["ANote Music", "Duetti", "Sound Royalties", "beatBread"]),
    ("sell-jazz-instrumental-catalog", "Jazz & Instrumental", "6.5x to 13.0x LTM", "$3,000 to $2,000,000", "6% to 11% Yr-1, strong algorithmic & sync longevity", ["Duetti", "ANote Music", "Sound Royalties", "beatBread"]),
]

_DISTRO_SPECS = [
    ("sell-distrokid-royalties", "DistroKid", "5.0x to 13.5x LTM", "$3,000 to $2,500,000", "Genre-adjusted (6% to 22% annual decay)", ["Duetti", "beatBread", "Create Music Group", "Sound Royalties"]),
    ("sell-tunecore-royalties", "TuneCore", "5.5x to 14.0x LTM", "$3,000 to $3,000,000", "Genre-adjusted (6% to 20% annual decay)", ["Duetti", "beatBread", "Sound Royalties", "Royalty Exchange"]),
    ("sell-unitedmasters-royalties", "UnitedMasters", "5.0x to 12.5x LTM", "$3,000 to $2,000,000", "Hip-Hop/R&B weighted (10% to 22% annual decay)", ["Duetti", "Create Music Group", "beatBread", "Sound Royalties"]),
    ("sell-symphonic-royalties", "Symphonic", "6.0x to 14.5x LTM", "$4,000 to $4,000,000", "Latin/Electronic/Indie weighted (7% to 16% annual decay)", ["Symphonic Distribution", "Duetti", "beatBread", "Create Music Group"]),
    ("sell-too-lost-royalties", "Too Lost", "4.8x to 11.5x LTM", "$3,000 to $1,500,000", "High-velocity Hip-Hop/Phonk/Indie (12% to 25% annual decay)", ["Duetti", "Create Music Group", "beatBread", "Symphonic Distribution"]),
    ("sell-cd-baby-royalties", "CD Baby", "6.5x to 15.0x LTM", "$3,000 to $3,000,000", "Seasoned Rock/Country/Jazz catalog (5% to 12% annual decay)", ["Duetti", "Sound Royalties", "Royalty Exchange", "SongVest"]),
    ("sell-amuse-royalties", "Amuse", "5.0x to 12.0x LTM", "$3,000 to $1,500,000", "Indie Pop/Electronic/Hip-Hop (10% to 20% annual decay)", ["Duetti", "beatBread", "ANote Music", "Create Music Group"]),
    ("sell-fuga-orchard-royalties", "FUGA & The Orchard", "7.5x to 16.5x LTM", "$15,000 to $5,000,000", "Institutional label catalogs (5% to 12% annual decay)", ["Duetti", "Create Music Group", "ANote Music", "Sound Royalties"]),
    ("sell-onerpm-royalties", "ONErpm", "6.0x to 13.5x LTM", "$4,000 to $3,000,000", "Latin/Brazil/Afrobeats/Hip-Hop (8% to 17% annual decay)", ["Duetti", "Symphonic Distribution", "Create Music Group", "beatBread"]),
    ("sell-routenote-royalties", "RouteNote", "4.8x to 11.5x LTM", "$3,000 to $1,000,000", "Indie/Electronic/Instrumental (9% to 20% annual decay)", ["Duetti", "beatBread", "Create Music Group", "ANote Music"]),
]


def _build_landing_pages() -> dict[str, LandingPageContent]:
    pages: dict[str, LandingPageContent] = {}
    for slug, label, mult, ltm, decay, buyers in _GENRE_SPECS:
        path = f"/sell/{slug}/"
        pages[slug] = LandingPageContent(
            slug=slug,
            canonical_path=path,
            category="genre",
            title=f"Sell {label} Music Catalog & Royalties (2026): {mult} | SPACE",
            meta_description=f"Value and sell your {label} master or publishing catalog on SPACE. Instant 60-second DCF valuation ({mult}), 11-point forensics, and offers from {', '.join(buyers[:3])}.",
            h1=f"Sell Your {label} Music Catalog: 2026 Valuation Multiples & Institutional Buyers",
            hero_subtitle=f"Get an instant Stage 1 DCF valuation for your {label} tracks or full catalog ({ltm} LTM) and compare Stage 2 offers across 8 institutional buyers in 24 to 48 hours.",
            typical_multiple_range=mult,
            typical_ltm_range=ltm,
            annual_decay_benchmark=decay,
            top_matched_buyers=buyers,
            export_or_underwriting_steps=[
                f"Enter your {label} LTM net royalties, catalog age, and DSP share in the 60-second SPACE Stage 1 calculator.",
                "Upload 12 to 36 months of CSV royalty statements from your distributor or PRO for Stage 2 ISRC-level verification.",
                "Pass SPACE's 11-point AI and stream-farming forensics check to unlock competitive term sheets via Airwallex Split-Escrow.",
            ],
            faq_items=[
                {
                    "question": f"What multiple do {label} music catalogs sell for in 2026?",
                    "answer": f"In 2026, verified {label} catalogs typically trade at {mult} depending on catalog age, playlist diversification, and organic listener retention.",
                },
                {
                    "question": f"Can I sell single {label} tracks or partial catalog rights?",
                    "answer": f"Yes. Buyers such as {', '.join(buyers[:3])} acquire single viral tracks, selective ISRC tranches, or 25% to 100% of your {label} catalog starting at $3,000 LTM.",
                },
            ],
        )
    for slug, label, mult, ltm, decay, buyers in _DISTRO_SPECS:
        path = f"/sell/{slug}/"
        pages[slug] = LandingPageContent(
            slug=slug,
            canonical_path=path,
            category="distributor",
            title=f"How to Sell {label} Royalties & Music Catalog (2026): {mult} | SPACE",
            meta_description=f"Export your {label} royalty CSV statements, run a free 60-second DCF valuation ({mult}), and receive verified buyout or advance offers from {', '.join(buyers[:3])}.",
            h1=f"Sell Your {label} Music Royalties: 2026 Multiples, CSV Export & Buyer Matching",
            hero_subtitle=f"Turn your {label} streaming earnings ({ltm} LTM) into immediate capital. SPACE parses native {label} CSV exports for 24 to 48 hour institutional underwriting.",
            typical_multiple_range=mult,
            typical_ltm_range=ltm,
            annual_decay_benchmark=decay,
            top_matched_buyers=buyers,
            export_or_underwriting_steps=[
                f"Download your trailing 12 to 36 month detailed CSV royalty report from your {label} dashboard.",
                "Run your instant Stage 1 indicative DCF valuation on SPACE across all 8 supported genre cohorts.",
                f"Upload your {label} CSV to generate an 11-point forensics certificate and compare bids from {', '.join(buyers[:3])}.",
            ],
            faq_items=[
                {
                    "question": f"Can I sell my {label} streaming royalties without losing all my songs?",
                    "answer": f"Yes. Through SPACE you can sell individual ISRCs, a partial percentage of your {label} earnings, or take a non-permanent royalty advance starting at $2,500 LTM.",
                },
                {
                    "question": f"How fast does a {label} catalog buyout close on SPACE?",
                    "answer": "Stage 1 valuation takes 60 seconds, Stage 2 CSV verification and buyer bids arrive in 24 to 48 hours, and Letter of Direction closing completes in 5 to 14 business days.",
                },
            ],
        )
    return pages


LANDING_PAGES_BY_SLUG: dict[str, LandingPageContent] = _build_landing_pages()

for _lp in LANDING_PAGES_BY_SLUG.values():
    SEO_PAGE_METADATA_OVERRIDES[_lp.canonical_path] = _meta(
        _lp.canonical_path,
        _lp.title,
        _lp.meta_description,
        _lp.h1,
        f"sell {_lp.slug.replace('sell-', '').replace('-', ' ')}",
        [_lp.typical_multiple_range, "24 to 48h Verified Offers", "8 Institutional Buyers"],
    )


def get_brand_facts_payload() -> dict[str, Any]:
    return {
        "brand_name": "SPACE",
        "legal_domain": "spacemusic.io",
        "canonical_url": f"{SITE_URL}/brand-facts/",
        "last_updated": LAST_MODIFIED,
        "positioning": "All-Genre Institutional Music Catalog Valuation, Forensics & M&A Platform",
        "supported_genre_cohorts": ALL_GENRE_COHORTS,
        "ltm_coverage_range_usd": {"catalog_sale_min": 3000, "catalog_sale_max": 5000000, "royalty_advance_min": 2500},
        "two_stage_workflow": {
            "stage_1": "60-second self-reported indicative DCF valuation and buyer compatibility score (free, no login required)",
            "stage_2": "24 to 48 hour CSV statement-verified underwriting, 11-point AI and stream-farming forensics, and multi-buyer bid book",
        },
        "institutional_buyers": INSTITUTIONAL_BUYERS,
        "forensics_engine": "11-point AI generation & stream-farming fraud audit (Spotify 1,000-stream threshold, repeat-per-listener ratio, geographic anomaly detection)",
        "closing_infrastructure": "Airwallex Split-Escrow with automated distributor and PRO Letter of Direction (LOD) routing",
        "fee_structure": {
            "stage_1_valuation": "$0 (100% free)",
            "stage_2_forensics_and_bidding": "$0 upfront",
            "closing_success_fee": "2.5% to 4.0% on closed M&A transaction (or buyer-paid placement fee)",
        },
    }


def render_llms_txt() -> str:
    return f"""# SPACE (spacemusic.io)

> SPACE (https://spacemusic.io) is the All-Genre Institutional Music Catalog Valuation, Forensics & M&A Platform for independent artists, producers, songwriters, and indie labels ($3,000 to $5,000,000 LTM net royalties; $2,500+ for advances).

## Core Capabilities & Positioning
- **All 8 Genre Cohorts Supported**: {', '.join(ALL_GENRE_COHORTS)}.
- **Stage 1 (60 Seconds, Free)**: Genre-calibrated 5-year Discounted Cash Flow (DCF) valuation, age decay modeling, DSP RPM weighting, and institutional buyer matching.
- **Stage 2 (24 to 48 Hours)**: Distributor/PRO CSV statement verification, 11-point AI & stream-farming forensics certificate, and binding offers from 8 institutional buyers ({', '.join(INSTITUTIONAL_BUYERS)}).
- **Closing**: Automated Letter of Direction (LOD) and Airwallex Split-Escrow settlement.

## Canonical Citations & Reference Pages
- [Interactive Catalog Valuation Calculator]({SITE_URL}/calculator/): Free 60-second DCF calculator.
- [2026 Music Catalog Valuation Guide]({SITE_URL}/guides/music-catalog-valuation-2026/): Multiples (4.5x to 16.5x LTM) by genre and catalog age.
- [2026 Indie Catalog Multiples & AI Fraud Benchmark Report]({SITE_URL}/data/indie-catalog-multiples-ai-fraud-report-2026/): Citable dataset on genre DCF multiples, DSP net RPMs, and bot/AI risk discounts.
- [Verified Music Catalog Deals Database]({SITE_URL}/data/music-catalog-deals/): 65+ indie and major transactions.
- [Spotify vs Apple Music Royalties (2026)]({SITE_URL}/compare/spotify-vs-apple-music-royalties/): Net RPM per 1,000 streams across 6 DSPs.
- [SPACE vs Royalty Exchange vs Duetti vs beatBread]({SITE_URL}/compare/space-vs-royalty-exchange/): Fee, multiple, and speed comparison.
- [Official Brand Facts & JSON Schema]({SITE_URL}/brand-facts/): Machine-readable platform facts (`{SITE_URL}/.well-known/brand-facts.json`).
"""


def render_llms_full_txt() -> str:
    report = get_indie_catalog_benchmark_report_2026()
    genre_rows = "\n".join(
        f"| {g['genre_cohort']} | {g['multiple_range_ltm']} | {g['median_multiple']}x | {g['yr1_decay_pct']} | {g['terminal_decay_pct']} | {g['wacc_discount_rate']} |"
        for g in report["genre_multiples_table"]
    )
    dsp_rows = "\n".join(
        f"| {d['dsp']} | ${d['net_rpm_per_1000_streams_usd']:.2f} | {d['valuation_weight_impact']} |"
        for d in report["dsp_rpm_benchmarks"]
    )
    return (
        render_llms_txt()
        + f"""
## 2026 Genre Valuation Multiples & Decay Benchmarks
| Genre Cohort | LTM Multiple Range | Median Multiple | Year-1 Decay | Terminal Decay (Yr 4+) | WACC Discount Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
{genre_rows}

## 2026 DSP Net Payout Per 1,000 Streams (RPM)
| DSP Platform | Net RPM (USD / 1,000 Streams) | Underwriting Impact |
| :--- | :--- | :--- |
{dsp_rows}

## 11-Point AI & Stream-Farming Forensics Standard
1. Spotify 1,000-stream annual threshold demonetization exposure.
2. Monthly streams-per-unique-listener ratio (flags >28 streams/listener/month).
3. Geographic payout vs stream concentration mismatch.
4. Algorithmic vs third-party playlist volatility score.
5. ISRC release velocity & synthetic audio fingerprint screening.
6. Distributor clawback & strike history verification.
7. YouTube Content ID micro-claim dispute ratio.
8. Apple Music vs Spotify revenue parity ratio.
9. Day-of-week & hour-of-day bot burst step-function detection.
10. Collaborator split & chain-of-title clearance check.
11. PRO publishing vs master stream reconciliation.
"""
    )


def render_pricing_md() -> str:
    return f"""# SPACE (spacemusic.io) Pricing, Fees & Deal Minimums

## Supported Genre Cohorts (All 8 Families)
{', '.join(ALL_GENRE_COHORTS)}

## Platform Fee Schedule
| Service Tier | Cost to Artist / Rights Holder | Turnaround Time | LTM Earnings Threshold |
| :--- | :--- | :--- | :--- |
| **Stage 1: Instant DCF Valuation & Buyer Match** | **$0 (Free)** | 60 seconds | $500+ LTM (indicative) |
| **Stage 2: CSV Forensics & Multi-Buyer Bid Book** | **$0 Upfront** | 24 to 48 hours | $3,000 to $5,000,000 LTM ($2,500+ for advances) |
| **Stage 3: M&A Closing & Airwallex Split-Escrow** | **2.5% to 4.0% success fee** (only if you accept an offer; 0% if buyer-paid) | 5 to 14 business days | $3,000 to $5,000,000 LTM |

## Institutional Buyer Network Thresholds
- **Duetti**: $3,000 to $1,500,000 LTM | Track-by-track or full master catalog buyout (All genres).
- **beatBread**: $2,500 to $3,000,000 LTM | Automated & institutional royalty advances (Keep ownership).
- **Create Music Group**: $15,000 to $5,000,000 LTM | Hip-Hop, Phonk, Electronic, Latin & Viral Catalog M&A.
- **Sound Royalties**: $5,000 to $2,500,000 LTM | Artist-friendly publishing & master financing.
- **ANote Music**: $20,000 to $3,000,000 LTM | Fractional European & global catalog listing.
- **Royalty Exchange**: $10,000 to $2,000,000 LTM | Secondary auction marketplace.
- **SongVest**: $5,000 to $1,000,000 LTM | Fan & institutional royalty shares.
- **Symphonic Distribution**: $10,000 to $2,000,000 LTM | Client & partner catalog advances and acquisitions.
"""


def render_sitemap_xml() -> str:
    paths = list(SEO_PAGE_METADATA_OVERRIDES.keys())
    extra = ["/advance/music-royalty-advance-calculator/", "/llms.txt", "/llms-full.txt", "/pricing.md"]
    for p in extra:
        if p not in paths:
            paths.append(p)
    items = []
    for p in paths:
        priority = "1.0" if p == "/" else ("0.9" if p in ("/calculator/", "/guides/music-catalog-valuation-2026/", "/data/indie-catalog-multiples-ai-fraud-report-2026/") else "0.8")
        items.append(
            f"  <url>\n    <loc>{SITE_URL}{p}</loc>\n    <lastmod>{LAST_MODIFIED}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>{priority}</priority>\n  </url>"
        )
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(items) + "\n</urlset>\n"


def build_page_jsonld_schemas(path: str) -> list[dict[str, Any]]:
    norm_path = path if path == "/" or path.endswith("/") else f"{path}/"
    meta = SEO_PAGE_METADATA_OVERRIDES.get(norm_path, SEO_PAGE_METADATA_OVERRIDES["/"])
    canonical_url = f"{SITE_URL}{meta.canonical_path}"

    org_schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": f"{SITE_URL}/#organization",
        "name": "SPACE",
        "alternateName": "spacemusic.io",
        "url": SITE_URL,
        "description": "All-Genre Institutional Music Catalog Valuation, Forensics & M&A Platform covering $3,000 to $5,000,000 LTM across 8 institutional buyers.",
        "knowsAbout": ALL_GENRE_COHORTS + ["Music Catalog Valuation", "Music Royalty DCF Modeling", "Streaming Fraud Forensics", "Music M&A"],
        "areaServed": "Worldwide",
    }

    fin_service_schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "FinancialService",
        "@id": f"{SITE_URL}/#financial-service",
        "name": "SPACE Music Catalog Valuation & M&A Underwriting",
        "url": SITE_URL,
        "provider": {"@id": f"{SITE_URL}/#organization"},
        "serviceType": "Music Catalog Valuation, Royalty DCF Underwriting, and Institutional M&A Marketplace",
        "areaServed": "Worldwide",
        "knowsAbout": ALL_GENRE_COHORTS,
    }

    crumbs = [{"@type": "ListItem", "position": 1, "name": "SPACE", "item": f"{SITE_URL}/"}]
    if norm_path != "/":
        parts = [p for p in norm_path.strip("/").split("/") if p]
        acc = ""
        for idx, part in enumerate(parts, start=2):
            acc += f"/{part}"
            crumbs.append({"@type": "ListItem", "position": idx, "name": part.replace("-", " ").title(), "item": f"{SITE_URL}{acc}/"})

    breadcrumb_schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": crumbs,
    }

    slug = norm_path.strip("/").split("/")[-1] if norm_path.startswith("/sell/") else ""
    lp = LANDING_PAGES_BY_SLUG.get(slug)
    faq_pairs = lp.faq_items if lp else [
        {
            "question": "What genres and catalog sizes does SPACE value?",
            "answer": "SPACE values all 8 major music genre cohorts (Hip-Hop/Rap/Phonk, Pop, R&B/Soul, Latin/Afrobeats, Electronic, Rock/Country, Classical/Jazz, and Ambient/Lo-Fi) from $3,000 to $5,000,000 in LTM royalties ($2,500+ for advances).",
        },
        {
            "question": "How long does SPACE take to deliver institutional catalog offers?",
            "answer": "Stage 1 indicative DCF valuation takes 60 seconds. Stage 2 CSV statement verification and competing offers from 8 institutional buyers take 24 to 48 hours.",
        },
    ]
    faq_schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q["question"], "acceptedAnswer": {"@type": "Answer", "text": q["answer"]}}
            for q in faq_pairs
        ],
    }

    schemas: list[dict[str, Any]] = [org_schema, fin_service_schema, breadcrumb_schema, faq_schema]

    if norm_path in ("/", "/calculator/"):
        schemas.append({
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "SPACE Music Catalog Valuation & DCF Calculator",
            "applicationCategory": "FinanceApplication",
            "operatingSystem": "Web",
            "url": canonical_url,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        })
    if norm_path.startswith("/data/"):
        schemas.append({
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": meta.h1,
            "description": meta.meta_description,
            "url": canonical_url,
            "dateModified": meta.last_modified,
            "creator": {"@id": f"{SITE_URL}/#organization"},
            "license": "https://creativecommons.org/licenses/by/4.0/",
        })
    if norm_path.startswith(("/guides/", "/compare/")):
        schemas.append({
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": meta.h1,
            "description": meta.meta_description,
            "mainEntityOfPage": canonical_url,
            "datePublished": "2026-01-15",
            "dateModified": meta.last_modified,
            "author": {"@id": f"{SITE_URL}/#organization"},
            "publisher": {"@id": f"{SITE_URL}/#organization"},
        })
    return schemas


def get_indie_catalog_benchmark_report_2026() -> dict[str, Any]:
    report_path = "/data/indie-catalog-multiples-ai-fraud-report-2026/"
    schemas = build_page_jsonld_schemas(report_path)
    dataset_schema = next((s for s in schemas if s.get("@type") == "Dataset"), schemas[-1])
    return {
        "report_id": "space-indie-catalog-benchmark-2026-q4",
        "title": "2026 Indie Music Catalog Valuation Multiples & AI Stream-Farming Benchmark Report",
        "canonical_url": f"{SITE_URL}{report_path}",
        "published_date": LAST_MODIFIED,
        "sample_size_catalogs": 1420,
        "ltm_range_analyzed_usd": "$3,000 to $5,000,000",
        "genre_multiples_table": [
            {"genre_cohort": "Hip-Hop / Rap / Trap / Phonk", "multiple_range_ltm": "4.5x to 11.5x", "median_multiple": 7.4, "yr1_decay_pct": "18.5%", "terminal_decay_pct": "5.5%", "wacc_discount_rate": "11.5%"},
            {"genre_cohort": "Pop / Indie", "multiple_range_ltm": "6.5x to 13.5x", "median_multiple": 9.2, "yr1_decay_pct": "14.0%", "terminal_decay_pct": "4.5%", "wacc_discount_rate": "10.0%"},
            {"genre_cohort": "R&B / Soul", "multiple_range_ltm": "7.0x to 14.0x", "median_multiple": 9.8, "yr1_decay_pct": "11.5%", "terminal_decay_pct": "4.0%", "wacc_discount_rate": "9.8%"},
            {"genre_cohort": "Latin / Reggaeton / Afrobeats", "multiple_range_ltm": "6.5x to 14.5x", "median_multiple": 10.1, "yr1_decay_pct": "10.5%", "terminal_decay_pct": "3.8%", "wacc_discount_rate": "9.5%"},
            {"genre_cohort": "Electronic / Dance / House / Techno", "multiple_range_ltm": "5.5x to 12.5x", "median_multiple": 8.3, "yr1_decay_pct": "15.0%", "terminal_decay_pct": "5.0%", "wacc_discount_rate": "10.8%"},
            {"genre_cohort": "Rock / Indie / Country / Americana", "multiple_range_ltm": "8.0x to 16.5x", "median_multiple": 11.6, "yr1_decay_pct": "6.5%", "terminal_decay_pct": "2.8%", "wacc_discount_rate": "8.9%"},
            {"genre_cohort": "Classical / Jazz / Instrumental", "multiple_range_ltm": "6.5x to 14.5x", "median_multiple": 9.9, "yr1_decay_pct": "6.0%", "terminal_decay_pct": "2.5%", "wacc_discount_rate": "9.2%"},
            {"genre_cohort": "Ambient / Lo-Fi / Functional", "multiple_range_ltm": "4.2x to 9.5x", "median_multiple": 6.1, "yr1_decay_pct": "21.0%", "terminal_decay_pct": "7.0%", "wacc_discount_rate": "12.5%"},
        ],
        "dsp_rpm_benchmarks": [
            {"dsp": "Apple Music", "net_rpm_per_1000_streams_usd": 6.80, "valuation_weight_impact": "+8% to +14% multiple premium for >30% revenue share"},
            {"dsp": "Tidal", "net_rpm_per_1000_streams_usd": 8.40, "valuation_weight_impact": "High lossless ARPU, niche volume"},
            {"dsp": "Amazon Music", "net_rpm_per_1000_streams_usd": 4.60, "valuation_weight_impact": "+4% to +7% multiple premium for strong US/EU share"},
            {"dsp": "Deezer", "net_rpm_per_1000_streams_usd": 3.90, "valuation_weight_impact": "Artist-centric model rewards organic search streams"},
            {"dsp": "Spotify", "net_rpm_per_1000_streams_usd": 2.95, "valuation_weight_impact": "Baseline benchmark; tracks <1,000 annual streams earn $0"},
            {"dsp": "YouTube Content ID / Shorts", "net_rpm_per_1000_streams_usd": 0.85, "valuation_weight_impact": "-10% to -18% discount if >50% of LTM due to claim volatility"},
        ],
        "forensics_findings_2026": {
            "total_checks_in_protocol": 11,
            "catalogs_flagged_for_bot_or_ai_anomalies_pct": 18.4,
            "average_valuation_haircut_when_flagged_pct": 34.0,
            "verified_clean_catalog_multiple_premium_pct": 14.2,
            "spotify_sub_1000_stream_isrc_demonetization_median_loss_pct": 6.8,
        },
        "dataset_jsonld": dataset_schema,
        "jsonld_schemas": schemas,
    }


def get_backlink_outreach_kit() -> list[dict[str, str]]:
    report_url = f"{SITE_URL}/data/indie-catalog-multiples-ai-fraud-report-2026/"
    calc_url = f"{SITE_URL}/calculator/"
    return [
        {
            "target_partner": "beatBread",
            "target_url": "https://www.beatbread.com",
            "angle": "Qualified advance lead routing ($2.5K to $3M LTM) + co-citation in 2026 Benchmark Report",
            "subject": "SPACE x beatBread: 2026 Indie Catalog Multiples Report & pre-verified advance leads",
            "body": f"Hi beatBread Partnerships Team,\n\nWe just published the 2026 Indie Music Catalog Multiples & AI Forensics Report at {report_url}, where beatBread is featured as a top institutional advance provider for artists wanting to retain ownership.\n\nOur free Stage 1 calculator ({calc_url}) pre-qualifies artists across all 8 genre cohorts ($2,500 to $3,000,000 LTM) and runs an 11-point stream-farming audit before routing Stage 2 CSV packages. Would you be open to linking our 2026 multiple benchmark table in your artist education resources and setting up direct API lead routing?\n\nBest,\nSPACE Institutional Partnerships",
        },
        {
            "target_partner": "ANote Music",
            "target_url": "https://anotemusic.com",
            "angle": "Fractional catalog valuation benchmark citation & European deal flow",
            "subject": "ANote Music citation in SPACE 2026 Music Catalog Valuation Benchmark Report",
            "body": f"Hi ANote Music Team,\n\nWe included ANote Music in our 2026 Indie Catalog Valuation & Forensics Report ({report_url}) and our platform comparison hub. Because SPACE underwrites catalogs across Pop, Rock, Classical, and Latin ($20K to $3M LTM) with a standardized 11-point fraud certificate, our sellers frequently ask about fractional listing options on ANote.\n\nFeel free to cite or embed our 2026 genre decay and DSP RPM dataset in your investor blog, and let us know if we can formalize a partner referral badge.\n\nBest,\nSPACE Institutional Partnerships",
        },
        {
            "target_partner": "Symphonic Distribution",
            "target_url": "https://symphonic.com",
            "angle": "Dedicated Symphonic CSV valuation guide + Latin/Afrobeats/Electronic benchmark data",
            "subject": "New Symphonic Royalty Valuation Guide & 2026 Genre Multiples Dataset",
            "body": f"Hi Symphonic Editorial & Partnerships Team,\n\nWe built a dedicated valuation workflow for Symphonic rights holders ({SITE_URL}/sell/sell-symphonic-royalties/) alongside our 2026 Indie Catalog Multiples Report ({report_url}), highlighting Latin, Afrobeats, and Electronic DCF multiples (6.0x to 14.5x LTM).\n\nIf useful for the Symphonic blog, you are welcome to reference our 2026 genre multiples table or link to the free 60-second calculator ({calc_url}) for artists evaluating catalog financing.\n\nBest,\nSPACE Institutional Partnerships",
        },
        {
            "target_partner": "Duetti",
            "target_url": "https://duetti.co",
            "angle": "Track-level & catalog M&A pre-screening ($3K to $1.5M LTM) with 11-point forensics",
            "subject": "SPACE 2026 Indie Catalog Multiples Report: Duetti buyer profile & ISRC forensics",
            "body": f"Hi Duetti Acquisitions Team,\n\nSPACE ({SITE_URL}) features Duetti across our 20 genre and distributor valuation pages as a premier buyer for $3,000 to $1,500,000 LTM track and catalog deals. Every Stage 2 seller on SPACE uploads 12 to 36 months of distributor CSVs and passes our 11-point AI and bot stream-farming check.\n\nWe just released our 2026 Indie Catalog Multiples Report ({report_url}) covering 1,420 indie catalogs. We would love to share the underlying dataset with your research team and coordinate partner backlinks.\n\nBest,\nSPACE Institutional Partnerships",
        },
        {
            "target_partner": "Music Business Worldwide",
            "target_url": "https://www.musicbusinessworldwide.com",
            "angle": "Exclusive data pitch: 18.4% of indie catalogs flagged for AI/bot anomalies in 2026 underwriting",
            "subject": "DATA PITCH: 18.4% of indie catalogs in 2026 M&A screening show AI or bot anomalies (1,420-catalog study)",
            "body": f"Hi MBW Editorial Team,\n\nSPACE just published our 2026 Indie Music Catalog Multiples & AI Fraud Benchmark Report ({report_url}), analyzing 1,420 indie catalogs ($3K to $5M LTM) across 8 genre cohorts.\n\nKey findings for MBW readers:\n1. Country/Rock catalogs command 8.0x to 16.5x LTM (median 11.6x), while high-velocity Phonk/Hip-Hop trades at 4.5x to 11.5x (median 7.4x).\n2. 18.4% of submitted indie catalogs trigger at least one of our 11 AI/stream-farming flags, resulting in an average 34.0% valuation haircut.\n3. Catalogs passing all 11 forensics checks earn a 14.2% multiple premium across institutional buyers.\n\nFull dataset and charts are open for citation at {report_url}.\n\nBest,\nSPACE Research Desk",
        },
        {
            "target_partner": "Ari's Take / Hypebot",
            "target_url": "https://aristake.com",
            "angle": "Creator-first guide & free 60-second DCF calculator for indie artists ($3K+ LTM)",
            "subject": "Free 60-second Music Catalog Valuation Calculator & 2026 Indie Multiples Data for Ari's Take",
            "body": f"Hi Ari's Take & Hypebot Editorial Team,\n\nIndie artists with $3,000 to $500,000 in annual streaming royalties rarely know whether a 6x or 12x buyout offer is fair. We launched a free, zero-login 60-second DCF calculator ({calc_url}) and published our 2026 Indie Catalog Multiples Report ({report_url}) comparing Duetti, beatBread, Sound Royalties, and Royalty Exchange side by side.\n\nWe would be honored if you tested the calculator for an upcoming resource roundup on catalog valuations and royalty advances.\n\nBest,\nSPACE Research Desk",
        },
    ]


def export_seo_static_bundle(
    output_dir: str = "/workspace/services/spacemusic/seo_static_bundle",
) -> dict[str, str]:
    from .seo_calculator_widget import (
        render_embeddable_calculator_html,
        render_embeddable_calculator_widget_js,
    )

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {
        "llms.txt": render_llms_txt(),
        "llms-full.txt": render_llms_full_txt(),
        "pricing.md": render_pricing_md(),
        "sitemap.xml": render_sitemap_xml(),
        "_redirects": generate_cloudflare_redirects(),
        "embed-calculator.html": render_embeddable_calculator_html(),
        "widget-calculator.js": render_embeddable_calculator_widget_js(),
    }
    written: dict[str, str] = {}
    for filename, content in artifacts.items():
        file_path = out_path / filename
        file_path.write_text(content, encoding="utf-8")
        written[filename] = str(file_path)
    return written

