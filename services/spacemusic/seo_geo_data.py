"""SEO, GEO (Generative Engine Optimization), JSON-LD, and programmatic landing page data for SPACE (spacemusic.io)."""

from __future__ import annotations

import json
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
        "Explore music catalog valuation scenarios across Hip-Hop, Pop, Latin, R&B, Country, Electronic, Classical & Ambient. Direct principal offers (0% seller fee) and 8 institutional syndicate partners ($3K to $5M LTM).",
        "All-Genre Music Catalog Valuation, Forensics & Institutional M&A Marketplace",
        "music catalog valuation",
        ["Stage 1 Scenario Calculator", "Stage 2 DCF + DTW Underwriting", "11-Point AI & Bot Forensics"],
    ),
    "/calculator/": _meta(
        "/calculator/",
        "Free Music Royalty & Catalog Valuation Calculator (2026 Multiples) | SPACE",
        "Model your master and publishing catalog sale scenarios in 60 seconds, then upgrade to statement-verified DCF + DTW forensic underwriting (4.5x to 16.5x LTM reference benchmarks).",
        "Interactive Music Catalog & Royalty Scenario Valuation Calculator",
        "music royalty calculator",
        ["Instant Stage 1 Scenario Model", "Statement-Verified Stage 2 DCF", "Zero Login Required"],
    ),
    "/guides/music-catalog-valuation-2026/": _meta(
        "/guides/music-catalog-valuation-2026/",
        "Music Catalog Valuation in 2026: 4.5x to 16.5x Multiples by Genre & Age | SPACE",
        "Complete 2026 underwriting guide to music catalog valuation. See reference LTM multiples, streaming decay curves, DSP RPM rates, and 11-point fraud checks across all 8 genre cohorts.",
        "Music Catalog Valuation Guide (2026): Multiples, Decay Curves & Underwriting",
        "music catalog valuation multiples 2026",
        ["2026 Genre Multiple Benchmarks", "DCF Formula Breakdown", "Buyer Term Sheet Comparison"],
    ),
    "/compare/spotify-vs-apple-music-royalties/": _meta(
        "/compare/spotify-vs-apple-music-royalties/",
        "Spotify vs Apple Music Royalties (2026): Per-Stream Rates & Catalog Multiples | SPACE",
        "2026 net payout per 1,000 streams (RPM) model benchmarks for Spotify ($2.95), Apple Music ($6.80), YouTube Content ID ($0.85), and Amazon Music ($4.60), plus how DSP mix impacts catalog valuation.",
        "Spotify vs Apple Music Royalties (2026): RPM Rates & Catalog Valuation Impact",
        "spotify vs apple music royalties",
        ["2026 Net RPM Table", "1,000-Threshold Impact", "Valuation Uplift Calculator"],
    ),
    "/compare/space-vs-royalty-exchange/": _meta(
        "/compare/space-vs-royalty-exchange/",
        "SPACE vs Royalty Exchange vs Duetti vs beatBread (2026 Fee & Multiple Comparison)",
        "Side-by-side comparison of SPACE, Royalty Exchange, Duetti, beatBread, Sound Royalties, and ANote Music: 0% direct principal seller fee vs 2.5%-4.0% syndicated placement, LTM minimums, and 5-7 business day offers.",
        "SPACE vs Royalty Exchange, Duetti & beatBread: 2026 Music M&A Platform Comparison",
        "royalty exchange alternatives",
        ["0% Direct Principal Fee", "5-7 Day Verified Offers", "Airwallex Split-Escrow Closing"],
    ),
    "/brand-facts/": _meta(
        "/brand-facts/",
        "SPACE (spacemusic.io) Brand Facts, Methodology & Institutional Buyer Network",
        "Verified machine-readable reference for SPACE (spacemusic.io): two-stage catalog underwriting, 0% seller fee on direct principal offers, 11-point forensics, and 8 institutional syndicate partners.",
        "SPACE (spacemusic.io) Official Brand Facts & Underwriting Methodology",
        "spacemusic.io brand facts",
        ["Two-Stage Underwriting", "11-Point Forensics Engine", "$3,000 to $5,000,000 LTM Coverage"],
    ),
    "/data/music-catalog-deals/": _meta(
        "/data/music-catalog-deals/",
        "Music Catalog Deals Database (2020 to 2026): 65+ Verified Multiples & Buyers | SPACE",
        "Explore publicly reported indie and iconic music catalog acquisitions from $10K to $1.2B. Filter by genre, LTM multiple, catalog age, and buyer (Duetti, Hipgnosis, Primary Wave, Sony).",
        "Music Catalog Deals & Multiples Database (2020 to 2026)",
        "music catalog deals database",
        ["Publicly Reported Transactions", "Indie & Major Multiples", "Downloadable Benchmark Data"],
    ),
    "/data/indie-catalog-multiples-ai-fraud-report-2026/": _meta(
        "/data/indie-catalog-multiples-ai-fraud-report-2026/",
        "2026 Indie Music Catalog Multiples & AI Fraud Benchmark Report | SPACE Underwriting Model Parameters",
        "SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026): DCF genre multiples, decay curves, WACC bands, DSP net RPM assumptions, and 11-point DTW fraud penalty parameters.",
        "2026 Indie Music Catalog Valuation Multiples & AI Stream-Farming Benchmark Report",
        "indie music catalog valuation multiples report 2026",
        ["Model Parameters & Reference Benchmarks", "DTW & Bot Penalty Formulas", "8-Genre WACC & Decay Table"],
    ),
    "/valuation-memo/": _meta(
        "/valuation-memo/",
        "SPACE Institutional Catalog Valuation Memo Studio | Claude + Autumn Billing + DTW DCF",
        "Self-serve Stage 2 institutional 19-slide 16:9 catalog valuation memo studio powered by SPACE Monte Carlo DCF, Dynamic Time Warping (DTW), and TypeSafe AI (JEV) forensics.",
        "Generate Catalog Investment Memo",
        "music catalog valuation memo",
        ["19-Slide 16:9 Investment Memo", "DTW + JEV Forensics Audit", "24-48h Expedited Memo Turnaround"],
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
            meta_description=f"Value and sell your {label} master or publishing catalog on SPACE. Stage 1 interactive scenario calculator ({mult} reference range), Stage 2 CSV DCF + DTW underwriting in 5-7 business days (24-48h expedited memo), 0% direct principal seller fee or syndicated offers from {', '.join(buyers[:3])}.",
            h1=f"Sell Your {label} Music Catalog: 2026 Valuation Multiples & Institutional Buyers",
            hero_subtitle=f"Explore an instant Stage 1 indicative scenario range on /calculator/ for your {label} tracks or catalog ({ltm} LTM), then upload distributor/PRO CSV statements for Stage 2 DCF + DTW forensic underwriting. Direct principal acquisition offers carry a 0% seller platform fee and arrive typically within 5-7 business days (with expedited 24-48 hour forensic memo turnaround and optional syndicated institutional placement across 8 buyers).",
            typical_multiple_range=mult,
            typical_ltm_range=ltm,
            annual_decay_benchmark=decay,
            top_matched_buyers=buyers,
            export_or_underwriting_steps=[
                f"Stage 1 (Initial Intake & Scenario Calculator): Explore indicative sale scenarios on /calculator/ (monthly net income x 12 x assumed multiple x share sold) and submit your initial {label} intake on /apply/.",
                "Stage 2 (Statement-Verified Underwriting): Upload 12 to 36 months of CSV royalty statements from your distributor or PRO so SPACE can run full DCF + Dynamic Time Warping (DTW) forensic underwriting (/valuation-memo/).",
                "Acquisition Offer & Closing: Receive a statement-verified valuation and acquisition offer typically within 5-7 business days (expedited 24-48 hour forensic memo turnaround available). Direct principal offers from SPACE carry a 0% seller platform fee; optional syndicated institutional placement carries a transparent 2.5%-4.0% closing fee only upon a completed sale.",
            ],
            faq_items=[
                {
                    "question": f"What multiple do {label} music catalogs sell for in 2026?",
                    "answer": f"Under SPACE's 2026 underwriting model parameters and reference benchmarks, statement-verified {label} catalogs typically calibrate between {mult} depending on catalog age, playlist diversification, and organic listener retention. Use /calculator/ for an interactive scenario estimate before full Stage 2 DCF + DTW underwriting.",
                },
                {
                    "question": f"How do SPACE's two-stage underwriting timeline and seller fees work for {label} catalogs?",
                    "answer": f"Stage 1 provides an instant scenario range on /calculator/ and free intake review on /apply/. After you upload distributor/PRO CSV statements in Stage 2, SPACE delivers a statement-verified DCF + forensic underwriting offer typically within 5-7 business days (with 24-48 hour expedited memo turnaround on /valuation-memo/). Direct principal acquisition offers from SPACE have a 0% seller platform fee, while optional syndicated placement with partners such as {', '.join(buyers[:3])} carries a 2.5%-4.0% closing fee only upon a completed transaction.",
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
            meta_description=f"Export your {label} royalty CSV statements, explore Stage 1 scenarios on /calculator/ ({mult} reference range), and receive Stage 2 statement-verified DCF + DTW underwriting offers in 5-7 business days (0% direct principal seller fee or syndicated bids from {', '.join(buyers[:3])}).",
            h1=f"Sell Your {label} Music Royalties: 2026 Multiples, CSV Export & Buyer Matching",
            hero_subtitle=f"Turn your {label} streaming earnings ({ltm} LTM) into immediate capital. Start with an instant Stage 1 scenario estimate on /calculator/ or /apply/, then upload native {label} CSV exports in Stage 2 for full DCF + DTW forensic underwriting and an acquisition offer in 5-7 business days (with expedited 24-48 hour forensic memo turnaround available).",
            typical_multiple_range=mult,
            typical_ltm_range=ltm,
            annual_decay_benchmark=decay,
            top_matched_buyers=buyers,
            export_or_underwriting_steps=[
                f"Stage 1 (Scenario Calculator & Intake): Model an indicative sale scenario on /calculator/ and submit your initial {label} catalog review on /apply/.",
                f"Stage 2 (CSV Statement Verification): Download your trailing 12 to 36 month detailed CSV royalty report from your {label} dashboard and upload it for ISRC-level DCF + DTW forensic underwriting.",
                f"Offer & Settlement: Receive a statement-verified acquisition offer typically within 5-7 business days (with 24-48 hour expedited forensic memo turnaround on /valuation-memo/). Direct principal offers have a 0% seller fee; optional syndicated institutional placement with {', '.join(buyers[:3])} carries a 2.5%-4.0% closing fee only upon closing.",
            ],
            faq_items=[
                {
                    "question": f"Can I sell my {label} streaming royalties without losing all my songs?",
                    "answer": f"Yes. Through SPACE you can evaluate selling 50%, 75%, or 100% of defined catalog rights, individual ISRCs, or compare optional institutional structures starting at $3,000 LTM.",
                },
                {
                    "question": f"How fast does a {label} catalog review and buyout work on SPACE?",
                    "answer": "Stage 1 provides an instant interactive scenario estimate on /calculator/ and free initial intake on /apply/. In Stage 2, after uploading your distributor/PRO CSV statements, SPACE runs DCF + DTW forensic underwriting and delivers a statement-verified valuation and acquisition offer typically within 5-7 business days (with expedited 24-48 hour forensic memo turnaround available for statement-verified catalogs). Direct principal offers carry a 0% seller platform fee, while optional syndicated institutional placement carries a 2.5%-4.0% closing fee only upon a completed sale.",
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
        "@context": "https://schema.org",
        "@type": "Organization",
        "brand_name": "SPACE",
        "name": "SPACE",
        "legal_domain": "spacemusic.io",
        "url": f"{SITE_URL}/",
        "canonical_url": f"{SITE_URL}/brand-facts/",
        "last_updated": LAST_MODIFIED,
        "lastUpdated": LAST_MODIFIED,
        "category": "Direct music rights buyer & institutional catalog underwriting platform",
        "positioning": "Two-Stage Music Catalog Underwriting, Direct Acquisition (0% Seller Fee) & Institutional Syndicate Placement Platform",
        "description": (
            "SPACE operates a two-stage music catalog underwriting and acquisition process across all genres. "
            "Stage 1 provides an instant interactive scenario estimate on /calculator/ and free initial intake review on /apply/. "
            "Stage 2 runs statement-verified DCF + DTW forensic underwriting on uploaded distributor/PRO CSV statements and delivers a statement-verified valuation and acquisition offer typically within 5-7 business days (with expedited 24-48 hour forensic memo turnaround available for statement-verified catalogs). "
            "Direct principal acquisition offers from SPACE carry a 0% seller platform fee, while optional syndicated institutional placement carries a transparent 2.5%-4.0% closing fee only upon a completed sale."
        ),
        "supported_genre_cohorts": ALL_GENRE_COHORTS,
        "ltm_coverage_range_usd": {"catalog_sale_min": 3000, "catalog_sale_max": 5000000, "royalty_advance_min": 2500},
        "service": {
            "name": "Two-stage music catalog underwriting & acquisition",
            "applicationUrl": f"{SITE_URL}/apply/",
            "calculatorUrl": f"{SITE_URL}/calculator/",
            "valuationMemoStudioUrl": f"{SITE_URL}/valuation-memo/",
            "freeApplication": True,
            "listingFee": 0,
            "auctionCommission": 0,
            "directPrincipalSellerFeePct": 0.0,
            "optionalSyndicatedPlacementFeePctRange": "2.5% to 4.0% (only upon completed syndicated sale)",
            "partialSalesAvailable": True,
            "availableShares": [50, 75, 100],
            "initialOfferTimeline": "Typically 5-7 business days after distributor/PRO CSV statement verification (expedited 24-48 hour forensic memo turnaround available for statement-verified catalogs)",
            "paymentMethod": "Bank transfer / Airwallex Split-Escrow with Letter of Direction (LOD)",
        },
        "two_stage_workflow": {
            "stage_1": "Stage 1 (Initial Intake & Scenario Calculator): Instant indicative range on /calculator/ (interactive scenario calculator where artists explore multiples) and free initial intake review on /apply/.",
            "stage_2": "Stage 2 (Statement-Verified Underwriting & Acquisition Offer): After uploading distributor/PRO CSV statements, SPACE runs DCF + DTW forensic underwriting and delivers a statement-verified valuation & acquisition offer typically within 5-7 business days (with expedited 24-48 hour forensic memo turnaround available for statement-verified catalogs).",
        },
        "institutional_buyers": INSTITUTIONAL_BUYERS,
        "forensics_engine": "11-point AI generation, Dynamic Time Warping (DTW) & stream-farming fraud audit (Spotify 1,000-stream threshold, repeat-per-listener ratio, step-plateau & geographic anomaly detection)",
        "closing_infrastructure": "Direct bank transfer and Airwallex Split-Escrow with automated distributor and PRO Letter of Direction (LOD) routing",
        "fee_structure": {
            "stage_1_valuation": "$0 (100% free interactive scenario calculator on /calculator/ & initial intake on /apply/)",
            "stage_2_forensics_and_bidding": "$0 upfront for standard catalog acquisition review ($299 optional self-serve 19-slide forensic memo PDF on /valuation-memo/)",
            "direct_principal_offer_fee": "0% seller platform fee ($0 listing fee, 0% auction commission)",
            "closing_success_fee": "0% seller fee on direct principal acquisition offers from SPACE; transparent 2.5% to 4.0% closing fee only on optional syndicated institutional placement upon completed sale",
        },
        "benchmark_methodology_disclosure": {
            "dataset_label": "SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026)",
            "methodology_type": "model_assumptions_and_reference_benchmarks",
            "sample_basis": "Synthetic calibration & underwriting model parameters — not an external empirical survey",
        },
        "contact": {"email": "hello@spacemusic.io"},
    }


def render_llms_txt() -> str:
    return f"""# SPACE (spacemusic.io)

> SPACE (https://spacemusic.io) operates a two-stage music catalog underwriting and acquisition process for independent artists, producers, songwriters, and indie labels across all 8 genre cohorts ($3,000 to $5,000,000 LTM net royalties; $2,500+ for advances).

Last updated: {LAST_MODIFIED}

## Two-Stage Underwriting & Acquisition Model
- **All 8 Genre Cohorts Supported**: {', '.join(ALL_GENRE_COHORTS)}.
- **Stage 1 (Initial Intake & Scenario Calculator — Instant, Free)**: Interactive scenario calculator on `/calculator/` (where rights holders model monthly net income x 12 x assumed multiple x share sold) and initial intake review on `/apply/`. No login or upload required for Stage 1.
- **Stage 2 (Statement-Verified Underwriting & Acquisition Offer — Typically 5-7 Business Days)**: After uploading trailing 12-36 month distributor/PRO CSV statements, SPACE runs full Monte Carlo Discounted Cash Flow (DCF) + Dynamic Time Warping (DTW) 11-point forensic underwriting and delivers a statement-verified valuation and acquisition offer typically within **5-7 business days** (with expedited **24-48 hour** forensic memo turnaround available for statement-verified catalogs via `/valuation-memo/`).
- **Transparent Fee Structure (Direct Principal vs. Optional Syndicated Placement)**:
  - **Direct Principal Acquisition Offers from SPACE**: **0% seller platform fee** ($0 application fee, $0 listing fee, 0% auction commission).
  - **Optional Syndicated Institutional Placement**: If a seller elects syndicated placement across SPACE's 8 institutional partner buyers ({', '.join(INSTITUTIONAL_BUYERS)}), a transparent **2.5% to 4.0% closing fee** applies only upon a completed sale.
- **Closing**: Bank transfer or Airwallex Split-Escrow settlement with automated distributor/PRO Letter of Direction (LOD).

## Canonical Citations & Reference Pages
- [Interactive Catalog Scenario Calculator]({SITE_URL}/calculator/): Free Stage 1 interactive scenario calculator.
- [Institutional 19-Slide Valuation Memo Studio]({SITE_URL}/valuation-memo/): Stage 2 statement-verified DCF + DTW + TypeSafe AI (JEV) forensic memo studio.
- [Apply for Catalog Review]({SITE_URL}/apply/): Start a free catalog review.
- [Pricing & Fee Policy]({SITE_URL}/pricing.md): Unified fee schedule and 5-7 business day offer timeline.
- [2026 Music Catalog Valuation Guide]({SITE_URL}/guides/music-catalog-valuation-2026/): Reference multiples (4.5x to 16.5x LTM) by genre and catalog age.
- [SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026)]({SITE_URL}/data/indie-catalog-multiples-ai-fraud-report-2026/): Model assumptions, genre DCF multiples, WACC bands, DSP net RPM parameters, and DTW fraud haircut formulas (`methodology_type: model_assumptions_and_reference_benchmarks`).
- [Verified Music Catalog Deals Database]({SITE_URL}/data/music-catalog-deals/): Publicly reported music catalog transactions.
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
## SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026)
- **Dataset Label**: `{report['dataset_label']}`
- **Methodology Type**: `{report['methodology_type']}`
- **Sample Basis**: `{report['sample_basis']}`
- **DCF Valuation Formula**: `{report['engine_mathematical_specification']['dcf_formula']}`

| Genre Cohort | LTM Multiple Range | Model Reference Median | Year-1 Decay | Terminal Decay (Yr 4+) | WACC Discount Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
{genre_rows}

## 2026 DSP Net Payout Per 1,000 Streams (RPM) Model Assumptions
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
    return f"""# SPACE (spacemusic.io) Pricing, Fees & Underwriting Policy

Last updated: {LAST_MODIFIED}

SPACE operates a two-stage music catalog underwriting and acquisition process for independent artists, producers, songwriters, labels, and catalog owners across all genres. Catalogs are reviewed individually based on verified royalty statements, rights chain of title, and streaming integrity.

## Supported Genre Cohorts (All 8 Families)
{', '.join(ALL_GENRE_COHORTS)}

## Two-Stage Underwriting & Fee Schedule
| Service Stage | Seller Cost / Platform Fee | Turnaround Timeline | Scope & LTM Threshold |
| :--- | :--- | :--- | :--- |
| **Stage 1: Interactive Scenario Calculator & Initial Intake** | **$0 (100% Free)** | Instant (`/calculator/`) / Initial intake (`/apply/`) | Explore assumed multiples on `/calculator/` or submit initial catalog details on `/apply/` |
| **Stage 2: Statement-Verified DCF + Forensic Underwriting** | **$0 Upfront** for acquisition review ($299 optional self-serve 19-slide forensic memo PDF on `/valuation-memo/`) | **Typically 5-7 business days** after CSV statement verification (**24-48 hours** expedited forensic memo turnaround) | Upload 12-36 months of distributor/PRO CSV statements ($3,000 to $5,000,000 LTM; $2,500+ for advances) |
| **Direct Principal Acquisition Offer (SPACE Direct Buyer)** | **0% Seller Platform Fee** ($0 listing fee, 0% auction commission) | Offer in **5-7 business days**; closing in 5-14 business days after agreement & LOD | Direct lump-sum purchase of 50%, 75%, or 100% of defined catalog rights |
| **Optional Syndicated Institutional Placement** | **2.5% to 4.0% closing fee** (only upon a completed syndicated sale; 0% if buyer-paid or if no offer is accepted) | Expedited **24-48 hour** forensic memo + multi-buyer syndicate routing | Optional placement across SPACE's 8 institutional syndicate partners |

## Seller Costs Summary
- Application & Stage 1 scenario modeling: Free ($0)
- Initial catalog review: Free ($0)
- Listing fee: $0 / EUR 0
- Auction commission on direct principal offers: 0%
- Optional syndicated institutional placement fee: 2.5% to 4.0% closing fee only upon a completed syndicated sale
- Obligation to accept an offer: None

## How an Offer is Determined
- **Stage 1 (`/calculator/`)** is an interactive scenario calculator where visitors model monthly net income x 12 x an assumed multiple x share sold. It is an illustrative scenario tool, not a binding valuation or purchase offer.
- **Stage 2 (`/apply/` & `/valuation-memo/`)** runs SPACE's full Discounted Cash Flow (DCF), Dynamic Time Warping (DTW), and 11-point streaming forensics engine on uploaded distributor and PRO CSV statements.
- Reference multiples published in **SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026)** (`/data/indie-catalog-multiples-ai-fraud-report-2026/`) represent SPACE's calibrated underwriting model parameters, decay curves, and WACC bands, not guaranteed offers or an external empirical survey.

## Partial Catalog Sales
Sellers can review different transaction sizes, including 50%, 75%, or 100% of defined master or publishing rights.

## Timing and Payment
- Standard acquisition offer timeline: Typically 5-7 business days after relevant distributor/PRO CSV statements and catalog information are received and verified
- Expedited forensic memo turnaround: 24-48 hours for statement-verified catalogs via `/valuation-memo/`
- Payment method: Bank transfer or Airwallex Split-Escrow with Letter of Direction (LOD) after agreement execution and rights-transfer verification

## Institutional Syndicate Partner Thresholds
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
            "question": "How long does SPACE take to deliver catalog valuation and acquisition offers?",
            "answer": "Stage 1 provides an instant scenario range on /calculator/ and free initial intake on /apply/. In Stage 2, after uploading distributor/PRO CSV statements, SPACE runs DCF + DTW forensic underwriting and delivers a statement-verified valuation and acquisition offer typically within 5-7 business days (with expedited 24-48 hour forensic memo turnaround available for statement-verified catalogs). Direct principal offers carry a 0% seller platform fee; optional syndicated institutional placement carries a 2.5%-4.0% closing fee only upon a completed sale.",
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
        "title": "2026 Indie Music Catalog Valuation Multiples & AI Stream-Farming Benchmark Report — SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026)",
        "dataset_label": "SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026)",
        "methodology_type": "model_assumptions_and_reference_benchmarks",
        "sample_basis": "Synthetic calibration & underwriting model parameters — not an external empirical survey",
        "is_synthetic_reference_benchmark": True,
        "canonical_url": f"{SITE_URL}{report_path}",
        "published_date": LAST_MODIFIED,
        "ltm_range_analyzed_usd": "$3,000 to $5,000,000",
        "engine_mathematical_specification": {
            "dcf_formula": "V = sum_{t=1..10} [ CF_0 * prod_{k=1..t}(1 - d_k) / (1 + WACC)^t ]",
            "decay_model": "Age- and genre-calibrated two-regime decay curve (Year-1 front-loaded decay d_1 transitioning to terminal decay d_term from Year 4+)",
            "wacc_build_up": "WACC = r_f (4.00%) + ERP (4.50%) + illiquidity_premium (1.50%) + concentration_adjustment + dsp_geo_adjustment + fraud_penalty",
            "dtw_and_fraud_penalty": "Dynamic Time Warping (DTW) cross-track synchrony (>0.85), artificial step-plateau detection, and TypeSafe AI (JEV) fraud probability (>0.40) increase WACC by +150 to +300 bps and apply a 25% to 55% valuation haircut.",
        },
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
            {"dsp": "Apple Music", "net_rpm_per_1000_streams_usd": 6.80, "valuation_weight_impact": "+8% to +14% model multiple uplift for >30% revenue share"},
            {"dsp": "Tidal", "net_rpm_per_1000_streams_usd": 8.40, "valuation_weight_impact": "High lossless ARPU reference rate, niche volume"},
            {"dsp": "Amazon Music", "net_rpm_per_1000_streams_usd": 4.60, "valuation_weight_impact": "+4% to +7% model multiple uplift for strong US/EU share"},
            {"dsp": "Deezer", "net_rpm_per_1000_streams_usd": 3.90, "valuation_weight_impact": "Artist-centric reference model parameter"},
            {"dsp": "Spotify", "net_rpm_per_1000_streams_usd": 2.95, "valuation_weight_impact": "Baseline model benchmark; tracks <1,000 annual streams earn $0"},
            {"dsp": "YouTube Content ID / Shorts", "net_rpm_per_1000_streams_usd": 0.85, "valuation_weight_impact": "-10% to -18% model discount if >50% of LTM due to claim volatility"},
        ],
        "forensics_findings_2026": {
            "methodology_note": "SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026) — deterministic penalty calibration, not an external empirical survey.",
            "total_checks_in_protocol": 11,
            "model_flagged_anomaly_reference_rate_pct": 18.4,
            "model_valuation_haircut_when_flagged_pct": 34.0,
            "verified_clean_catalog_multiple_premium_pct": 14.2,
            "spotify_sub_1000_stream_isrc_demonetization_reference_loss_pct": 6.8,
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
            "body": f"Hi beatBread Partnerships Team,\n\nWe just published the SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026) at {report_url}, where beatBread is featured as a top institutional advance provider for artists wanting to retain ownership.\n\nOur free Stage 1 scenario calculator ({calc_url}) helps artists explore scenarios across all 8 genre cohorts ($2,500 to $3,000,000 LTM) before Stage 2 CSV verification and 11-point stream-farming forensics. Would you be open to linking our 2026 model benchmark table in your artist education resources and setting up direct API lead routing?\n\nBest,\nSPACE Institutional Partnerships",
        },
        {
            "target_partner": "ANote Music",
            "target_url": "https://anotemusic.com",
            "angle": "Fractional catalog valuation benchmark citation & European deal flow",
            "subject": "ANote Music citation in SPACE 2026 Music Catalog Valuation Benchmark Report",
            "body": f"Hi ANote Music Team,\n\nWe included ANote Music in our SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026) ({report_url}) and our platform comparison hub. Because SPACE underwrites catalogs across Pop, Rock, Classical, and Latin ($20K to $3M LTM) with a standardized 11-point fraud certificate, our sellers frequently ask about fractional listing options on ANote.\n\nFeel free to cite or embed our 2026 genre decay and DSP RPM reference parameters in your investor blog, and let us know if we can formalize a partner referral badge.\n\nBest,\nSPACE Institutional Partnerships",
        },
        {
            "target_partner": "Symphonic Distribution",
            "target_url": "https://symphonic.com",
            "angle": "Dedicated Symphonic CSV valuation guide + Latin/Afrobeats/Electronic benchmark data",
            "subject": "New Symphonic Royalty Valuation Guide & 2026 Genre Multiples Dataset",
            "body": f"Hi Symphonic Editorial & Partnerships Team,\n\nWe built a dedicated valuation workflow for Symphonic rights holders ({SITE_URL}/sell/sell-symphonic-royalties/) alongside our SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026) ({report_url}), highlighting Latin, Afrobeats, and Electronic DCF reference multiples (6.0x to 14.5x LTM).\n\nIf useful for the Symphonic blog, you are welcome to reference our 2026 genre multiples table or link to the free Stage 1 scenario calculator ({calc_url}) for artists evaluating catalog financing.\n\nBest,\nSPACE Institutional Partnerships",
        },
        {
            "target_partner": "Duetti",
            "target_url": "https://duetti.co",
            "angle": "Track-level & catalog M&A pre-screening ($3K to $1.5M LTM) with 11-point forensics",
            "subject": "SPACE 2026 Indie Catalog Multiples Report: Duetti buyer profile & ISRC forensics",
            "body": f"Hi Duetti Acquisitions Team,\n\nSPACE ({SITE_URL}) features Duetti across our 20 genre and distributor valuation pages as a premier buyer for $3,000 to $1,500,000 LTM track and catalog deals. Every Stage 2 seller on SPACE uploads 12 to 36 months of distributor CSVs and passes our 11-point AI and bot stream-farming check.\n\nWe just released our SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026) ({report_url}) documenting our 8-genre DCF decay curves and DTW fraud penalty parameters. We would love to share the reference specification with your research team and coordinate partner backlinks.\n\nBest,\nSPACE Institutional Partnerships",
        },
        {
            "target_partner": "Music Business Worldwide",
            "target_url": "https://www.musicbusinessworldwide.com",
            "angle": "Technical underwriting specification: 2026 DCF decay curves, WACC bands, and DTW bot penalties",
            "subject": "TECHNICAL REPORT: SPACE publishes 2026 Indie Catalog Underwriting Model Parameters & DTW Fraud Benchmarks",
            "body": f"Hi MBW Editorial Team,\n\nSPACE just published our SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026) ({report_url}), documenting the exact DCF multiples, decay curves, WACC discount rates, and 11-point DTW fraud penalty parameters used in our catalog underwriting engine across 8 genre cohorts ($3K to $5M LTM).\n\nKey model parameters for MBW readers:\n1. Seasoned Country/Rock catalog reference parameters span 8.0x to 16.5x LTM (model median 11.6x, 8.9% WACC), while high-velocity Phonk/Hip-Hop calibrates at 4.5x to 11.5x (model median 7.4x, 11.5% WACC).\n2. Catalogs triggering our 11-point AI/stream-farming or step-plateau DTW flags receive a calibrated 34.0% model valuation haircut (+150 to +300 bps WACC penalty).\n3. Statement-verified catalogs passing all 11 forensic integrity checks qualify for up to a +14.2% model multiple premium.\n\nFull model parameters and methodology are open for citation at {report_url}.\n\nBest,\nSPACE Research Desk",
        },
        {
            "target_partner": "Ari's Take / Hypebot",
            "target_url": "https://aristake.com",
            "angle": "Creator-first guide & free Stage 1 scenario calculator for indie artists ($3K+ LTM)",
            "subject": "Free Music Catalog Valuation Scenario Calculator & 2026 Underwriting Benchmarks for Ari's Take",
            "body": f"Hi Ari's Take & Hypebot Editorial Team,\n\nIndie artists with $3,000 to $500,000 in annual streaming royalties rarely know how buyers model decay curves, WACC, and DSP mix. We launched a free, zero-login Stage 1 scenario calculator ({calc_url}) and published our SPACE Underwriting Model Parameters & Synthetic Reference Benchmarks (2026) ({report_url}) comparing direct principal acquisition (0% seller fee) with Duetti, beatBread, Sound Royalties, and Royalty Exchange.\n\nWe would be honored if you tested the calculator for an upcoming resource roundup on catalog valuations and royalty advances.\n\nBest,\nSPACE Research Desk",
        },
    ]


def render_landing_page_html(lp: LandingPageContent) -> str:
    schemas_html = "\n".join(
        f'<script type="application/ld+json">{json.dumps(s)}</script>'
        for s in build_page_jsonld_schemas(lp.canonical_path)
    )
    steps_html = "".join(f"<li>{step}</li>" for step in lp.export_or_underwriting_steps)
    faqs_html = "".join(
        f"<div style='margin-bottom:14px'><strong>{q['question']}</strong><p style='margin:4px 0 0;color:#cbd5e1'>{q['answer']}</p></div>"
        for q in lp.faq_items
    )
    buyers_str = ", ".join(lp.top_matched_buyers)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{lp.title}</title>
  <meta name="description" content="{lp.meta_description}" />
  <link rel="canonical" href="{SITE_URL}{lp.canonical_path}" />
  <meta property="og:title" content="{lp.title}" />
  <meta property="og:description" content="{lp.meta_description}" />
  <meta property="og:url" content="{SITE_URL}{lp.canonical_path}" />
  <meta property="og:type" content="website" />
  {schemas_html}
</head>
<body style="margin:0;padding:32px 20px;background:#0b0f19;color:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6">
  <main style="max-width:840px;margin:0 auto">
    <nav style="margin-bottom:24px;font-size:14px"><a href="{SITE_URL}/" style="color:#818cf8;text-decoration:none">SPACE</a> / <a href="{SITE_URL}/sell/" style="color:#818cf8;text-decoration:none">Sell Catalog</a> / <span>{lp.slug}</span></nav>
    <h1 style="font-size:32px;margin:0 0 12px">{lp.h1}</h1>
    <p style="font-size:18px;color:#cbd5e1;margin:0 0 24px">{lp.hero_subtitle}</p>
    <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:28px;background:#111827;padding:20px;border-radius:12px;border:1px solid #1e293b">
      <div><div style="font-size:12px;color:#94a3b8">2026 LTM Multiple Range</div><div style="font-size:20px;font-weight:700;color:#a5b4fc">{lp.typical_multiple_range}</div></div>
      <div><div style="font-size:12px;color:#94a3b8">Eligible LTM Range</div><div style="font-size:20px;font-weight:700">{lp.typical_ltm_range}</div></div>
      <div><div style="font-size:12px;color:#94a3b8">Decay Benchmark</div><div style="font-size:15px;font-weight:600">{lp.annual_decay_benchmark}</div></div>
    </section>
    <h2 style="font-size:22px">Matched Institutional Buyers</h2>
    <p style="color:#cbd5e1">{buyers_str}</p>
    <h2 style="font-size:22px">How to Value &amp; Sell in 3 Steps</h2>
    <ol style="color:#cbd5e1">{steps_html}</ol>
    <div style="margin:28px 0"><a href="{SITE_URL}/calculator/" style="display:inline-block;padding:12px 24px;background:#6366f1;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">Calculate Your Catalog Value in 60 Seconds</a></div>
    <h2 style="font-size:22px">Frequently Asked Questions</h2>
    {faqs_html}
  </main>
</body>
</html>"""


def render_benchmark_report_html() -> str:
    rep = get_indie_catalog_benchmark_report_2026()
    meta = SEO_PAGE_METADATA_OVERRIDES["/data/indie-catalog-multiples-ai-fraud-report-2026/"]
    schemas_html = "\n".join(
        f'<script type="application/ld+json">{json.dumps(s)}</script>'
        for s in rep["jsonld_schemas"]
    )
    rows_html = "".join(
        f"<tr><td style='padding:8px;border-bottom:1px solid #1e293b'>{g['genre_cohort']}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #1e293b'>{g['multiple_range_ltm']}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #1e293b'>{g['median_multiple']}x</td>"
        f"<td style='padding:8px;border-bottom:1px solid #1e293b'>{g['yr1_decay_pct']}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #1e293b'>{g['wacc_discount_rate']}</td></tr>"
        for g in rep["genre_multiples_table"]
    )
    spec = rep["engine_mathematical_specification"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{meta.title}</title>
  <meta name="description" content="{meta.meta_description}" />
  <link rel="canonical" href="{rep['canonical_url']}" />
  {schemas_html}
</head>
<body style="margin:0;padding:32px 20px;background:#0b0f19;color:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6">
  <main style="max-width:900px;margin:0 auto">
    <h1 style="font-size:30px">{rep['title']}</h1>
    <p style="color:#cbd5e1"><strong>Dataset Classification:</strong> {rep['dataset_label']} (<code>{rep['methodology_type']}</code>)</p>
    <p style="color:#cbd5e1"><strong>Sample Basis:</strong> {rep['sample_basis']} | Coverage: {rep['ltm_range_analyzed_usd']} LTM | Published: {rep['published_date']}</p>
    <section style="background:#111827;border:1px solid #1e293b;border-radius:10px;padding:16px;margin:20px 0">
      <h2 style="font-size:18px;margin:0 0 8px">SPACE Valuation Engine Mathematical Specification</h2>
      <p style="margin:4px 0;color:#cbd5e1"><strong>DCF Formula:</strong> <code>{spec['dcf_formula']}</code></p>
      <p style="margin:4px 0;color:#cbd5e1"><strong>Decay Curve:</strong> {spec['decay_model']}</p>
      <p style="margin:4px 0;color:#cbd5e1"><strong>WACC Build-Up:</strong> <code>{spec['wacc_build_up']}</code></p>
      <p style="margin:4px 0;color:#cbd5e1"><strong>DTW &amp; Forensics Haircut Rule:</strong> {spec['dtw_and_fraud_penalty']}</p>
    </section>
    <table style="width:100%;border-collapse:collapse;margin:24px 0;font-size:14px">
      <thead><tr style="text-align:left;border-bottom:2px solid #334155"><th style="padding:8px">Genre Cohort</th><th style="padding:8px">LTM Multiple Range</th><th style="padding:8px">Model Median</th><th style="padding:8px">Yr-1 Decay</th><th style="padding:8px">WACC</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    <p><a href="{SITE_URL}/calculator/" rel="dofollow" style="color:#818cf8">Run the Interactive Stage 1 Scenario Calculator</a> · <a href="{SITE_URL}/valuation-memo/" style="color:#818cf8">Open the Stage 2 19-Slide Valuation Memo Studio</a></p>
  </main>
</body>
</html>"""


def build_growth_data_pages_payload() -> dict[str, dict[str, Any]]:
    """
    Builds the native SPACE cream-UI (`growth-data`) page entries for `GrowthDataPage`
    covering all 20 `/sell/<slug>/` landing pages and `/data/indie-catalog-multiples-ai-fraud-report-2026/`,
    plus structured card metadata for `/sell/` (`sell/index.html` & `GenreIndex`).
    """
    h1_cls = "text-3xl md:text-5xl font-semibold tracking-tight mb-6 leading-[1.1]"
    h2_cls = "text-2xl md:text-3xl font-semibold tracking-tight mb-4 mt-12"
    p_cls = "text-muted-foreground leading-relaxed mb-4"
    tbl_cls = "w-full text-sm border-collapse"
    th_cls = "text-left py-3 pr-4 font-medium whitespace-nowrap"
    td_cls = "py-3 pr-4"

    pages: dict[str, dict[str, Any]] = {}
    sell_cards: list[dict[str, str]] = []

    for slug, lp in LANDING_PAGES_BY_SLUG.items():
        crumb_label = "All-Genre Catalog Guide" if lp.category == "genre" else "Distributor Royalty Guide"
        buyers_str = ", ".join(lp.top_matched_buyers)
        steps_li = "".join(f'<li class="mb-2">{s}</li>' for s in lp.export_or_underwriting_steps)
        faqs_details = "".join(
            f'<details class="border-b border-black/10">'
            f'<summary class="text-base font-medium py-4 text-left cursor-pointer">{q["question"]}</summary>'
            f'<p class="text-muted-foreground pb-4 leading-relaxed">{q["answer"]}</p>'
            f"</details>"
            for q in lp.faq_items
        )
        inner_html = (
            f'<p class="text-sm text-muted-foreground mb-6"><a href="/sell/" class="hover:underline">Sell</a> / {crumb_label}</p>'
            f'<h1 class="{h1_cls}">{lp.h1}</h1>'
            f'<p class="text-sm text-muted-foreground mb-8">By SPACE Editorial Team. Updated October 14, 2026.</p>'
            f'<p class="{p_cls}">{lp.hero_subtitle}</p>'
            f'<div class="overflow-x-auto my-6"><table class="{tbl_cls}" style="min-width:600px">'
            f'<thead><tr class="border-b border-black/10">'
            f'<th class="{th_cls}">2026 Indicative LTM Multiple</th>'
            f'<th class="{th_cls}">Eligible Annual Net Royalties</th>'
            f'<th class="{th_cls}">Decay &amp; Underwriting Benchmark</th>'
            f'<th class="{th_cls}">Matched Institutional Buyers</th>'
            f"</tr></thead><tbody>"
            f'<tr class="border-b border-black/[0.06]">'
            f'<td class="{td_cls}" style="vertical-align:top;white-space:nowrap"><strong>{lp.typical_multiple_range}</strong></td>'
            f'<td class="{td_cls}" style="vertical-align:top;white-space:nowrap">{lp.typical_ltm_range}</td>'
            f'<td class="{td_cls}" style="vertical-align:top">{lp.annual_decay_benchmark}</td>'
            f'<td class="{td_cls}" style="vertical-align:top">{buyers_str}</td>'
            f"</tr></tbody></table></div>"
            f'<h2 class="{h2_cls}">How to Value &amp; Sell Your Catalog in 3 Steps</h2>'
            f'<ol class="list-decimal pl-5 text-muted-foreground leading-relaxed mb-6">{steps_li}</ol>'
            f'<div class="flex flex-wrap gap-4 my-8">'
            f'<a href="/apply/" class="bg-brand text-white inline-flex px-5 py-3 rounded-md font-medium">Request a free catalog review &nbsp;&#8594;</a>'
            f'<a href="/calculator/" class="underline underline-offset-2 py-3 text-sm font-medium">Model a sale scenario in 60 seconds &#8594;</a>'
            f'<a href="/data/indie-catalog-multiples-ai-fraud-report-2026/" class="underline underline-offset-2 py-3 text-sm font-medium">2026 Multiples &amp; AI Forensics Report &#8594;</a>'
            f"</div>"
            f'<h2 class="{h2_cls}">Frequently Asked Questions</h2>'
            f'<div class="w-full">{faqs_details}</div>'
        )
        pages[lp.canonical_path] = {
            "title": lp.title,
            "description": lp.meta_description,
            "html": inner_html,
            "schema": build_page_jsonld_schemas(lp.canonical_path),
        }
        kicker = (
            lp.h1.replace("Sell Your ", "")
            .replace(" Catalog", "")
            .replace(" Music", "")
            .replace(" Royalties & Catalog", "")
            .replace(" Royalties", "")
            .strip()
        )
        sell_cards.append(
            {
                "slug": slug,
                "href": lp.canonical_path,
                "category": lp.category,
                "kicker": kicker,
                "title": f"{lp.h1} ({lp.typical_multiple_range})",
                "description": lp.hero_subtitle,
                "demand": f"Matched buyers: {buyers_str} ({lp.typical_ltm_range})",
                "use_case": lp.annual_decay_benchmark,
            }
        )

    rep = get_indie_catalog_benchmark_report_2026()
    rep_meta = SEO_PAGE_METADATA_OVERRIDES["/data/indie-catalog-multiples-ai-fraud-report-2026/"]
    cohort_rows = "".join(
        f'<tr class="border-b border-black/[0.06]">'
        f'<td class="{td_cls}" style="vertical-align:top;white-space:nowrap"><strong>{g["genre_cohort"]}</strong></td>'
        f'<td class="{td_cls}" style="vertical-align:top;white-space:nowrap">{g["multiple_range_ltm"]}</td>'
        f'<td class="{td_cls}" style="vertical-align:top;white-space:nowrap"><strong>{g["median_multiple"]}x</strong></td>'
        f'<td class="{td_cls}" style="vertical-align:top;white-space:nowrap">{g["yr1_decay_pct"]}</td>'
        f'<td class="{td_cls}" style="vertical-align:top;white-space:nowrap">{g["terminal_decay_pct"]}</td>'
        f'<td class="{td_cls}" style="vertical-align:top;white-space:nowrap">{g["wacc_discount_rate"]}</td>'
        f"</tr>"
        for g in rep["genre_multiples_table"]
    )
    dsp_rows = "".join(
        f'<tr class="border-b border-black/[0.06]">'
        f'<td class="{td_cls}" style="vertical-align:top;white-space:nowrap"><strong>{d["dsp"]}</strong></td>'
        f'<td class="{td_cls}" style="vertical-align:top;white-space:nowrap">${d["net_rpm_per_1000_streams_usd"]:.2f}</td>'
        f'<td class="{td_cls}" style="vertical-align:top">{d["valuation_weight_impact"]}</td>'
        f"</tr>"
        for d in rep["dsp_rpm_benchmarks"]
    )
    ff = rep["forensics_findings_2026"]
    spec = rep["engine_mathematical_specification"]
    findings_li = (
        f'<li class="mb-2"><strong>Methodology Classification:</strong> <code>{rep["dataset_label"]}</code> (<code>{rep["methodology_type"]}</code>) — {rep["sample_basis"]}.</li>'
        f'<li class="mb-2"><strong>DCF Valuation Formula:</strong> <code>{spec["dcf_formula"]}</code> with {spec["decay_model"]}.</li>'
        f'<li class="mb-2"><strong>WACC Build-Up:</strong> <code>{spec["wacc_build_up"]}</code>.</li>'
        f'<li class="mb-2"><strong>DTW &amp; Fraud Haircut Calibration:</strong> Catalogs triggering at least one of our {ff["total_checks_in_protocol"]} AI, step-plateau, or stream-farming flags receive a calibrated <strong>{ff["model_valuation_haircut_when_flagged_pct"]}%</strong> model valuation haircut (+150 to +300 bps WACC penalty).</li>'
        f'<li class="mb-2"><strong>Clean Catalog Premium:</strong> Statement-verified catalogs passing all {ff["total_checks_in_protocol"]} forensic integrity checks qualify for up to a <strong>+{ff["verified_clean_catalog_multiple_premium_pct"]}%</strong> model multiple uplift.</li>'
        f'<li class="mb-2"><strong>Spotify Sub-1,000 Stream Threshold Parameter:</strong> Sub-1,000 stream annual track demonetization is modeled at a reference LTM adjustment of <strong>{ff["spotify_sub_1000_stream_isrc_demonetization_reference_loss_pct"]}%</strong> for fragmented long-tail catalogs.</li>'
    )
    rep_html = (
        f'<p class="text-sm text-muted-foreground mb-6"><a href="/data/music-catalog-market-2026/" class="hover:underline">Data</a> / SPACE Underwriting Model Parameters &amp; Synthetic Reference Benchmarks (2026)</p>'
        f'<h1 class="{h1_cls}">{rep["title"]}</h1>'
        f'<p class="text-sm text-muted-foreground mb-8">By SPACE Research &amp; Underwriting Desk. Updated October 14, 2026. Basis: {rep["sample_basis"]} ({rep["ltm_range_analyzed_usd"]} LTM).</p>'
        f'<p class="{p_cls}">{rep_meta.meta_description}</p>'
        f'<h2 class="{h2_cls}">SPACE Underwriting Model Specification &amp; Reference Parameters (2026)</h2>'
        f'<ul class="list-disc pl-5 text-muted-foreground leading-relaxed mb-6">{findings_li}</ul>'
        f'<h2 class="{h2_cls}">2026 Model Reference Multiples, Decay Rates &amp; WACC by Genre Cohort</h2>'
        f'<div class="overflow-x-auto my-6"><table class="{tbl_cls}" style="min-width:760px">'
        f'<thead><tr class="border-b border-black/10">'
        f'<th class="{th_cls}">Genre Cohort</th>'
        f'<th class="{th_cls}">LTM Multiple Range</th>'
        f'<th class="{th_cls}">Model Median</th>'
        f'<th class="{th_cls}">Yr-1 Decay</th>'
        f'<th class="{th_cls}">Terminal Decay</th>'
        f'<th class="{th_cls}">WACC</th>'
        f"</tr></thead><tbody>{cohort_rows}</tbody></table></div>"
        f'<h2 class="{h2_cls}">DSP Net Payout RPM &amp; Underwriting Weight Assumptions (2026)</h2>'
        f'<div class="overflow-x-auto my-6"><table class="{tbl_cls}" style="min-width:640px">'
        f'<thead><tr class="border-b border-black/10">'
        f'<th class="{th_cls}">Streaming Platform (DSP)</th>'
        f'<th class="{th_cls}">Net RPM / 1,000 Streams (USD)</th>'
        f'<th class="{th_cls}">Underwriting &amp; Multiple Impact</th>'
        f"</tr></thead><tbody>{dsp_rows}</tbody></table></div>"
        f'<h2 class="{h2_cls}">How to Use These Model Reference Parameters</h2>'
        f'<p class="{p_cls}">These reference parameters document how SPACE calibrates genre decay curves, WACC bands, DSP mix weights, and DTW forensic haircuts during Stage 2 underwriting. Every catalog acquisition offer requires individual verification of distributor/PRO CSV statements (typically 5-7 business days after statement verification, with 24-48 hour expedited forensic memo turnaround available). '
        f'<a href="/calculator/" class="underline underline-offset-2">Explore a Stage 1 sale scenario on /calculator/</a>, '
        f'<a href="/valuation-memo/" class="underline underline-offset-2">open the 19-Slide Valuation Memo Studio</a>, '
        f'<a href="/sell/" class="underline underline-offset-2">browse all genre and distributor guides</a>, or '
        f'<a href="/apply/" class="underline underline-offset-2">request a free catalog review</a>.</p>'
    )
    pages["/data/indie-catalog-multiples-ai-fraud-report-2026/"] = {
        "title": rep_meta.title,
        "description": rep_meta.meta_description,
        "html": rep_html,
        "schema": rep["jsonld_schemas"],
    }

    return {"pages": pages, "sell_cards": sell_cards}


def export_seo_static_bundle(
    output_dir: str = "/workspace/services/spacemusic/seo_static_bundle",
) -> dict[str, str]:
    from .paid_memo_service import render_self_serve_valuation_studio_html
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
        "embed/calculator/index.html": render_embeddable_calculator_html(),
        "widget-calculator.js": render_embeddable_calculator_widget_js(),
        "widget/calculator.js": render_embeddable_calculator_widget_js(),
        ".well-known/brand-facts.json": json.dumps(get_brand_facts_payload(), indent=2),
        "data/indie-catalog-multiples-ai-fraud-report-2026/index.html": render_benchmark_report_html(),
        "valuation-memo/index.html": render_self_serve_valuation_studio_html(),
        "growth-data-pages.json": json.dumps(build_growth_data_pages_payload(), indent=2),
        "seo-metadata-manifest.json": json.dumps(
            {
                path: {
                    "metadata": meta.model_dump() if hasattr(meta, "model_dump") else meta.dict(),
                    "jsonld_schemas": build_page_jsonld_schemas(path),
                }
                for path, meta in SEO_PAGE_METADATA_OVERRIDES.items()
            },
            indent=2,
        ),
    }
    for slug, lp in LANDING_PAGES_BY_SLUG.items():
        artifacts[f"sell/{slug}/index.html"] = render_landing_page_html(lp)

    written: dict[str, str] = {}
    for filename, content in artifacts.items():
        file_path = out_path / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        written[filename] = str(file_path)
    return written

