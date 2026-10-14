"""
Zero-Touch Stage 1 Pipeline & Live DSP Enrichment Engine (`services/spacemusic/zero_touch_stage1.py`)

Automates the entire Stage 1 catalog screening workflow in <15 seconds when a Typeform
webhook (`xzx5SBJb` - SPACE catalog review) or direct application arrives:

1. Extracts Spotify Artist / Track / Album IDs from any URL format (or resolves via
   artist/label search fallback).
2. Enriches live DSP profile metadata (followers, monthly listeners, verified badge,
   external social links, top tracks with exact stream counts & durations, and full
   album/single release history + P-line labels).
3. Runs an Implied-Stream-to-Revenue Cross-Check ("Declared vs. Mathematical Stream Floor"):
   calculates what the artist's observed Spotify streams and monthly listener velocity can
   mathematically generate across all DSPs, catching fabricated revenue claims (e.g. claiming
   $144,000/yr with 9 monthly listeners) BEFORE requesting statements.
4. Injects Distributor-Specific Step-by-Step Export Guides into the Stage 1 reply email
   (tailored click-paths for DistroKid, TuneCore, UnitedMasters, Too Lost, Symphonic,
   CD Baby, Amuse, RouteNote, Proton, FUGA/The Orchard/Believe, or Sony/Universal/WMG).
5. Automatically Declines or Quarantines confirmed AI farms / spoofed profiles
   (`CONFIRMED_AI_OR_FARM` or extreme stream-to-revenue fabrication) so zero human
   underwriting time is wasted.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple

from pydantic import BaseModel, Field

from services.valuation.ai_profile_detector import (
    AuthenticityStatus,
    ReleaseMetadataItem,
)
from services.valuation.engine import (
    CatalogValuationInput,
    CatalogValuationOutput,
    RiskFlag,
    RiskSeverity,
    SpaceValuationEngine,
    TrackInput,
    convert_to_eur,
    load_rules,
)
from .models import CatalogApplication, ReplyDraft
from .typeform_adapter import (
    application_to_valuation_input,
    generate_reply_draft,
)


# ---------------------------------------------------------------------------
# 1. URL Extraction Helpers (Artist / Track / Album IDs)
# ---------------------------------------------------------------------------

def extract_spotify_reference(url: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts `(entity_type, spotify_id)` from a Spotify URL or URI.
    `entity_type` is one of `"artist"`, `"track"`, `"album"`, `"playlist"`, or `None`.
    """
    if not url:
        return None, None
    s = url.strip()
    m_web = re.search(
        r"open\.spotify\.com/(?:intl-[a-z]{2}/)?(artist|track|album|playlist)/([A-Za-z0-9]{22})",
        s,
    )
    if m_web:
        return m_web.group(1).lower(), m_web.group(2)

    m_uri = re.search(r"spotify:(artist|track|album|playlist):([A-Za-z0-9]{22})", s)
    if m_uri:
        return m_uri.group(1).lower(), m_uri.group(2)

    return None, None


# ---------------------------------------------------------------------------
# 2. Live DSP Profile Snapshot Schema & Normalization
# ---------------------------------------------------------------------------

class LiveSpotifyTrackItem(BaseModel):
    track_id: Optional[str] = None
    title: str
    duration_ms: int = 180_000
    total_streams: int = 0
    release_date: Optional[date] = None
    label: Optional[str] = None


class LiveSpotifyArtistSnapshot(BaseModel):
    spotify_artist_id: str
    artist_name: str
    verified: bool = False
    followers: int = 0
    monthly_listeners: int = 0
    external_social_links: List[str] = Field(default_factory=list)
    biography: Optional[str] = None
    top_tracks: List[LiveSpotifyTrackItem] = Field(default_factory=list)
    releases: List[ReleaseMetadataItem] = Field(default_factory=list)
    source: str = "live_spotify_api"


def _parse_iso_date_prefix(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    s = str(raw).strip()
    if len(s) >= 10:
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            pass
    if re.match(r"^\d{4}$", s):
        return date(int(s), 6, 15)
    return None


def parse_scrape_creators_spotify_payload(
    raw_payload: Dict[str, Any],
    fallback_artist_id: Optional[str] = None,
) -> LiveSpotifyArtistSnapshot:
    """
    Normalizes a raw Spotify artist JSON payload (such as ScrapeCreators / Treg
    `scrapecreators.x.v1-spotify-artist` or Spotify Web/Partner API format) into
    a structured `LiveSpotifyArtistSnapshot`.
    """
    data = (
        raw_payload.get("data")
        or raw_payload.get("result", {}).get("data")
        or raw_payload.get("result")
        or raw_payload
    )
    basic = data.get("artist_basic") or data

    uri = str(basic.get("uri") or basic.get("id") or fallback_artist_id or "")
    artist_id = uri.split(":")[-1] if ":" in uri else (uri or "unknown")
    artist_name = str(basic.get("name") or data.get("name") or "Unknown Artist")
    verified = bool(basic.get("verified", False))
    followers = int(basic.get("followers") or 0)
    monthly_listeners = int(basic.get("monthly_listeners") or 0)

    ext_links_raw = basic.get("external_links") or data.get("external_links") or []
    ext_links: List[str] = []
    for item in ext_links_raw:
        if isinstance(item, str):
            ext_links.append(item)
        elif isinstance(item, dict) and item.get("url"):
            ext_links.append(str(item["url"]))

    top_tracks: List[LiveSpotifyTrackItem] = []
    for t in data.get("top_tracks") or []:
        if not isinstance(t, dict):
            continue
        t_uri = str(t.get("uri") or t.get("id") or "")
        t_id = t_uri.split(":")[-1] if ":" in t_uri else (t_uri or None)
        playcount = t.get("playcount")
        if playcount is None:
            playcount = t.get("streams") or 0
        dur_ms = int(t.get("duration_ms") or 180_000)
        rel_dt = _parse_iso_date_prefix(t.get("release_date"))
        top_tracks.append(
            LiveSpotifyTrackItem(
                track_id=t_id,
                title=str(t.get("name") or t.get("title") or "Untitled"),
                duration_ms=dur_ms,
                total_streams=int(playcount or 0),
                release_date=rel_dt,
                label=t.get("label"),
            )
        )

    releases: List[ReleaseMetadataItem] = []
    for alb in data.get("albums") or []:
        if not isinstance(alb, dict):
            continue
        releases.append(
            ReleaseMetadataItem(
                title=str(alb.get("name") or alb.get("title") or "Untitled Album"),
                release_date=_parse_iso_date_prefix(alb.get("release_date")),
                release_type="ALBUM",
                track_count=int(alb.get("total_tracks") or alb.get("track_count") or 10),
                label=alb.get("label"),
            )
        )
    for sng in data.get("singles") or []:
        if not isinstance(sng, dict):
            continue
        releases.append(
            ReleaseMetadataItem(
                title=str(sng.get("name") or sng.get("title") or "Untitled Single"),
                release_date=_parse_iso_date_prefix(sng.get("release_date")),
                release_type="SINGLE",
                track_count=int(sng.get("total_tracks") or sng.get("track_count") or 1),
                label=sng.get("label"),
            )
        )

    return LiveSpotifyArtistSnapshot(
        spotify_artist_id=artist_id,
        artist_name=artist_name,
        verified=verified,
        followers=followers,
        monthly_listeners=monthly_listeners,
        external_social_links=ext_links,
        biography=basic.get("biography") or data.get("biography"),
        top_tracks=top_tracks,
        releases=releases,
    )


# ---------------------------------------------------------------------------
# 3. Implied-Stream-to-Revenue Cross-Check (Stage 1 Mathematical Floor)
# ---------------------------------------------------------------------------

class ImpliedRevenueCrossCheck(BaseModel):
    """
    Compares the seller's declared LTM revenue (`declared_ltm_eur`) against the
    mathematical ceiling of what their observed Spotify monthly listeners and
    cumulative top-track streams could plausibly generate across all DSPs.
    """

    declared_ltm_eur: float
    spotify_monthly_listeners: int
    top_tracks_cumulative_streams: int
    estimated_annual_spotify_streams: int
    estimated_all_dsp_ltm_ceiling_eur: float
    estimated_all_dsp_ltm_midpoint_eur: float
    declared_to_ceiling_ratio: float
    discrepancy_status: str = Field(
        default="PLAUSIBLE",
        description="PLAUSIBLE | ELEVATED_OFF_SPOTIFY_DEPENDENCY | EXTREME_FABRICATION_OR_MISMATCH",
    )
    explanation: str = ""
    recommended_haircut_pct: float = 0.0
    recommended_discount_bps: int = 0


def evaluate_implied_stream_revenue_crosscheck(
    *,
    declared_ltm_eur: float,
    spotify_monthly_listeners: Optional[int],
    top_tracks: Sequence[LiveSpotifyTrackItem],
    ownership_share_pct: float = 100.0,
    notes: Optional[str] = None,
) -> Optional[ImpliedRevenueCrossCheck]:
    """
    Computes an upper-bound and midpoint LTM royalty estimate from live Spotify metrics:
    - Each monthly listener generates ~3.2 streams/month on average (up to ~6.5 for high-repeat genres).
    - Top 10 tracks typically represent 60%–85% of an independent artist's total catalog streams.
    - Spotify typically represents 40%–75% of total global DSP revenue (unless catalog is primarily
      YouTube Content ID, sync/game soundtracks like Counter-Strike, or TikTok/Chinese DSPs).
    """
    if spotify_monthly_listeners is None and not top_tracks:
        return None
    if declared_ltm_eur <= 0:
        return None

    listeners = max(0, spotify_monthly_listeners or 0)
    top_streams_sum = sum(max(0, t.total_streams) for t in top_tracks)

    # Check if notes explicitly indicate non-Spotify dominant revenue (e.g. game soundtracks, sync, YouTube)
    notes_l = (notes or "").lower()
    has_non_spotify_driver = any(
        kw in notes_l
        for kw in ["counter-strike", "valve", "sync", "youtube", "television", "film", "game", "soundtrack", "physical"]
    )

    # 1. Estimate annual Spotify streams from monthly listeners (generous ceiling: 6.0 streams/listener/mo)
    annual_streams_from_listeners = listeners * 6.0 * 12.0

    # 2. Estimate annual Spotify streams from cumulative top-track streams (generous ceiling: 45% of lifetime top tracks earned in LTM, scaled by 1.5x for deep catalog)
    annual_streams_from_top_tracks = top_streams_sum * 0.45 * 1.5

    est_annual_spotify_streams = int(round(max(annual_streams_from_listeners, annual_streams_from_top_tracks)))

    # Midpoint vs generous ceiling RPM & multi-DSP multiplier
    # Midpoint: €0.0028/stream on Spotify, Spotify = 55% of all DSPs -> €0.0051 per Spotify stream across all DSPs
    # Ceiling:  €0.0038/stream on Spotify, Spotify = 30% of all DSPs -> €0.0127 per Spotify stream across all DSPs
    ownership_factor = max(0.01, min(1.0, ownership_share_pct / 100.0))
    midpoint_eur = max(150.0, est_annual_spotify_streams * 0.0051 * ownership_factor)
    ceiling_eur = max(500.0, est_annual_spotify_streams * 0.0135 * ownership_factor)

    if has_non_spotify_driver:
        # Allow 5x higher ceiling when sync / gaming / TV / YouTube is explicitly cited
        ceiling_eur = max(ceiling_eur * 5.0, 50_000.0)

    ratio = round(declared_ltm_eur / max(1.0, ceiling_eur), 2)

    if ratio >= 5.0 and listeners < 2_500 and top_streams_sum < 100_000 and not has_non_spotify_driver:
        status = "EXTREME_FABRICATION_OR_MISMATCH"
        haircut = 0.75
        bps = 400
        explanation = (
            f"Declared LTM (€{declared_ltm_eur:,.0f}) is {ratio:.1f}x higher than the generous all-DSP mathematical "
            f"ceiling (€{ceiling_eur:,.0f}/yr) implied by {listeners:,} Spotify monthly listeners and "
            f"{top_streams_sum:,} cumulative top-track streams."
        )
    elif ratio >= 2.0 and not has_non_spotify_driver:
        status = "ELEVATED_OFF_SPOTIFY_DEPENDENCY"
        haircut = 0.25
        bps = 175
        explanation = (
            f"Declared LTM (€{declared_ltm_eur:,.0f}) exceeds the Spotify-implied all-DSP ceiling (€{ceiling_eur:,.0f}/yr) "
            f"by {ratio:.1f}x — requires verification of non-Spotify revenue (Apple Music, YouTube Content ID, or Sync)."
        )
    else:
        status = "PLAUSIBLE"
        haircut = 0.0
        bps = 0
        explanation = (
            f"Declared LTM (€{declared_ltm_eur:,.0f}) is consistent with observed Spotify footprint "
            f"({listeners:,} monthly listeners, {top_streams_sum:,} cumulative top-track streams; "
            f"all-DSP ceiling €{ceiling_eur:,.0f}/yr)."
        )

    return ImpliedRevenueCrossCheck(
        declared_ltm_eur=round(declared_ltm_eur, 2),
        spotify_monthly_listeners=listeners,
        top_tracks_cumulative_streams=top_streams_sum,
        estimated_annual_spotify_streams=est_annual_spotify_streams,
        estimated_all_dsp_ltm_ceiling_eur=round(ceiling_eur, 2),
        estimated_all_dsp_ltm_midpoint_eur=round(midpoint_eur, 2),
        declared_to_ceiling_ratio=ratio,
        discrepancy_status=status,
        explanation=explanation,
        recommended_haircut_pct=haircut,
        recommended_discount_bps=bps,
    )


# ---------------------------------------------------------------------------
# 4. Distributor-Specific CSV Export Step-by-Step Instructions
# ---------------------------------------------------------------------------

DISTRIBUTOR_EXPORT_GUIDES: Dict[str, str] = {
    "distrokid": (
        "**How to export your DistroKid statement (takes ~30 seconds):**\n"
        "  1. Log in to **distrokid.com/bank** and click **\"See Excruciating Detail\"**.\n"
        "  2. Click the **Download (TSV/CSV)** icon in the top-right corner covering all available months.\n"
        "  3. Attach that raw `.tsv` or `.csv` file directly to your reply."
    ),
    "tunecore": (
        "**How to export your TuneCore sales report:**\n"
        "  1. Log in to TuneCore and go to **Money & Analytics → Sales Reports**.\n"
        "  2. Download the **Full Detailed CSV Sales Reports** for the last 24–36 months and attach them to your reply."
    ),
    "unitedmasters": (
        "**How to export your UnitedMasters statement:**\n"
        "  1. Open your UnitedMasters dashboard and go to **Wallet → Statements**.\n"
        "  2. Download the monthly **CSV Breakdown** files for the last 24 months and attach them to your reply."
    ),
    "too lost": (
        "**How to export your Too Lost royalty statements:**\n"
        "  1. Log in to your Too Lost portal and navigate to **Royalties → Statements / Analytics Export**.\n"
        "  2. Export the **Track/ISRC-level CSV** for the last 24–36 months and attach it to your reply."
    ),
    "symphonic": (
        "**How to export your Symphonic SMS statement:**\n"
        "  1. Log in to **SymphonicMS (SMS) → Royalties → Statements**.\n"
        "  2. Export the **Detailed CSV Royalty Report** (by ISRC, DSP, and territory) for the last 24–36 months."
    ),
    "cd baby": (
        "**How to export your CD Baby royalty report:**\n"
        "  1. Log in to CD Baby and go to **Sales & Reports → Accounting / Detailed Sales**.\n"
        "  2. Export the **CSV Sales History** for the last 24–36 months and attach it here."
    ),
    "amuse": (
        "**How to export your Amuse royalty data:**\n"
        "  1. Log in to **Amuse Web → Wallet / Royalties**.\n"
        "  2. Click **Export CSV** to download your full track-by-track transaction history and attach it here."
    ),
    "routenote": (
        "**How to export your RouteNote earnings report:**\n"
        "  1. Log in to RouteNote and navigate to **Sales & Reports → Earnings**.\n"
        "  2. Download the monthly **CSV statements** covering the last 24–36 months."
    ),
    "proton": (
        "**How to export your Proton SoundSystem statements:**\n"
        "  1. Log in to **Proton SoundSystem → Accounting / Statements**.\n"
        "  2. Export the **CSV/Excel track-level royalty statements** for the last 24–36 months."
    ),
    "sony": (
        "**How to export your Sony Music / The Orchard / AWAL royalty statements:**\n"
        "  1. Log in to your **Sony Royalty Portal / The Orchard Workstation**.\n"
        "  2. Download your **CSV/Excel Statement Detail** (by ISRC, period, and DSP) for the last 24–36 months alongside your distribution agreement."
    ),
    "universal": (
        "**How to export your Universal Music / Virgin / Ingrooves royalty statements:**\n"
        "  1. Log in to your **UMG Royalty Portal**.\n"
        "  2. Export the **Detailed CSV/Excel Royalty Statements** for the last 24–36 months."
    ),
    "warner": (
        "**How to export your Warner Music / ADA / Level statements:**\n"
        "  1. Log in to your **WMG / ADA Royalty Portal**.\n"
        "  2. Download the **Detailed CSV/Excel Royalty Statements** for the last 24–36 months."
    ),
}


def get_distributor_export_guide(distributor_or_admin: Optional[str]) -> str:
    """
    Returns a tailored step-by-step CSV export guide based on the applicant's distributor.
    """
    s = (distributor_or_admin or "").strip().lower()
    if "distrokid" in s or "distro kid" in s:
        return DISTRIBUTOR_EXPORT_GUIDES["distrokid"]
    if "tunecore" in s or "tune core" in s:
        return DISTRIBUTOR_EXPORT_GUIDES["tunecore"]
    if "united master" in s or "unitedmasters" in s:
        return DISTRIBUTOR_EXPORT_GUIDES["unitedmasters"]
    if "too lost" in s or "toolost" in s:
        return DISTRIBUTOR_EXPORT_GUIDES["too lost"]
    if "symphonic" in s:
        return DISTRIBUTOR_EXPORT_GUIDES["symphonic"]
    if "cd baby" in s or "cdbaby" in s:
        return DISTRIBUTOR_EXPORT_GUIDES["cd baby"]
    if "amuse" in s:
        return DISTRIBUTOR_EXPORT_GUIDES["amuse"]
    if "routenote" in s or "route note" in s:
        return DISTRIBUTOR_EXPORT_GUIDES["routenote"]
    if "proton" in s:
        return DISTRIBUTOR_EXPORT_GUIDES["proton"]
    if any(k in s for k in ["sony", "orchard", "awal", "rca", "columbia"]):
        return DISTRIBUTOR_EXPORT_GUIDES["sony"]
    if any(k in s for k in ["universal", "umg", "ingrooves", "virgin", "spinnin"]):
        return DISTRIBUTOR_EXPORT_GUIDES["universal"]
    if any(k in s for k in ["warner", "wmg", "ada"]):
        return DISTRIBUTOR_EXPORT_GUIDES["warner"]

    dist_label = distributor_or_admin or "your distributor"
    return (
        f"**How to export your statements from {dist_label}:**\n"
        f"  1. Log in to your **{dist_label}** royalty portal and open **Reports / Earnings / Statements**.\n"
        "  2. Export the **full detailed CSV/TSV or Excel report** (showing monthly earnings by track/ISRC, store/DSP, and country) for the last 24–36 months."
    )


# ---------------------------------------------------------------------------
# 5. Zero-Touch Stage 1 Orchestrator
# ---------------------------------------------------------------------------

class ZeroTouchActionDecision(str):
    AUTO_SEND_STAGE1_CSV_REQUEST = "AUTO_SEND_STAGE1_CSV_REQUEST"
    AUTO_SEND_MISSING_INFO_FOLLOWUP = "AUTO_SEND_MISSING_INFO_FOLLOWUP"
    AUTO_SEND_PARTNERSHIP_BOOKING = "AUTO_SEND_PARTNERSHIP_BOOKING"
    AUTO_DECLINE_AI_OR_FAKE_PROFILE = "AUTO_DECLINE_AI_OR_FAKE_PROFILE"
    AUTO_DECLINE_BELOW_THRESHOLD = "AUTO_DECLINE_BELOW_THRESHOLD"
    MANUAL_COMPLIANCE_HOLD = "MANUAL_COMPLIANCE_HOLD"


class ZeroTouchStage1Result(BaseModel):
    application_id: str
    artist_or_label_name: str
    contact_email: str
    spotify_enriched: bool = False
    spotify_snapshot: Optional[LiveSpotifyArtistSnapshot] = None
    implied_revenue_crosscheck: Optional[ImpliedRevenueCrossCheck] = None
    autonomous_decision: str
    pipeline_status: str
    valuation: CatalogValuationOutput
    reply_draft: ReplyDraft
    distributor_export_guide: str


def apply_live_spotify_enrichment(
    val_input: CatalogValuationInput,
    snapshot: LiveSpotifyArtistSnapshot,
) -> Tuple[CatalogValuationInput, Optional[ImpliedRevenueCrossCheck]]:
    """
    Enriches a `CatalogValuationInput` with live Spotify metadata (`followers`,
    `monthly_listeners`, `verified`, `external_social_links_count`, `releases`, and
    top-track durations/streams) and runs the mathematical stream-to-revenue cross-check.
    """
    val_input.spotify_artist_id = snapshot.spotify_artist_id
    val_input.spotify_followers = snapshot.followers
    val_input.spotify_monthly_listeners = snapshot.monthly_listeners
    val_input.spotify_verified = snapshot.verified
    val_input.external_social_links_count = len(snapshot.external_social_links)

    if snapshot.releases:
        val_input.releases = list(snapshot.releases)

    # Populate top tracks if Stage 2 CSV tracks are not yet present
    if not val_input.tracks and snapshot.top_tracks:
        total_top_streams = sum(max(0, t.total_streams) for t in snapshot.top_tracks)
        synthesized_tracks: List[TrackInput] = []
        for idx, t in enumerate(snapshot.top_tracks):
            share = (
                t.total_streams / total_top_streams
                if total_top_streams > 0
                else 1.0 / max(1, len(snapshot.top_tracks))
            )
            synthesized_tracks.append(
                TrackInput(
                    isrc=t.track_id or f"SPOTIFY_TOP_{idx + 1}",
                    title=t.title,
                    release_date=t.release_date,
                    duration_seconds=t.duration_ms / 1000.0,
                    total_streams=t.total_streams,
                    revenue_share=round(share, 6),
                )
            )
        val_input.tracks = synthesized_tracks

    rules = load_rules()
    declared_eur = convert_to_eur(val_input.declared_ltm_amount, val_input.declared_currency, rules)
    crosscheck = evaluate_implied_stream_revenue_crosscheck(
        declared_ltm_eur=declared_eur,
        spotify_monthly_listeners=snapshot.monthly_listeners,
        top_tracks=snapshot.top_tracks,
        ownership_share_pct=val_input.ownership_share_pct,
        notes=val_input.notes,
    )
    return val_input, crosscheck


def execute_zero_touch_stage1(
    app_row: CatalogApplication,
    *,
    engine: Optional[SpaceValuationEngine] = None,
    spotify_snapshot: Optional[LiveSpotifyArtistSnapshot] = None,
    raw_spotify_payload: Optional[Dict[str, Any]] = None,
    reference_date: Optional[date] = None,
) -> ZeroTouchStage1Result:
    """
    Executes the complete Zero-Touch Stage 1 pipeline:
    1. Converts `CatalogApplication` -> `CatalogValuationInput`.
    2. Normalizes and injects `spotify_snapshot` (or `raw_spotify_payload` from Treg/Spotify).
    3. Runs the Implied-Stream-to-Revenue mathematical cross-check.
    4. Runs `SpaceValuationEngine.evaluate()` (including 8-genre Bayesian DCF + AI/Fake detector).
    5. Determines the autonomous routing action (`AUTO_SEND_STAGE1_CSV_REQUEST`,
       `AUTO_DECLINE_AI_OR_FAKE_PROFILE`, `AUTO_SEND_MISSING_INFO_FOLLOWUP`, etc.) and
       builds the tailored reply draft with distributor-specific export instructions.
    """
    eng = engine or SpaceValuationEngine()
    val_input = application_to_valuation_input(app_row)

    snap = spotify_snapshot
    if snap is None and raw_spotify_payload is not None:
        _, extracted_id = extract_spotify_reference(app_row.listen_url)
        snap = parse_scrape_creators_spotify_payload(
            raw_spotify_payload,
            fallback_artist_id=extracted_id or app_row.spotify_artist_id,
        )

    crosscheck: Optional[ImpliedRevenueCrossCheck] = None
    if snap is not None:
        val_input, crosscheck = apply_live_spotify_enrichment(val_input, snap)
        app_row.spotify_artist_id = snap.spotify_artist_id

    valuation = eng.evaluate(val_input, reference_date=reference_date)

    # Inject Implied-Stream-to-Revenue Cross-Check into RiskFlags & Valuation if severe mismatch
    if crosscheck is not None:
        if crosscheck.discrepancy_status == "EXTREME_FABRICATION_OR_MISMATCH":
            valuation.risk_flags.append(
                RiskFlag(
                    code="IMPLIED_STREAM_REVENUE_MISMATCH",
                    severity=RiskSeverity.CRITICAL,
                    title="Declared Royalties Exceed Mathematical DSP Stream Ceiling (>5x)",
                    description=crosscheck.explanation,
                    discount_rate_bps_impact=crosscheck.recommended_discount_bps,
                )
            )
            valuation.integrity_score = round(max(0.0, valuation.integrity_score - 45.0), 1)
        elif crosscheck.discrepancy_status == "ELEVATED_OFF_SPOTIFY_DEPENDENCY":
            valuation.risk_flags.append(
                RiskFlag(
                    code="OFF_SPOTIFY_REVENUE_VERIFICATION_REQUIRED",
                    severity=RiskSeverity.MEDIUM,
                    title="Declared Royalties Exceed Spotify-Implied Ceiling (>2x)",
                    description=crosscheck.explanation,
                    discount_rate_bps_impact=crosscheck.recommended_discount_bps,
                )
            )

    export_guide = get_distributor_export_guide(app_row.distributor_or_admin)

    # Autonomous routing decision
    ai_rep = valuation.ai_profile_validation
    is_confirmed_ai_or_fake = (
        ai_rep is not None
        and ai_rep.authenticity_status == AuthenticityStatus.CONFIRMED_AI_OR_FARM
    ) or (
        crosscheck is not None
        and crosscheck.discrepancy_status == "EXTREME_FABRICATION_OR_MISMATCH"
        and (snap is not None and snap.monthly_listeners < 300)
    )

    if app_row.inquiry_route == "partnership":
        decision = ZeroTouchActionDecision.AUTO_SEND_PARTNERSHIP_BOOKING
        reply_draft = generate_reply_draft(app_row, valuation)
    elif is_confirmed_ai_or_fake:
        decision = ZeroTouchActionDecision.AUTO_DECLINE_AI_OR_FAKE_PROFILE
        valuation.pipeline_status = "DECLINED_AI_OR_FAKE_PROFILE"
        first_name = (app_row.contact_name or "there").split()[0]
        subject = f"Your SPACE catalog review — {app_row.artist_or_label_name or 'Catalog Submission'}"
        body = (
            f"Hi {first_name},\n\n"
            f"Thank you for submitting **{app_row.artist_or_label_name or 'your catalog'}** to SPACE.\n\n"
            "After running our automated DSP metadata and catalog eligibility screening, "
            "this catalog does not meet our current underwriting criteria for acquisition "
            "(which require verified organic streaming history, human-authored copyright eligibility, "
            "and established DSP listener velocity above platform monetization thresholds).\n\n"
            "We appreciate you thinking of SPACE and wish you the best with your releases.\n\n"
            "Best regards,\n"
            "Emil\n"
            "SPACE (spacemusic.io)"
        )
        reply_draft = ReplyDraft(
            recipient_email=app_row.contact_email,
            recipient_name=app_row.contact_name,
            subject=subject,
            body=body,
            template_type="AUTO_DECLINE_AI_OR_FAKE",
        )
    elif valuation.pipeline_status == "MISSING_INFO":
        decision = ZeroTouchActionDecision.AUTO_SEND_MISSING_INFO_FOLLOWUP
        reply_draft = generate_reply_draft(app_row, valuation)
    elif valuation.pipeline_status == "DECLINED_BELOW_THRESHOLD":
        decision = ZeroTouchActionDecision.AUTO_DECLINE_BELOW_THRESHOLD
        reply_draft = generate_reply_draft(app_row, valuation)
    elif (
        ai_rep is not None
        and ai_rep.authenticity_status == AuthenticityStatus.SUSPECTED_AI_OR_FAKE
    ):
        decision = ZeroTouchActionDecision.MANUAL_COMPLIANCE_HOLD
        reply_draft = generate_reply_draft(app_row, valuation)
    else:
        decision = ZeroTouchActionDecision.AUTO_SEND_STAGE1_CSV_REQUEST
        base_draft = generate_reply_draft(app_row, valuation)
        # Inject the tailored distributor step-by-step export guide into the Stage 1 CSV request
        enhanced_body = base_draft.body.replace(
            "Best regards,\nEmil\nSPACE (spacemusic.io)",
            f"{export_guide}\n\nBest regards,\nEmil\nSPACE (spacemusic.io)",
        )
        reply_draft = ReplyDraft(
            recipient_email=base_draft.recipient_email,
            recipient_name=base_draft.recipient_name,
            subject=base_draft.subject,
            body=enhanced_body,
            template_type=base_draft.template_type,
        )

    # Sync application row fields
    app_row.pipeline_status = valuation.pipeline_status
    app_row.valuation_stage = valuation.valuation_stage
    app_row.effective_cf0_eur = valuation.baseline.effective_cf0_eur
    app_row.price_low_eur = valuation.price_low_eur
    app_row.price_median_eur = valuation.price_median_eur
    app_row.price_high_eur = valuation.price_high_eur
    app_row.implied_multiple_median = valuation.implied_ltm_multiple_median
    app_row.discount_rate = valuation.discount_rate.total_discount_rate
    app_row.integrity_score = valuation.integrity_score
    app_row.valuation_confidence = valuation.valuation_confidence
    app_row.valuation_report_json = (
        valuation.model_dump() if hasattr(valuation, "model_dump") else valuation.dict()
    )
    app_row.draft_reply_subject = reply_draft.subject
    app_row.draft_reply_body = reply_draft.body

    return ZeroTouchStage1Result(
        application_id=str(app_row.id),
        artist_or_label_name=app_row.artist_or_label_name,
        contact_email=app_row.contact_email,
        spotify_enriched=snap is not None,
        spotify_snapshot=snap,
        implied_revenue_crosscheck=crosscheck,
        autonomous_decision=decision,
        pipeline_status=valuation.pipeline_status,
        valuation=valuation,
        reply_draft=reply_draft,
        distributor_export_guide=export_guide,
    )
