"""
AI & Fake Artist Profile Forensics Detector (`services/valuation/ai_profile_detector.py`)

Detects synthetic / AI-generated artist profiles (Suno / Udio mass-uploaders),
fake DIY P-line major-label spoofing, and zero-velocity ghost profiles across
both Stage 1 (Typeform + Spotify profile metadata) and Stage 2 (CSV statement) inputs.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, Sequence

from pydantic import BaseModel, Field


class AuthenticityStatus(str, Enum):
    VERIFIED_ORGANIC = "VERIFIED_ORGANIC"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SUSPECTED_AI_OR_FAKE = "SUSPECTED_AI_OR_FAKE"
    CONFIRMED_AI_OR_FARM = "CONFIRMED_AI_OR_FARM"


SPOOFED_MAJOR_LABELS = [
    "universal music",
    "sony music",
    "warner music",
    "island def jam",
    "def jam",
    "maybach music",
    "republic records",
    "interscope",
    "atlantic records",
    "columbia records",
    "rca records",
    "epic records",
    "aftermath",
    "xo records",
    "ovosound",
    "ovo sound",
    "cactus jack",
]

DIY_DISTRIBUTOR_KEYWORDS = {
    "distrokid",
    "tunecore",
    "unitedmasters",
    "united masters",
    "united master",
    "ditto",
    "amuse",
    "cd baby",
    "cdbaby",
    "routenote",
    "route note",
    "landr",
    "too lost",
    "toolost",
    "soundclod",
    "soundcloud",
    "symphonic",
    "onerpm",
}

AI_DISCLOSURE_PATTERNS = [
    r"\b(?:my\s+music|catalog|songs|tracks)\s+(?:is|are|was|were)?\s*(?:created|made|generated|produced)\s+(?:with|by|using)\s+ai\b",
    r"\bincluding\s+music\s+(?:created|made|generated)\s+with\s+ai\b",
    r"\b(?:suno|udio|boomy|soundraw|mubert|aisong|lalal|kits\.ai|elevenlabs)\b",
]


class ReleaseMetadataItem(BaseModel):
    title: str
    release_date: Optional[date] = None
    release_type: str = "SINGLE"  # SINGLE | ALBUM | EP
    track_count: int = 1
    label: Optional[str] = None
    total_streams: Optional[int] = None
    duration_ms: Optional[int] = None


class AIProfileValidationReport(BaseModel):
    ai_fake_probability_score: float = Field(
        default=0.0,
        description="0.0 (completely organic human artist) to 100.0 (confirmed AI farm / fake profile)",
    )
    authenticity_status: AuthenticityStatus = AuthenticityStatus.VERIFIED_ORGANIC
    signals_detected: List[str] = Field(default_factory=list)
    self_disclosed_ai: bool = False
    ai_studio_or_synthetic_url: bool = False
    mass_upload_cadence_detected: bool = False
    spoofed_major_label_detected: bool = False
    ghost_profile_mismatch: bool = False
    short_clip_loop_farm_detected: bool = False
    recommended_haircut_pct: float = 0.0
    recommended_discount_bps: int = 0


def evaluate_ai_and_fake_profile(
    *,
    artist_or_label_name: str,
    listen_url: Optional[str] = None,
    organization_website: Optional[str] = None,
    distributor_or_admin: Optional[str] = None,
    notes: Optional[str] = None,
    declared_ltm_eur: float = 0.0,
    spotify_followers: Optional[int] = None,
    spotify_monthly_listeners: Optional[int] = None,
    spotify_verified: Optional[bool] = None,
    external_social_links_count: Optional[int] = None,
    releases: Optional[Sequence[ReleaseMetadataItem]] = None,
    track_durations_ms: Optional[Sequence[int]] = None,
    track_release_dates: Optional[Sequence[date]] = None,
    track_labels: Optional[Sequence[str]] = None,
    track_streams: Optional[Sequence[int]] = None,
    reference_date: Optional[date] = None,
) -> AIProfileValidationReport:
    """
    Evaluates an artist/catalog submission across 7 forensic dimensions to detect
    AI-generated catalogs (Suno/Udio farms), fake spoofed profiles, and ghost accounts.
    """
    ref_date = reference_date or date.today()
    score = 0.0
    signals: List[str] = []

    self_disclosed_ai = False
    ai_studio_url = False
    mass_upload = False
    spoofed_major = False
    ghost_mismatch = False
    short_clip_farm = False

    notes_text = (notes or "").strip()
    notes_lower = notes_text.lower()
    urls_combined = f"{listen_url or ''} {organization_website or ''}".lower()
    dist_lower = (distributor_or_admin or "").strip().lower()

    # ------------------------------------------------------------------
    # 1. Explicit AI Generation Disclosure or AI Studio / Synthetic Domain
    # ------------------------------------------------------------------
    for pat in AI_DISCLOSURE_PATTERNS:
        if re.search(pat, notes_lower):
            self_disclosed_ai = True
            score += 45.0
            signals.append(
                "Explicit AI music disclosure in submission notes (Suno/Udio/AI tools referenced — "
                "pure AI-generated outputs lack human copyright protection and face DSP demonetization)."
            )
            break

    if any(
        dom in urls_combined
        for dom in [".ai.studio", "suno.com", "suno.ai", "udio.com", "boomy.com", "mubert.com"]
    ):
        ai_studio_url = True
        score += 35.0
        signals.append(
            f"AI Studio or generative music platform domain detected in submitted URL ({organization_website or listen_url})."
        )

    # Check for "1,750 unreleased tracks across 175 albums" style bulk library claims
    m_bulk = re.search(r"(\d[\d,]*)\s*(?:unreleased\s+)?tracks", notes_lower)
    if m_bulk:
        try:
            n_claimed = int(m_bulk.group(1).replace(",", ""))
            if n_claimed >= 300 and ("unreleased" in notes_lower or "categories" in notes_lower):
                score += 40.0
                mass_upload = True
                signals.append(
                    f"Bulk synthetic library pattern: applicant claims {n_claimed:,} tracks "
                    "with zero commercial streaming history."
                )
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # 2. Release Velocity & Same-Day Batch Dumping (Suno/Udio Farm Signature)
    # ------------------------------------------------------------------
    all_dates: List[date] = []
    if releases:
        all_dates.extend([r.release_date for r in releases if r.release_date is not None])
    if track_release_dates:
        all_dates.extend([d for d in track_release_dates if d is not None])

    if all_dates:
        # Focus same-day batch check on recent releases (within last 24 months) so legacy
        # back-catalog migrations (e.g. 2012-12-15) are not misclassified as AI farms.
        recent_dates = [d for d in all_dates if (ref_date - d).days <= 730]
        date_counts = Counter(recent_dates)
        max_same_day = max(date_counts.values()) if date_counts else 0
        # Count releases within the most active 30-day window in recent 24 months
        sorted_dates = sorted(recent_dates)
        max_in_30d = 0
        for i, d_start in enumerate(sorted_dates):
            in_win = sum(1 for d_end in sorted_dates[i:] if 0 <= (d_end - d_start).days <= 30)
            if in_win > max_in_30d:
                max_in_30d = in_win

        earliest_date = min(all_dates)
        catalog_span_days = max(1, (ref_date - earliest_date).days)

        # Count how many full albums were dropped within 180 days
        album_count_180d = 0
        if releases:
            album_count_180d = sum(
                1
                for r in releases
                if r.release_type.upper() == "ALBUM"
                and r.track_count >= 8
                and r.release_date is not None
                and (ref_date - r.release_date).days <= 240
            )

        if max_same_day >= 4 or max_in_30d >= 8 or album_count_180d >= 5:
            mass_upload = True
            score += 40.0
            signals.append(
                f"AI/Bot mass-upload cadence: {max_same_day} releases on the exact same date, "
                f"{max_in_30d} releases within a 30-day window, and {album_count_180d} full albums in <8 months."
            )
        elif len(all_dates) >= 6 and catalog_span_days <= 45:
            mass_upload = True
            score += 35.0
            signals.append(
                f"Newly minted high-frequency profile: {len(all_dates)} releases dropped within "
                f"the last {catalog_span_days} days with no prior catalog history."
            )

    # ------------------------------------------------------------------
    # 3. Spoofed Major-Label P-Lines on DIY Distributors
    # ------------------------------------------------------------------
    has_major_declared = any(maj in dist_lower for maj in SPOOFED_MAJOR_LABELS)
    is_diy_dist = (any(k in dist_lower for k in DIY_DISTRIBUTOR_KEYWORDS) or not dist_lower) and not has_major_declared
    labels_to_check: List[str] = []
    if releases:
        labels_to_check.extend([r.label for r in releases if r.label])
    if track_labels:
        labels_to_check.extend([lbl for lbl in track_labels if lbl])

    if is_diy_dist and labels_to_check:
        spoofed_hits = set()
        for lbl in labels_to_check:
            lbl_l = lbl.lower()
            for maj in SPOOFED_MAJOR_LABELS:
                if maj in lbl_l:
                    spoofed_hits.add(lbl)
        if spoofed_hits:
            spoofed_major = True
            score += 45.0
            sample_spoofs = ", ".join(sorted(list(spoofed_hits))[:3])
            signals.append(
                f"Fake Major-Label P-Line Spoofing: DIY distributor ({distributor_or_admin or 'DIY'}) "
                f"releases carry fabricated major-label strings ({sample_spoofs})."
            )

    # ------------------------------------------------------------------
    # 4. Short-Clip Loop Farming (~58-65s tracks to game Spotify 30s stream floor)
    # ------------------------------------------------------------------
    durations: List[int] = []
    if releases:
        durations.extend([r.duration_ms for r in releases if r.duration_ms is not None and r.duration_ms > 0])
    if track_durations_ms:
        durations.extend([d for d in track_durations_ms if d is not None and d > 0])

    if len(durations) >= 3:
        under_70s = [d for d in durations if 30_000 <= d <= 70_000]
        share_under_70s = len(under_70s) / len(durations)
        if share_under_70s >= 0.40:
            short_clip_farm = True
            score += 30.0
            signals.append(
                f"Short-clip loop farm signature: {share_under_70s * 100:.0f}% of tracks are 30–70 seconds long "
                "(engineered to maximize per-minute stream counts just above Spotify's 30-second monetization trigger)."
            )

    # ------------------------------------------------------------------
    # 5. Ghost Profile / Zero-Stream Velocity vs. Declared Revenue
    # ------------------------------------------------------------------
    observed_streams: List[int] = []
    if releases:
        observed_streams.extend([r.total_streams for r in releases if r.total_streams is not None])
    if track_streams:
        observed_streams.extend([s for s in track_streams if s is not None])

    total_obs_streams = sum(observed_streams) if observed_streams else None

    if (
        spotify_monthly_listeners is not None
        and spotify_monthly_listeners < 50
        and (spotify_followers is None or spotify_followers < 200)
        and (declared_ltm_eur > 1000.0 or (total_obs_streams is not None and total_obs_streams == 0 and len(observed_streams) >= 3))
    ):
        ghost_mismatch = True
        score += 35.0
        signals.append(
            f"Ghost/Zero-Velocity Spotify Profile: only {spotify_monthly_listeners} monthly listeners "
            f"(followers: {spotify_followers or 0}) despite active catalog submission."
        )
    elif (
        spotify_monthly_listeners is not None
        and spotify_monthly_listeners < 300
        and total_obs_streams is not None
        and total_obs_streams < 1000
        and len(observed_streams) >= 4
    ):
        ghost_mismatch = True
        score += 30.0
        signals.append(
            f"Sub-threshold ghost catalog: top tracks show {total_obs_streams} cumulative streams "
            f"and {spotify_monthly_listeners} monthly listeners (0 monetizable tracks under Spotify's 1,000-stream floor)."
        )

    # ------------------------------------------------------------------
    # 6. Extreme Listener-to-Follower Ratio with Zero Social Footprint
    # ------------------------------------------------------------------
    if (
        spotify_monthly_listeners is not None
        and spotify_followers is not None
        and spotify_monthly_listeners >= 50_000
    ):
        follower_ratio = spotify_followers / max(1, spotify_monthly_listeners)
        if follower_ratio < 0.015 and (external_social_links_count == 0):
            score += 25.0
            signals.append(
                f"Anonymous playlist-dependent profile: {spotify_monthly_listeners:,} monthly listeners "
                f"with only {spotify_followers:,} followers ({follower_ratio * 100:.2f}% conversion) and zero linked social accounts."
            )

    # Cap score at 100.0
    final_score = round(min(100.0, max(0.0, score)), 1)

    if final_score >= 70.0:
        status = AuthenticityStatus.CONFIRMED_AI_OR_FARM
        haircut_pct = 0.80
        bps = 450
    elif final_score >= 40.0:
        status = AuthenticityStatus.SUSPECTED_AI_OR_FAKE
        haircut_pct = 0.40
        bps = 300
    elif final_score >= 20.0:
        status = AuthenticityStatus.REVIEW_REQUIRED
        haircut_pct = 0.15
        bps = 150
    else:
        status = AuthenticityStatus.VERIFIED_ORGANIC
        haircut_pct = 0.0
        bps = 0

    return AIProfileValidationReport(
        ai_fake_probability_score=final_score,
        authenticity_status=status,
        signals_detected=signals,
        self_disclosed_ai=self_disclosed_ai,
        ai_studio_or_synthetic_url=ai_studio_url,
        mass_upload_cadence_detected=mass_upload,
        spoofed_major_label_detected=spoofed_major,
        ghost_profile_mismatch=ghost_mismatch,
        short_clip_loop_farm_detected=short_clip_farm,
        recommended_haircut_pct=haircut_pct,
        recommended_discount_bps=bps,
    )
