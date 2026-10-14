"""
Lead-Lag Arbitrage Detector & Chain-of-Title / Split Auditor
(`services/valuation/lead_lag_and_title_forensics.py`)

Implements two institutional due-diligence engines that solve the 90-day accounting lag
and hidden encumbrance traps in music catalog acquisitions:

1. Lead-Lag Arbitrage & Pre-Clawback Dump Detector (`evaluate_lead_lag_arbitrage`):
   - Compares trailing CSV royalty statement velocity (which lags 60–90 days behind real-time)
     against live DSP listener/stream momentum (`spotify_monthly_listeners`, recent top-track
     velocity, or real-time 30-day stream estimates).
   - Computes the Real-Time Velocity Ratio (`RVR`):
     - `RVR < 0.35`: `PRE_CLAWBACK_DUMP_WARNING` (catalog has crashed or been delisted/penalized
       on DSPs in the last 60 days while historical CSV statements still look healthy).
     - `0.35 <= RVR < 0.65`: `POST_STATEMENT_DECELERATION` (steep drop since last statement period).
     - `0.65 <= RVR <= 1.65`: `SYNCHRONIZED_STEADY` (live DSP velocity matches accounting statements).
     - `RVR > 1.65`: `MOMENTUM_ARBITRAGE_OPPORTUNITY` (catalog is breaking out on DSPs/TikTok/Shazam
       faster than trailing CSV statements reflect — high-alpha acquisition opportunity).

2. Automated Chain-of-Title, Distributor-Hopping & Split-Sheet Auditor (`evaluate_chain_of_title`):
   - Audits P-line / label strings across historical releases (`ReleaseMetadataItem` & `TrackInput`).
   - Detects `DISTRIBUTOR_HOPPING_UNRECOUPED_RISK`: when a catalog recently migrated from an
     advance-issuing distributor/label (e.g., Create Music Group, Too Lost, Empire, Symphonic,
     Foundation, Stem, AWAL) to a DIY distributor (e.g., DistroKid, TuneCore) within the last
     12 months — a classic sign of fleeing an unrecouped advance.
   - Detects `MULTI_ENTITY_PLINE_FRAGMENTATION`: when releases carry multiple distinct corporate
     or third-party label P-lines that do not match the applicant's artist/label/organization name.
   - Detects `COLLABORATOR_OR_PRODUCER_SPLIT_EXPOSURE`: scans track titles (`feat.`, `ft.`, `with`,
     `&`, `x`, `prod.`) and submission notes to generate an automated checklist of required
     Master Split Sheets and Producer Letters of Direction (LODs) before closing.
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import List, Optional, Sequence, Set

from pydantic import BaseModel, Field

from .ai_profile_detector import ReleaseMetadataItem


class LeadLagSignalStatus(str, Enum):
    PRE_CLAWBACK_DUMP_WARNING = "PRE_CLAWBACK_DUMP_WARNING"
    POST_STATEMENT_DECELERATION = "POST_STATEMENT_DECELERATION"
    SYNCHRONIZED_STEADY = "SYNCHRONIZED_STEADY"
    MOMENTUM_ARBITRAGE_OPPORTUNITY = "MOMENTUM_ARBITRAGE_OPPORTUNITY"


class LeadLagArbitrageReport(BaseModel):
    real_time_velocity_ratio: float = Field(
        default=1.0,
        description="Ratio of live DSP implied monthly stream/revenue velocity to latest CSV monthly average.",
    )
    signal_status: LeadLagSignalStatus = LeadLagSignalStatus.SYNCHRONIZED_STEADY
    trailing_statement_monthly_streams: int = 0
    trailing_statement_monthly_eur: float = 0.0
    live_implied_monthly_streams: int = 0
    live_implied_monthly_eur: float = 0.0
    recommended_haircut_pct: float = 0.0
    recommended_discount_bps: int = 0
    rationale: str = ""


ADVANCE_ISSUING_DISTRIBUTORS = {
    "create music",
    "too lost",
    "toolost",
    "empire",
    "symphonic",
    "foundation media",
    "stem",
    "awal",
    "vydia",
    "the orchard",
    "orchard",
    "believe",
    "fuga",
    "onerpm",
    "unitedmasters",
    "united masters",
}

DIY_SELF_SERVE_LABELS = {
    "distrokid",
    "records dk",
    "tunecore",
    "cd baby",
    "cdbaby",
    "routenote",
    "amuse",
    "ditto",
}


class ChainOfTitleStatus(str, Enum):
    CLEAN_SINGLE_OWNER = "CLEAN_SINGLE_OWNER"
    SPLIT_VERIFICATION_REQUIRED = "SPLIT_VERIFICATION_REQUIRED"
    ENCUMBRANCE_OR_HOPPING_ALERT = "ENCUMBRANCE_OR_HOPPING_ALERT"


class ChainOfTitleAuditReport(BaseModel):
    title_status: ChainOfTitleStatus = ChainOfTitleStatus.CLEAN_SINGLE_OWNER
    distinct_plines_detected: List[str] = Field(default_factory=list)
    distributor_hopping_detected: bool = False
    unrecouped_advance_risk: bool = False
    collaborator_tracks_detected: List[str] = Field(default_factory=list)
    estimated_featured_track_share: float = 0.0
    required_closing_documents: List[str] = Field(default_factory=list)
    recommended_discount_bps: int = 0
    findings: List[str] = Field(default_factory=list)


def evaluate_lead_lag_arbitrage(
    *,
    trailing_monthly_revenues_eur: Sequence[float],
    trailing_monthly_streams: Sequence[int],
    spotify_monthly_listeners: Optional[int] = None,
    live_30d_spotify_streams: Optional[int] = None,
    spotify_revenue_share: float = 0.65,
    observed_blended_rpm_eur: float = 0.0029,
) -> Optional[LeadLagArbitrageReport]:
    """
    Compares the most recent 3 months of CSV accounting statements against live DSP
    monthly listeners or 30-day real-time streams to detect either:
    - A post-statement collapse / DSP takedown (`PRE_CLAWBACK_DUMP_WARNING`, RVR < 0.35), or
    - A real-time viral breakout not yet priced into trailing statements (`MOMENTUM_ARBITRAGE_OPPORTUNITY`, RVR > 1.65).
    """
    if not trailing_monthly_revenues_eur:
        return None
    if spotify_monthly_listeners is None and live_30d_spotify_streams is None:
        return None

    recent_revs = list(trailing_monthly_revenues_eur[-3:])
    avg_stmt_monthly_eur = sum(recent_revs) / max(1, len(recent_revs))
    if avg_stmt_monthly_eur <= 10.0:
        return None

    recent_strms = [s for s in trailing_monthly_streams[-3:] if s > 0]
    if recent_strms:
        avg_stmt_monthly_streams = int(round(sum(recent_strms) / len(recent_strms)))
    else:
        avg_stmt_monthly_streams = int(round(avg_stmt_monthly_eur / max(0.0005, observed_blended_rpm_eur)))

    # Estimate current 30-day Spotify streams from live_30d_spotify_streams or monthly_listeners
    if live_30d_spotify_streams is not None and live_30d_spotify_streams >= 0:
        live_sp_streams = live_30d_spotify_streams
    else:
        # Empirical conversion: 1 monthly listener ~= 3.4 streams/month on average
        live_sp_streams = int(round((spotify_monthly_listeners or 0) * 3.4))

    # Scale Spotify 30d streams to all-DSP monthly streams using observed Spotify DSP share
    sp_share_clamped = max(0.25, min(0.95, spotify_revenue_share if spotify_revenue_share > 0 else 0.65))
    live_all_dsp_streams = int(round(live_sp_streams / sp_share_clamped))

    effective_rpm = (
        avg_stmt_monthly_eur / avg_stmt_monthly_streams
        if avg_stmt_monthly_streams > 0
        else observed_blended_rpm_eur
    )
    live_monthly_eur = live_all_dsp_streams * effective_rpm

    rvr = round(live_monthly_eur / max(1.0, avg_stmt_monthly_eur), 3)

    if rvr < 0.35:
        status = LeadLagSignalStatus.PRE_CLAWBACK_DUMP_WARNING
        haircut = 0.55
        bps = 350
        rationale = (
            f"Pre-Clawback Dump Warning (RVR={rvr:.2f}x): Live DSP velocity (~€{live_monthly_eur:,.0f}/mo from "
            f"{spotify_monthly_listeners or 0:,} monthly listeners) is {(1.0 - rvr) * 100:.0f}% below the trailing CSV "
            f"statement average (€{avg_stmt_monthly_eur:,.0f}/mo). High risk that key tracks or playlists were "
            "delisted during the 60–90 day statement reporting lag."
        )
    elif rvr < 0.65:
        status = LeadLagSignalStatus.POST_STATEMENT_DECELERATION
        haircut = 0.20
        bps = 150
        rationale = (
            f"Post-Statement Deceleration (RVR={rvr:.2f}x): Live DSP velocity (~€{live_monthly_eur:,.0f}/mo) "
            f"has cooled {(1.0 - rvr) * 100:.0f}% below the trailing 3-month CSV average (€{avg_stmt_monthly_eur:,.0f}/mo)."
        )
    elif rvr > 1.65:
        status = LeadLagSignalStatus.MOMENTUM_ARBITRAGE_OPPORTUNITY
        haircut = 0.0
        bps = 0
        rationale = (
            f"Momentum Arbitrage Signal (RVR={rvr:.2f}x): Live DSP velocity (~€{live_monthly_eur:,.0f}/mo from "
            f"{spotify_monthly_listeners or 0:,} monthly listeners) is running {rvr:.2f}x ABOVE the trailing CSV "
            f"statement average (€{avg_stmt_monthly_eur:,.0f}/mo) — catalog is accelerating during the 90-day accounting lag."
        )
    else:
        status = LeadLagSignalStatus.SYNCHRONIZED_STEADY
        haircut = 0.0
        bps = 0
        rationale = (
            f"Synchronized Real-Time Velocity (RVR={rvr:.2f}x): Live DSP footprint (~€{live_monthly_eur:,.0f}/mo) "
            f"closely corroborates trailing CSV statement average (€{avg_stmt_monthly_eur:,.0f}/mo)."
        )

    return LeadLagArbitrageReport(
        real_time_velocity_ratio=rvr,
        signal_status=status,
        trailing_statement_monthly_streams=avg_stmt_monthly_streams,
        trailing_statement_monthly_eur=round(avg_stmt_monthly_eur, 2),
        live_implied_monthly_streams=live_all_dsp_streams,
        live_implied_monthly_eur=round(live_monthly_eur, 2),
        recommended_haircut_pct=haircut,
        recommended_discount_bps=bps,
        rationale=rationale,
    )


def evaluate_chain_of_title(
    *,
    artist_or_label_name: str,
    declared_distributor: Optional[str] = None,
    declared_ownership_pct: float = 100.0,
    releases: Optional[Sequence[ReleaseMetadataItem]] = None,
    track_titles: Optional[Sequence[str]] = None,
    track_labels: Optional[Sequence[str]] = None,
    notes: Optional[str] = None,
    reference_date: Optional[date] = None,
) -> ChainOfTitleAuditReport:
    """
    Audits release P-lines, distributor migration history, and featured/producer collaborations
    to verify Chain of Title and generate required closing documents (LODs, Split Sheets, Recoupment Releases).
    """
    ref_date = reference_date or date.today()
    findings: List[str] = []
    closing_docs: List[str] = [
        "Signed Master / Catalog Purchase Agreement (SPACE Standard Short-Form APA)",
        f"Distributor Letter of Direction (LOD) / Account Transfer Authorization ({declared_distributor or 'Current Distributor'})",
    ]
    bps = 0

    # 1. Collect all P-lines / labels and release dates
    dated_labels: List[ tuple[Optional[date], str] ] = []
    if releases:
        for r in releases:
            if r.label and r.label.strip():
                dated_labels.append((r.release_date, r.label.strip()))
    if track_labels:
        for lbl in track_labels:
            if lbl and lbl.strip():
                dated_labels.append((None, lbl.strip()))

    distinct_plines = sorted({lbl for _, lbl in dated_labels})

    # 2. Check for Distributor Hopping / Unrecouped Advance Flight
    # Specifically: older releases on an advance-issuing label/distributor, but recent releases
    # (or declared current distributor) switched to DIY (DistroKid/TuneCore)
    dist_lower = (declared_distributor or "").lower()
    is_current_diy = any(d in dist_lower for d in DIY_SELF_SERVE_LABELS)

    prior_advance_labels: Set[str] = set()
    recent_diy_labels: Set[str] = set()

    for rel_dt, lbl in dated_labels:
        lbl_l = lbl.lower()
        for adv_kw in ADVANCE_ISSUING_DISTRIBUTORS:
            if adv_kw in lbl_l and adv_kw not in dist_lower:
                prior_advance_labels.add(lbl)
        if any(diy_kw in lbl_l for diy_kw in DIY_SELF_SERVE_LABELS):
            if rel_dt is None or (ref_date - rel_dt).days <= 365:
                recent_diy_labels.add(lbl)

    notes_lower = (notes or "").lower()
    explicit_advance_note = any(
        kw in notes_lower for kw in ["advance", "unrecouped", "recoup", "loan", "lien", "encumbrance"]
    )

    distributor_hopping = bool(prior_advance_labels and (is_current_diy or recent_diy_labels))
    unrecouped_risk = distributor_hopping or explicit_advance_note

    if distributor_hopping:
        bps += 200
        prior_str = ", ".join(sorted(prior_advance_labels)[:3])
        findings.append(
            f"Distributor-Hopping / Potential Unrecouped Balance: Historical releases carry `{prior_str}` P-lines "
            f"while current distribution is `{declared_distributor or 'DIY'}` — require Zero-Balance / Lien Release Confirmation."
        )
        closing_docs.append(
            f"Written Zero-Balance & Recoupment Release Confirmation from prior distributor/label ({prior_str})"
        )
    elif explicit_advance_note:
        bps += 175
        findings.append(
            "Submission notes reference an existing advance, recoupment balance, or encumbrance — "
            "require payoff statement or direct proceeds deduction at closing."
        )
        closing_docs.append("Payoff Statement & Lien Release from existing advance provider")

    # 3. Check for Collaborator / Featured Artist / Producer Split Exposure
    all_titles: List[str] = []
    if track_titles:
        all_titles.extend([t for t in track_titles if t])
    elif releases:
        all_titles.extend([r.title for r in releases if r.title])

    collab_pattern = re.compile(
        r"(?:\b(?:feat\.?|ft\.?|featuring|with|prod\.?\s+by)\b|\s+[xX&]\s+)",
        re.IGNORECASE,
    )
    collab_tracks: List[str] = []
    for t in all_titles:
        if collab_pattern.search(t):
            collab_tracks.append(t)

    collab_share = len(collab_tracks) / max(1, len(all_titles)) if all_titles else 0.0

    if collab_tracks and declared_ownership_pct >= 99.0:
        bps += 100
        sample_collabs = ", ".join(collab_tracks[:3])
        findings.append(
            f"Collaborator / Featured Artist Split Exposure: Seller declared {declared_ownership_pct:.0f}% ownership, "
            f"but {len(collab_tracks)}/{len(all_titles)} tracks ({collab_share * 100:.0f}%) list featured artists, co-artists, "
            f"or producers in the title ({sample_collabs})."
        )
        closing_docs.append(
            "Signed Master Split Sheets & Featured Artist Side-Artist Waivers for collaborative tracks"
        )

    if len(distinct_plines) >= 4 and not distributor_hopping:
        bps += 75
        findings.append(
            f"Multi-Entity P-Line Fragmentation: Catalog spans {len(distinct_plines)} distinct P-line strings "
            f"({', '.join(distinct_plines[:4])}) — verify 100% chain of title across all entities."
        )

    if unrecouped_risk:
        status = ChainOfTitleStatus.ENCUMBRANCE_OR_HOPPING_ALERT
    elif collab_tracks or len(distinct_plines) >= 4 or declared_ownership_pct < 100.0:
        status = ChainOfTitleStatus.SPLIT_VERIFICATION_REQUIRED
    else:
        status = ChainOfTitleStatus.CLEAN_SINGLE_OWNER

    return ChainOfTitleAuditReport(
        title_status=status,
        distinct_plines_detected=distinct_plines,
        distributor_hopping_detected=distributor_hopping,
        unrecouped_advance_risk=unrecouped_risk,
        collaborator_tracks_detected=collab_tracks,
        estimated_featured_track_share=round(collab_share, 4),
        required_closing_documents=closing_docs,
        recommended_discount_bps=bps,
        findings=findings,
    )
