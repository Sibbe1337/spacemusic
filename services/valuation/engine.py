"""
SPACE Valuation & Forensics Engine (services/valuation/engine.py)

A deterministic + stochastic (Monte Carlo) music catalog valuation and due-diligence
engine tailored for independent and mid-market music catalogs ($3k-$500k LTM).

Architecture Layers:
1. Baseline Normalizer: Gross-to-net distributor fee adjustment, FX normalization,
   median-absolute-deviation (MAD) spike clipping (Winsorization), and LTM vs L3M
   momentum weighting.
2. Cohort Survival & Decay Model: Weibull/exponential age-cohort decay curves by
   genre family with empirical Bayesian shrinkage against track-level monthly statement slopes.
3. 6-Point Forensics & Integrity Scorer:
   - Spotify 1,000 annual stream threshold trap detector
   - Spotify functional noise (<120,000 ms duration) demonetization check
   - Net Per-Stream Yield (RPM) anomaly & bot-farm territory detector
   - Herfindahl-Hirschman Index (HHI) track revenue concentration
   - Monthly step-function / promotional playlist spike detector
   - Spotify P/C-line copyright & label mismatch vs declared ownership
4. Dynamic Risk-Adjusted Discount Rate (WACC / IRR build-up model).
5. Track-by-Track Monte Carlo DCF (60-month & 120-month horizons) + Deal Structure
   generator (Upfront cash vs 12-month performance holdback/clawback reserve).
"""

from __future__ import annotations

import math
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yaml
from pydantic import BaseModel, Field

from .dtw_matcher import (
    DTWMatchResult,
    LifecycleArchetype,
    compute_cross_track_dtw_synchrony,
    evaluate_dtw_lifecycle,
)


RULES_DEFAULT_PATH = Path(__file__).parent / "rules.yaml"

KNOWN_DISTRIBUTORS = {
    "distrokid",
    "tunecore",
    "cd baby",
    "cdbaby",
    "amuse",
    "fuga",
    "the orchard",
    "orchard",
    "believe",
    "symphonic",
    "unitedmasters",
    "united masters",
    "onerpm",
    "routenote",
    "route note",
    "awal",
    "empire",
    "ditto",
    "landr",
    "stem",
    "vydia",
    "kontor",
    "labelworx",
    "proton",
    "zebralution",
    "kobalt",
    "songtrust",
    "sentric",
    "bmi",
    "ascap",
    "stim",
    "prs",
    "gema",
}

TIER_1_COUNTRIES = {
    "US", "GB", "UK", "DE", "SE", "NO", "DK", "FI", "NL", "CH",
    "AU", "CA", "FR", "AT", "BE", "IE", "NZ", "JP",
}

HIGH_BOT_RISK_COUNTRIES = {
    "TR", "RU", "VN", "PK", "BD", "EG", "ID", "IN", "BR", "MX",
}


class GenreFamily(str, Enum):
    AMBIENT_FUNCTIONAL = "ambient_functional"
    LOFI_CHILL = "lofi_chill"
    ELECTRONIC_DANCE = "electronic_dance"
    HIPHOP_RNB_PHONK = "hiphop_rnb_phonk"
    POP_INDIE = "pop_indie"
    ROCK_METAL_COUNTRY = "rock_metal_country"
    LATIN_AFRO = "latin_afro"
    CLASSICAL_JAZZ_INSTRUMENTAL = "classical_jazz_instrumental"
    # Backward-compatible aliases
    ELECTRONIC_INDIE = "electronic_indie"
    POP_HIPHOP_RNB = "pop_hiphop_rnb"
    ROCK_FOLK_COUNTRY = "rock_folk_country"


class RightsScope(str, Enum):
    MASTERS = "masters"
    PUBLISHING = "publishing"
    BOTH = "both"
    UNKNOWN = "unknown"


class RoyaltyBasis(str, Enum):
    NET_PAYABLE = "net_payable"
    GROSS_BEFORE_DEDUCTIONS = "gross_before_deductions"
    UNSURE = "unsure"


class RiskSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskFlag(BaseModel):
    code: str
    severity: RiskSeverity
    title: str
    description: str
    discount_rate_bps_impact: int = 0
    haircut_pct_impact: float = 0.0


class TrackInput(BaseModel):
    isrc: Optional[str] = None
    title: str
    release_date: Optional[date] = None
    age_months: Optional[float] = None
    duration_ms: Optional[int] = None
    annual_streams: Optional[int] = None
    ltm_royalties_eur: Optional[float] = None
    revenue_share: Optional[float] = None
    spotify_popularity: Optional[int] = None
    spotify_label: Optional[str] = None
    spotify_copyright: Optional[str] = None
    monthly_royalties_eur: List[float] = Field(default_factory=list)
    empirical_annual_decay_rate: Optional[float] = None


class MonthlyStatementPoint(BaseModel):
    period: str  # YYYY-MM
    net_royalties_eur: float
    streams: int = 0


class CatalogValuationInput(BaseModel):
    catalog_title: str
    artist_or_label_name: str
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    representation_type: str = "own_catalog"  # own_catalog | represented_catalog | partnership
    owner_authorized: bool = True
    listen_url: Optional[str] = None
    spotify_artist_id: Optional[str] = None

    rights_scope: RightsScope = RightsScope.MASTERS
    royalty_basis: RoyaltyBasis = RoyaltyBasis.NET_PAYABLE
    distributor_or_admin: Optional[str] = None
    ownership_share_pct: float = 100.0
    existing_releases_only: bool = True

    declared_ltm_amount: float = 0.0
    declared_currency: str = "USD"
    statements_verified: bool = False

    genres: List[str] = Field(default_factory=list)
    spotify_followers: Optional[int] = None
    spotify_popularity: Optional[int] = None

    tracks: List[TrackInput] = Field(default_factory=list)
    monthly_history: List[MonthlyStatementPoint] = Field(default_factory=list)
    dsp_share: Dict[str, float] = Field(default_factory=dict)
    country_share: Dict[str, float] = Field(default_factory=dict)
    notes: Optional[str] = None


class DealStructureRecommendation(BaseModel):
    upfront_pct: float
    holdback_pct: float
    upfront_eur: float
    holdback_eur: float
    holdback_months: int = 12
    l3m_retention_covenant_pct: float = 80.0
    rationale: str


class DiscountRateBreakdown(BaseModel):
    base_rate: float
    age_premium: float
    concentration_premium: float
    volatility_and_trend_premium: float
    forensics_integrity_premium: float
    verification_premium: float
    representation_premium: float
    total_discount_rate: float


class BaselineNormalizationReport(BaseModel):
    declared_ltm_eur: float
    statement_ltm_eur: Optional[float] = None
    distributor_fee_haircut_pct: float
    spike_clipped_eur: float
    l3m_annualized_eur: Optional[float] = None
    functional_noise_haircut_eur: float = 0.0
    subthreshold_1000_streams_haircut_eur: float = 0.0
    ownership_adjusted_baseline_eur: float
    effective_cf0_eur: float


class CohortAllocation(BaseModel):
    frontline_0_12m_share: float
    burn_in_12_24m_share: float
    mid_catalog_24_48m_share: float
    evergreen_48m_plus_share: float
    dollar_weighted_age_months: float
    blended_year1_decay_rate: float
    blended_steady_state_decay_rate: float


class CatalogValuationOutput(BaseModel):
    valuation_stage: str  # STAGE_1_INDICATIVE | STAGE_2_STATEMENT_VERIFIED
    pipeline_status: str  # MISSING_INFO | SCREENING | AWAITING_STATEMENTS | VALUATION_READY | DECLINED_BELOW_THRESHOLD
    genre_family: GenreFamily

    baseline: BaselineNormalizationReport
    cohorts: CohortAllocation
    discount_rate: DiscountRateBreakdown

    # 5-Year (60m) and 10-Year (120m) Monte Carlo DCF outputs in EUR
    npv_5y_p10_eur: float
    npv_5y_p50_eur: float
    npv_5y_p90_eur: float

    npv_10y_p10_eur: float
    npv_10y_p50_eur: float
    npv_10y_p90_eur: float

    # Selected Offer Range (cents & EUR for Offer model compatibility)
    price_low_eur: float
    price_median_eur: float
    price_high_eur: float

    price_low_cents: int
    price_median_cents: int
    price_high_cents: int

    implied_ltm_multiple_low: float
    implied_ltm_multiple_median: float
    implied_ltm_multiple_high: float
    expected_payback_months: float

    integrity_score: float  # 0 to 100
    valuation_confidence: float  # 0.0 to 1.0
    track_hhi: float
    implied_blended_rpm_usd: Optional[float] = None

    risk_flags: List[RiskFlag] = Field(default_factory=list)
    dtw_analysis: Optional[DTWMatchResult] = None
    deal_structure: DealStructureRecommendation
    yearly_projected_cashflows_p50_eur: List[float] = Field(default_factory=list)
    missing_data_fields: List[str] = Field(default_factory=list)
    qlero_bd_lead_score: int = 0
    qlero_bd_reasons: List[str] = Field(default_factory=list)


def load_rules(rules_path: Path = RULES_DEFAULT_PATH) -> Dict[str, Any]:
    if rules_path.exists():
        with open(rules_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def is_distributor_name(candidate: str) -> bool:
    if not candidate:
        return False
    cleaned = candidate.strip().lower()
    return cleaned in KNOWN_DISTRIBUTORS or any(
        cleaned == d or cleaned.startswith(f"{d} ") for d in KNOWN_DISTRIBUTORS
    )


def classify_genre_family(genres: List[str], rules: Dict[str, Any]) -> GenreFamily:
    if not genres:
        return GenreFamily.ELECTRONIC_DANCE

    joined = " ".join(g.lower() for g in genres)

    # 1. Check Lo-Fi / Chillhop Beats first (musical beats rather than pure white noise)
    if any(kw in joined for kw in ["lo-fi", "lofi", "chillhop", "study beats", "chill beats"]):
        return GenreFamily.LOFI_CHILL

    # 2. Check Ambient / Functional / Sleep / Meditation / White Noise
    func_keywords = rules.get("FUNCTIONAL_NOISE_POLICY", {}).get(
        "functional_genres",
        [
            "ambient", "sleep", "white noise", "rain", "nature",
            "meditation", "wellness", "asmr", "soundscape", "binaural", "drone", "spa",
        ],
    )
    if any(kw in joined for kw in func_keywords):
        return GenreFamily.AMBIENT_FUNCTIONAL

    # 3. Classical / Neo-Classical / Jazz / Instrumental Acoustic
    if any(kw in joined for kw in ["classical", "neo-classical", "neoclassical", "orchestral", "jazz", "bossa", "solo piano", "acoustic instrumental"]):
        return GenreFamily.CLASSICAL_JAZZ_INSTRUMENTAL

    # 4. Latin / Reggaeton / Afrobeats / Brazilian Funk
    if any(kw in joined for kw in ["reggaeton", "latin", "urbano", "afrobeats", "afropop", "amapiano", "baile funk", "bachata", "salsa", "regional mexicano"]):
        return GenreFamily.LATIN_AFRO

    # 5. Hip-Hop / R&B / Phonk / Rap / Trap / Drill
    if any(kw in joined for kw in ["hip hop", "hip-hop", "rap", "trap", "drill", "r&b", "rnb", "phonk", "drift phonk"]):
        return GenreFamily.HIPHOP_RNB_PHONK

    # 6. Rock / Metal / Folk / Country / Americana
    if any(kw in joined for kw in ["rock", "metal", "punk", "grunge", "folk", "country", "americana", "blues", "bluegrass"]):
        return GenreFamily.ROCK_METAL_COUNTRY

    # 7. Electronic / House / Techno / EDM / Drum & Bass
    if any(kw in joined for kw in ["electronic", "house", "techno", "trance", "edm", "drum and bass", "dnb", "dubstep", "synthwave", "electro", "club"]):
        return GenreFamily.ELECTRONIC_DANCE

    # 8. Pop / Indie Pop / Singer-Songwriter
    if any(kw in joined for kw in ["pop", "indie", "singer-songwriter", "alt-pop", "synthpop"]):
        return GenreFamily.POP_INDIE

    return GenreFamily.ELECTRONIC_DANCE


def lookup_distributor_fee(
    distributor_name: Optional[str],
    royalty_basis: RoyaltyBasis,
    rules: Dict[str, Any],
) -> float:
    if royalty_basis == RoyaltyBasis.NET_PAYABLE:
        return 0.0

    fees = rules.get("DISTRIBUTOR_FEES", {})
    if not distributor_name:
        return fees.get("default_unknown", 0.12) if royalty_basis == RoyaltyBasis.GROSS_BEFORE_DEDUCTIONS else 0.06

    norm = distributor_name.strip().lower().replace(" ", "_")
    for key, val in fees.items():
        if key in norm or norm in key:
            # If user answered "unsure", apply half the nominal fee or a conservative 5% buffer
            return float(val) if royalty_basis == RoyaltyBasis.GROSS_BEFORE_DEDUCTIONS else float(val) * 0.5

    default_fee = float(fees.get("default_unknown", 0.12))
    return default_fee if royalty_basis == RoyaltyBasis.GROSS_BEFORE_DEDUCTIONS else default_fee * 0.5


def convert_to_eur(amount: float, currency: str, rules: Dict[str, Any]) -> float:
    fx_map = rules.get(
        "FX_RATES_TO_EUR",
        {"EUR": 1.0, "USD": 0.92, "GBP": 1.17, "SEK": 0.088, "CAD": 0.67, "AUD": 0.60},
    )
    rate = float(fx_map.get((currency or "EUR").upper().strip(), 0.92))
    return amount * rate


def winsorize_monthly_spikes(monthly_values: List[float], mad_multiplier: float = 3.0) -> Tuple[List[float], float]:
    """
    Clips abnormal 1-3 month promotional/viral spikes using Median + k * MAD (robust to outliers).
    Returns (clipped_series, total_clipped_excess).
    """
    if len(monthly_values) < 4:
        return list(monthly_values), 0.0

    arr = np.array(monthly_values, dtype=float)
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    # Consistent normal-equivalent sigma from MAD
    robust_sigma = max(1.4826 * mad, 0.10 * median)
    cap = median + mad_multiplier * robust_sigma

    clipped = np.minimum(arr, cap)
    excess = float(np.sum(arr - clipped))
    return clipped.tolist(), max(0.0, excess)


def compute_empirical_track_Slope(monthly_royalties: List[float]) -> Optional[float]:
    """
    Estimates annualized exponential decay rate from a track's monthly royalty series.
    Returns positive value for decay (e.g. 0.20 = 20% annual decline), negative for growth (capped at -0.05).
    """
    clean = [max(v, 1e-2) for v in monthly_royalties if v is not None and v >= 0]
    if len(clean) < 6:
        return None

    x = np.arange(len(clean), dtype=float)
    y = np.log(np.array(clean, dtype=float))
    # Linear regression on log(royalty) vs month index: y = a + b*x
    slope_monthly, _ = np.polyfit(x, y, 1)
    # Annualized decay rate: if slope_monthly is negative, decay rate is positive
    annual_decay = float(1.0 - math.exp(12.0 * slope_monthly))
    return max(-0.05, min(0.80, annual_decay))


class SpaceValuationEngine:
    """
    Core valuation and due diligence engine for SPACE (spacemusic.io).
    Independent, zero external proprietary dependencies, deterministic seed support.
    """

    def __init__(self, rules_path: Path = RULES_DEFAULT_PATH, random_seed: int = 42):
        self.rules = load_rules(rules_path)
        self.random_seed = random_seed

    def evaluate(
        self,
        inp: CatalogValuationInput,
        reference_date: Optional[date] = None,
        n_simulations: int = 1000,
    ) -> CatalogValuationOutput:
        ref_date = reference_date or date.today()
        risk_flags: List[RiskFlag] = []
        missing_fields: List[str] = []

        # ------------------------------------------------------------------
        # 0. Input Validation & Triage
        # ------------------------------------------------------------------
        if not inp.artist_or_label_name or is_distributor_name(inp.artist_or_label_name):
            missing_fields.append("artist_or_label_name (applicant entered distributor name instead of artist/label)")
            risk_flags.append(
                RiskFlag(
                    code="DISTRIBUTOR_AS_ARTIST_NAME",
                    severity=RiskSeverity.HIGH,
                    title="Distributor Name Entered as Artist/Label",
                    description=(
                        f"Applicant provided '{inp.artist_or_label_name}' which matches a distributor/aggregator "
                        "rather than the underlying recording artist or label."
                    ),
                    discount_rate_bps_impact=150,
                )
            )

        if not inp.listen_url and not inp.spotify_artist_id and not inp.statements_verified:
            missing_fields.append("listen_url (public Spotify or DSP artist/catalog link)")

        if inp.declared_ltm_amount <= 0 and not inp.monthly_history:
            missing_fields.append("declared_ltm_amount (last 12 months royalty income or statement upload)")

        if inp.representation_type == "represented_catalog" and not inp.owner_authorized:
            missing_fields.append("owner_authorization (representative has not yet confirmed owner mandate)")
            risk_flags.append(
                RiskFlag(
                    code="UNCONFIRMED_REPRESENTATION_MANDATE",
                    severity=RiskSeverity.HIGH,
                    title="Unconfirmed Owner Mandate",
                    description="Representative indicated they still need to confirm authorization with the catalog owner.",
                    discount_rate_bps_impact=300,
                )
            )

        genre_family = classify_genre_family(inp.genres, self.rules)

        # ------------------------------------------------------------------
        # 1. Layer 1: Baseline Normalization (CF_0)
        # ------------------------------------------------------------------
        declared_ltm_eur = convert_to_eur(inp.declared_ltm_amount, inp.declared_currency, self.rules)
        dist_fee_pct = lookup_distributor_fee(inp.distributor_or_admin, inp.royalty_basis, self.rules)

        statement_ltm_eur: Optional[float] = None
        spike_clipped_eur = 0.0
        l3m_annualized_eur: Optional[float] = None

        if inp.monthly_history:
            sorted_hist = sorted(inp.monthly_history, key=lambda m: m.period)
            last_12 = sorted_hist[-12:]
            raw_monthly = [m.net_royalties_eur for m in last_12]
            scale_factor = 12.0 / max(1, len(raw_monthly))
            statement_ltm_eur = float(sum(raw_monthly) * scale_factor)

            clipped_monthly, excess = winsorize_monthly_spikes(raw_monthly, mad_multiplier=3.0)
            spike_clipped_eur = excess * scale_factor

            if spike_clipped_eur > 0.12 * max(1.0, statement_ltm_eur):
                risk_flags.append(
                    RiskFlag(
                        code="PROMO_OR_VIRAL_SPIKE_CLIPPED",
                        severity=RiskSeverity.MEDIUM,
                        title="Abnormal Monthly Royalty Spike Clipped",
                        description=(
                            f"Detected €{spike_clipped_eur:,.0f} in non-recurring monthly spike revenue above 3x MAD. "
                            "Baseline cash flow was Winsorized to prevent overpaying for temporary playlist spikes."
                        ),
                        discount_rate_bps_impact=150,
                    )
                )

            clipped_ltm_eur = float(sum(clipped_monthly) * scale_factor)
            if len(clipped_monthly) >= 6:
                l3m_annualized_eur = float(sum(clipped_monthly[-3:]) * 4.0)
                first_half = sum(clipped_monthly[: len(clipped_monthly) // 2])
                second_half = sum(clipped_monthly[len(clipped_monthly) // 2 :])
                if first_half > 0:
                    decline_ratio = (first_half - second_half) / first_half
                    decline_threshold = float(
                        self.rules.get("STREAM_DECLINE", {}).get("threshold_percentage", 0.30)
                    )
                    if decline_ratio >= decline_threshold:
                        risk_flags.append(
                            RiskFlag(
                                code="SEVERE_LTM_MOMENTUM_DECLINE",
                                severity=RiskSeverity.HIGH,
                                title="Steep Intra-Year Revenue Decline",
                                description=(
                                    f"Second-half royalties declined by {decline_ratio * 100:.1f}% compared to "
                                    f"first-half (exceeding {decline_threshold * 100:.0f}% threshold)."
                                ),
                                discount_rate_bps_impact=250,
                            )
                        )
            base_pre_fee_eur = clipped_ltm_eur
        else:
            base_pre_fee_eur = declared_ltm_eur

        net_after_dist_eur = base_pre_fee_eur * (1.0 - dist_fee_pct)

        # Momentum anchor: if L3M run-rate is lower than LTM, anchor CF_0 downward
        if l3m_annualized_eur is not None:
            l3m_net = l3m_annualized_eur * (1.0 - dist_fee_pct)
            momentum_weighted = min(net_after_dist_eur, 0.40 * net_after_dist_eur + 0.60 * l3m_net)
        else:
            momentum_weighted = net_after_dist_eur

        ownership_ratio = max(0.0, min(1.0, inp.ownership_share_pct / 100.0))
        ownership_adjusted_eur = momentum_weighted * ownership_ratio

        # ------------------------------------------------------------------
        # 2. Layer 2 & 3: Track Forensics & Cohort Survival Analysis
        # ------------------------------------------------------------------
        func_noise_haircut_eur = 0.0
        subthreshold_haircut_eur = 0.0

        tracks = inp.tracks or []
        total_track_rev = sum(max(0.0, t.ltm_royalties_eur or 0.0) for t in tracks)
        total_track_streams = sum(max(0, t.annual_streams or 0) for t in tracks)

        # Compute track revenue weights
        track_weights: List[float] = []
        track_ages_months: List[float] = []
        track_year1_decays: List[float] = []
        track_steady_decays: List[float] = []

        cohort_shares = {
            "frontline_0_12m": 0.0,
            "burn_in_12_24m": 0.0,
            "mid_catalog_24_48m": 0.0,
            "evergreen_48m_plus": 0.0,
        }

        priors = self.rules.get("COHORT_DECAY_PRIORS", {}).get(
            genre_family.value,
            {
                "frontline_0_12m": 0.40,
                "burn_in_12_24m": 0.20,
                "mid_catalog_24_48m": 0.10,
                "evergreen_48m_plus": 0.04,
            },
        )

        short_functional_share = 0.0
        subthreshold_stream_share = 0.0
        mismatched_label_share = 0.0

        min_func_duration_ms = int(
            self.rules.get("FUNCTIONAL_NOISE_POLICY", {}).get("min_duration_ms", 120000)
        )
        short_track_haircut_rate = float(
            self.rules.get("FUNCTIONAL_NOISE_POLICY", {}).get("short_track_haircut", 0.85)
        )
        stream_floor = int(
            self.rules.get("SPOTIFY_1000_STREAM_THRESHOLD", {}).get("annual_stream_floor", 1000)
        )
        stream_warning_zone = int(
            self.rules.get("SPOTIFY_1000_STREAM_THRESHOLD", {}).get("warning_zone_streams", 1800)
        )

        if tracks:
            for idx, t in enumerate(tracks):
                if t.revenue_share is not None and t.revenue_share > 0:
                    w = float(t.revenue_share)
                elif total_track_rev > 0 and t.ltm_royalties_eur is not None:
                    w = max(0.0, float(t.ltm_royalties_eur)) / total_track_rev
                elif total_track_streams > 0 and t.annual_streams is not None:
                    w = max(0.0, float(t.annual_streams)) / total_track_streams
                elif t.spotify_popularity is not None:
                    w = float(max(1, t.spotify_popularity))
                else:
                    w = 1.0 / len(tracks)
                track_weights.append(w)

            w_sum = sum(track_weights) or 1.0
            track_weights = [w / w_sum for w in track_weights]

            for t, w in zip(tracks, track_weights):
                # Determine age in months
                if t.age_months is not None:
                    age_m = max(1.0, float(t.age_months))
                elif t.release_date is not None:
                    days = max(30, (ref_date - t.release_date).days)
                    age_m = days / 30.4375
                else:
                    age_m = 24.0  # Default mid-catalog assumption when release_date is missing
                track_ages_months.append(age_m)

                # Cohort bucket
                if age_m < 12.0:
                    cohort_key = "frontline_0_12m"
                elif age_m < 24.0:
                    cohort_key = "burn_in_12_24m"
                elif age_m < 48.0:
                    cohort_key = "mid_catalog_24_48m"
                else:
                    cohort_key = "evergreen_48m_plus"
                cohort_shares[cohort_key] += w

                prior_decay = float(priors.get(cohort_key, 0.15))
                emp_decay = t.empirical_annual_decay_rate
                if emp_decay is None and t.monthly_royalties_eur:
                    emp_decay = compute_empirical_track_Slope(t.monthly_royalties_eur)

                # Empirical Bayes shrinkage: n / (n + 12)
                if emp_decay is not None:
                    n_obs = max(6, len(t.monthly_royalties_eur))
                    shrinkage_w = n_obs / (n_obs + 12.0)
                    post_decay = shrinkage_w * emp_decay + (1.0 - shrinkage_w) * prior_decay
                else:
                    post_decay = prior_decay

                # DTW shape-based trajectory refinement if track has >=6 monthly points
                if len(t.monthly_royalties_eur) >= 6:
                    track_dtw = evaluate_dtw_lifecycle(t.monthly_royalties_eur)
                    if track_dtw is not None and track_dtw.dtw_blend_weight > 0:
                        bw = track_dtw.dtw_blend_weight
                        post_decay = (1.0 - bw) * post_decay + bw * track_dtw.dtw_implied_annual_decay_rate

                track_year1_decays.append(post_decay)
                # Steady-state (year 4+) decay converges toward evergreen prior
                steady_prior = float(priors.get("evergreen_48m_plus", 0.04))
                track_steady_decays.append(0.35 * post_decay + 0.65 * steady_prior)

                # Forensics Check 1: Functional noise <120,000 ms (2 minutes)
                if (
                    genre_family == GenreFamily.AMBIENT_FUNCTIONAL
                    and t.duration_ms is not None
                    and t.duration_ms < min_func_duration_ms
                ):
                    short_functional_share += w

                # Forensics Check 2: Spotify <1,000 stream demonetization trap
                if t.annual_streams is not None and t.annual_streams < stream_warning_zone:
                    if t.annual_streams < stream_floor:
                        subthreshold_stream_share += w
                    else:
                        # Tracks between 1,000 and 1,800 streams have ~50% probability of dropping below 1,000 in Year 1-2
                        subthreshold_stream_share += 0.5 * w

                # Forensics Check 3: Label / Copyright mismatch vs declared artist/label
                if t.spotify_label and inp.artist_or_label_name and not is_distributor_name(inp.artist_or_label_name):
                    declared_norm = inp.artist_or_label_name.strip().lower()
                    label_norm = t.spotify_label.strip().lower()
                    dist_norm = (inp.distributor_or_admin or "").strip().lower()
                    if (
                        declared_norm not in label_norm
                        and label_norm not in declared_norm
                        and (not dist_norm or dist_norm not in label_norm)
                        and not any(dk in label_norm for dk in ["records dk", "distrokid", "tunecore", "self-released"])
                    ):
                        mismatched_label_share += w
        else:
            # Stage 1 without track-level breakdown: assume conservative Burn-in / Mid-Catalog blend
            cohort_shares = {
                "frontline_0_12m": 0.25,
                "burn_in_12_24m": 0.35,
                "mid_catalog_24_48m": 0.25,
                "evergreen_48m_plus": 0.15,
            }
            track_ages_months = [22.0]
            track_weights = [1.0]
            blended_prior = sum(cohort_shares[k] * float(priors[k]) for k in cohort_shares)
            track_year1_decays = [blended_prior]
            track_steady_decays = [float(priors.get("evergreen_48m_plus", 0.04)) * 1.25]

        # Apply haircuts for functional noise <2m and sub-1000 stream tracks
        if short_functional_share > 0.05:
            func_noise_haircut_eur = ownership_adjusted_eur * short_functional_share * short_track_haircut_rate
            risk_flags.append(
                RiskFlag(
                    code="SPOTIFY_FUNCTIONAL_NOISE_UNDER_2MIN",
                    severity=RiskSeverity.CRITICAL if short_functional_share > 0.30 else RiskSeverity.HIGH,
                    title="Functional/Ambient Tracks Under 2-Minute Threshold",
                    description=(
                        f"{short_functional_share * 100:.1f}% of catalog weight is in functional/ambient tracks "
                        f"shorter than 120 seconds. Under Spotify's royalty policy, <2m functional noise tracks "
                        f"face demonetization or severe stream-share reduction (€{func_noise_haircut_eur:,.0f} haircut applied)."
                    ),
                    discount_rate_bps_impact=300 if short_functional_share > 0.30 else 150,
                    haircut_pct_impact=short_functional_share * short_track_haircut_rate,
                )
            )

        if subthreshold_stream_share > 0.10:
            subthreshold_haircut_eur = (
                (ownership_adjusted_eur - func_noise_haircut_eur) * subthreshold_stream_share * 0.60
            )
            risk_flags.append(
                RiskFlag(
                    code="SPOTIFY_1000_STREAM_THRESHOLD_TRAP",
                    severity=RiskSeverity.HIGH if subthreshold_stream_share > 0.25 else RiskSeverity.MEDIUM,
                    title="High Exposure to Spotify 1,000-Stream Annual Threshold",
                    description=(
                        f"{subthreshold_stream_share * 100:.1f}% of catalog weight sits below or near Spotify's "
                        "1,000 annual stream monetization floor and will generate $0 once decayed below 1,000 streams/yr."
                    ),
                    discount_rate_bps_impact=200,
                    haircut_pct_impact=subthreshold_stream_share * 0.60,
                )
            )

        if mismatched_label_share > 0.15:
            risk_flags.append(
                RiskFlag(
                    code="COPYRIGHT_P_LINE_MISMATCH",
                    severity=RiskSeverity.HIGH,
                    title="Spotify P/C-Line Label Mismatch",
                    description=(
                        f"{mismatched_label_share * 100:.1f}% of catalog revenue weight is released under third-party "
                        "label P-lines on Spotify that do not match the declared artist/label or distributor."
                    ),
                    discount_rate_bps_impact=250,
                )
            )

        effective_cf0_eur = max(
            0.0, ownership_adjusted_eur - func_noise_haircut_eur - subthreshold_haircut_eur
        )

        # Compute HHI (Herfindahl-Hirschman Index) for track concentration
        if len(tracks) >= 2:
            track_hhi = float(sum(w * w for w in track_weights))
        else:
            # When track list is not yet provided or single track, assume moderate-high concentration (0.38)
            track_hhi = 1.0 if len(tracks) == 1 else 0.38

        if track_hhi >= 0.50:
            risk_flags.append(
                RiskFlag(
                    code="HIGH_SINGLE_TRACK_CONCENTRATION",
                    severity=RiskSeverity.HIGH,
                    title="High Single-Track Revenue Concentration",
                    description=(
                        f"Catalog Herfindahl-Hirschman Index (HHI) is {track_hhi:.2f} (>0.50 threshold), "
                        "indicating extreme dependence on 1-2 top tracks."
                    ),
                    discount_rate_bps_impact=300,
                )
            )

        # Forensics Check 4: Implied Net Per-Stream Yield (RPM) & Bot/Geo Risk
        implied_rpm_usd: Optional[float] = None
        total_hist_streams = sum(m.streams for m in inp.monthly_history) if inp.monthly_history else total_track_streams
        if total_hist_streams > 0 and effective_cf0_eur > 0:
            usd_rate = float(self.rules.get("FX_RATES_TO_EUR", {}).get("USD", 0.92))
            effective_usd = effective_cf0_eur / usd_rate
            implied_rpm_usd = effective_usd / float(total_hist_streams)

            rpm_cfg = self.rules.get("RPM_BENCHMARKS_USD_PER_STREAM", {}).get("spotify", {})
            if genre_family == GenreFamily.AMBIENT_FUNCTIONAL:
                min_rpm = float(rpm_cfg.get("functional_noise_min", 0.0004))
            elif genre_family == GenreFamily.LATIN_AFRO:
                min_rpm = float(rpm_cfg.get("latin_afro_min", 0.0009))
            else:
                min_rpm = float(rpm_cfg.get("blended_min", 0.0014))
            max_rpm = float(rpm_cfg.get("blended_max", 0.0058)) * 1.5

            if implied_rpm_usd < min_rpm or implied_rpm_usd > max_rpm:
                risk_flags.append(
                    RiskFlag(
                        code="IMPLIED_RPM_YIELD_ANOMALY",
                        severity=RiskSeverity.HIGH,
                        title="Abnormal Implied Per-Stream Payout Rate (RPM)",
                        description=(
                            f"Implied net payout rate is ${implied_rpm_usd:.5f}/stream (expected benchmark range "
                            f"${min_rpm:.4f}-${max_rpm:.4f}), indicating either heavy discounted/ad-tier dilution "
                            "or unverified royalty figures."
                        ),
                        discount_rate_bps_impact=200,
                    )
                )

        # Forensics Check 5: Geographic Concentration & Artificial Stream Exposure
        if inp.country_share:
            max_country, max_c_share = max(inp.country_share.items(), key=lambda kv: kv[1])
            high_risk_share = sum(
                share for c, share in inp.country_share.items() if c.upper() in HIGH_BOT_RISK_COUNTRIES
            )
            max_single_c_limit = float(
                self.rules.get("GEO_CONCENTRATION", {}).get("max_single_country_percentage", 0.70)
            )
            if max_c_share > max_single_c_limit and max_country.upper() not in TIER_1_COUNTRIES:
                risk_flags.append(
                    RiskFlag(
                        code="NON_TIER1_GEO_CONCENTRATION",
                        severity=RiskSeverity.HIGH,
                        title=f"High Single-Country Concentration ({max_country})",
                        description=(
                            f"{max_c_share * 100:.1f}% of streams originate from {max_country} "
                            f"(above {max_single_c_limit * 100:.0f}% threshold in non-Tier-1 market)."
                        ),
                        discount_rate_bps_impact=250,
                    )
                )
            elif high_risk_share > 0.55:
                risk_flags.append(
                    RiskFlag(
                        code="HIGH_BOT_RISK_TERRITORY_MIX",
                        severity=RiskSeverity.MEDIUM,
                        title="Elevated High-Fraud Territory Stream Share",
                        description=(
                            f"{high_risk_share * 100:.1f}% of streams come from territories with elevated "
                            "artificial-streaming clawback rates and low per-stream yield."
                        ),
                        discount_rate_bps_impact=175,
                    )
                )

        # Forensics Check 6: Follower-to-Royalty Organic Sanity Check
        if (
            inp.spotify_followers is not None
            and inp.spotify_followers < 250
            and effective_cf0_eur > 15000
            and genre_family not in {GenreFamily.AMBIENT_FUNCTIONAL, GenreFamily.LOFI_CHILL, GenreFamily.CLASSICAL_JAZZ_INSTRUMENTAL}
        ):
            risk_flags.append(
                RiskFlag(
                    code="LOW_ORGANIC_FOLLOWER_TO_REVENUE_RATIO",
                    severity=RiskSeverity.MEDIUM,
                    title="High Declared Royalties Relative to Organic Artist Followers",
                    description=(
                        f"Artist has only {inp.spotify_followers} Spotify followers while claiming "
                        f"€{effective_cf0_eur:,.0f}/yr in non-functional genres — verify third-party playlist dependency."
                    ),
                    discount_rate_bps_impact=175,
                )
            )

        # Forensics Check 7: Genre-Specific Sample / Beat-Lease Clearance Risk (Hip-Hop / Phonk / R&B)
        if genre_family in {GenreFamily.HIPHOP_RNB_PHONK, GenreFamily.POP_HIPHOP_RNB}:
            notes_lower = (inp.notes or "").lower()
            if any(kw in notes_lower for kw in ["lease", "beatstars", "uncleared", "sample", "type beat", "non-exclusive"]):
                risk_flags.append(
                    RiskFlag(
                        code="BEAT_LEASE_OR_SAMPLE_CLEARANCE_RISK",
                        severity=RiskSeverity.HIGH,
                        title="Beat-Lease or Uncleared Sample Exposure",
                        description=(
                            "Applicant notes reference beat leases, type beats, or sample usage in a Hip-Hop/Phonk/R&B catalog. "
                            "Require exclusive master producer agreements and sample clearance documentation before closing."
                        ),
                        discount_rate_bps_impact=250,
                    )
                )

        # Forensics Check 8: Dynamic Time Warping (DTW) Lifecycle Archetype & Step-Plateau Fraud Detection
        dtw_result: Optional[DTWMatchResult] = None
        dtw_cfg = self.rules.get("DTW_MODEL", {})
        dtw_series: List[float] = []
        if inp.monthly_history and len(inp.monthly_history) >= int(dtw_cfg.get("min_months_for_dtw", 6)):
            sorted_mh = sorted(inp.monthly_history, key=lambda m: m.period)
            dtw_series = [m.net_royalties_eur for m in sorted_mh]
        elif tracks and any(len(t.monthly_royalties_eur) >= 6 for t in tracks):
            longest_track = max(tracks, key=lambda t: len(t.monthly_royalties_eur))
            dtw_series = longest_track.monthly_royalties_eur

        if len(dtw_series) >= 6:
            dtw_result = evaluate_dtw_lifecycle(
                dtw_series,
                window=int(dtw_cfg.get("sakoe_chiba_band_months", 3)),
                sigma=float(dtw_cfg.get("kernel_bandwidth_sigma", 0.35)),
                max_blend_weight=float(dtw_cfg.get("max_dtw_blend_weight", 0.55)),
                step_threshold=float(dtw_cfg.get("step_plateau_distance_threshold", 0.18)),
            )
            if dtw_result is not None:
                # Check cross-track synchrony if multiple tracks have monthly series
                track_series_list = [t.monthly_royalties_eur for t in tracks if len(t.monthly_royalties_eur) >= 6]
                sync_score = compute_cross_track_dtw_synchrony(track_series_list)
                dtw_result.cross_track_synchrony_score = sync_score

                if dtw_result.is_artificial_step_plateau:
                    risk_flags.append(
                        RiskFlag(
                            code="DTW_ARTIFICIAL_STEP_PLATEAU",
                            severity=RiskSeverity.CRITICAL,
                            title="DTW Rectangular Step-Plateau Detected (Paid Playlist/Bot Signature)",
                            description=(
                                f"Dynamic Time Warping matched the monthly revenue curve to an ARTIFICIAL_STEP_PLATEAU "
                                f"(DTW distance {dtw_result.dtw_distance:.3f}). The catalog exhibits a sudden flat ceiling "
                                "with near-zero organic variance typical of fixed-volume paid playlisting or stream farming."
                            ),
                            discount_rate_bps_impact=350,
                        )
                    )
                elif dtw_result.matched_archetype == LifecycleArchetype.VIRAL_SPIKE_CRASH and dtw_result.dtw_distance < 0.22:
                    risk_flags.append(
                        RiskFlag(
                            code="DTW_VIRAL_CRASH_TRAJECTORY",
                            severity=RiskSeverity.MEDIUM,
                            title="DTW Viral Spike-Crash Lifecycle Shape",
                            description=(
                                f"DTW shape analysis classified the catalog trajectory as VIRAL_SPIKE_CRASH "
                                f"(similarity {dtw_result.similarity_score * 100:.0f}%), projecting steeper post-peak decay."
                            ),
                            discount_rate_bps_impact=150,
                        )
                    )

                if sync_score is not None and sync_score > 0.88:
                    risk_flags.append(
                        RiskFlag(
                            code="DTW_CROSS_TRACK_SYNCHRONY_ANOMALY",
                            severity=RiskSeverity.HIGH,
                            title="Abnormal Cross-Track DTW Synchrony Across Catalog",
                            description=(
                                f"Multiple tracks exhibit {sync_score * 100:.1f}% synchronized DTW shape similarity "
                                "despite independent release histories, indicating catalog-wide promotional playlist injection."
                            ),
                            discount_rate_bps_impact=225,
                        )
                    )

                # Blend catalog-level DTW decay into track_year1_decays when tracks lacked individual monthly series
                if not any(len(t.monthly_royalties_eur) >= 6 for t in tracks) and dtw_result.dtw_blend_weight > 0:
                    bw = dtw_result.dtw_blend_weight
                    track_year1_decays = [
                        (1.0 - bw) * d + bw * dtw_result.dtw_implied_annual_decay_rate
                        for d in track_year1_decays
                    ]

        dollar_weighted_age_months = float(
            sum(a * w for a, w in zip(track_ages_months, track_weights))
        )
        blended_y1_decay = float(
            sum(d * w for d, w in zip(track_year1_decays, track_weights))
        )
        blended_steady_decay = float(
            sum(d * w for d, w in zip(track_steady_decays, track_weights))
        )

        cohorts_report = CohortAllocation(
            frontline_0_12m_share=round(cohort_shares["frontline_0_12m"], 4),
            burn_in_12_24m_share=round(cohort_shares["burn_in_12_24m"], 4),
            mid_catalog_24_48m_share=round(cohort_shares["mid_catalog_24_48m"], 4),
            evergreen_48m_plus_share=round(cohort_shares["evergreen_48m_plus"], 4),
            dollar_weighted_age_months=round(dollar_weighted_age_months, 1),
            blended_year1_decay_rate=round(blended_y1_decay, 4),
            blended_steady_state_decay_rate=round(blended_steady_decay, 4),
        )

        # ------------------------------------------------------------------
        # 3. Layer 4: Dynamic Risk-Adjusted Discount Rate (r)
        # ------------------------------------------------------------------
        dr_cfg = self.rules.get("DISCOUNT_RATE_MODEL", {})
        if inp.rights_scope == RightsScope.PUBLISHING:
            base_rate = float(dr_cfg.get("base_rate_publishing", 0.105))
        elif inp.rights_scope == RightsScope.BOTH:
            base_rate = float(dr_cfg.get("base_rate_both", 0.11))
        else:
            base_rate = float(dr_cfg.get("base_rate_masters", 0.12))

        # Age premium: 0% at >=48m, up to +6.0% at <=6m
        age_premium = max(0.0, min(0.06, (48.0 - min(48.0, dollar_weighted_age_months)) / 42.0 * 0.06))

        # Concentration premium: 0% at HHI <= 0.10, up to +4.5% at HHI >= 0.65
        conc_premium = max(0.0, min(0.045, (track_hhi - 0.10) / 0.55 * 0.045))

        # Volatility & trend premium from monthly statements
        vol_premium = 0.0
        if inp.monthly_history and len(inp.monthly_history) >= 6:
            vals = np.array([m.net_royalties_eur for m in inp.monthly_history[-12:]], dtype=float)
            mean_v = float(np.mean(vals))
            if mean_v > 0:
                cv = float(np.std(vals) / mean_v)
                vol_premium = min(0.04, max(0.0, (cv - 0.15) * 0.06))

        # Forensics premium from risk flags (excluding representation/verification which are tracked explicitly)
        forensics_bps = sum(
            rf.discount_rate_bps_impact
            for rf in risk_flags
            if rf.code not in {"UNCONFIRMED_REPRESENTATION_MANDATE"}
        )
        forensics_premium = min(0.06, forensics_bps / 10000.0)

        verification_premium = (
            0.0
            if inp.statements_verified
            else float(dr_cfg.get("unverified_statement_penalty", 0.05))
        )
        representation_premium = (
            float(dr_cfg.get("unconfirmed_representation_penalty", 0.03))
            if (inp.representation_type == "represented_catalog" and not inp.owner_authorized)
            else 0.0
        )

        raw_discount_rate = (
            base_rate
            + age_premium
            + conc_premium
            + vol_premium
            + forensics_premium
            + verification_premium
            + representation_premium
        )
        total_discount_rate = max(
            float(dr_cfg.get("min_discount_rate", 0.095)),
            min(float(dr_cfg.get("max_discount_rate", 0.28)), raw_discount_rate),
        )

        discount_breakdown = DiscountRateBreakdown(
            base_rate=round(base_rate, 4),
            age_premium=round(age_premium, 4),
            concentration_premium=round(conc_premium, 4),
            volatility_and_trend_premium=round(vol_premium, 4),
            forensics_integrity_premium=round(forensics_premium, 4),
            verification_premium=round(verification_premium, 4),
            representation_premium=round(representation_premium, 4),
            total_discount_rate=round(total_discount_rate, 4),
        )

        # ------------------------------------------------------------------
        # 4. Integrity Score & Confidence Score
        # ------------------------------------------------------------------
        penalty_points = sum(
            25
            if rf.severity == RiskSeverity.CRITICAL
            else 15
            if rf.severity == RiskSeverity.HIGH
            else 8
            if rf.severity == RiskSeverity.MEDIUM
            else 3
            for rf in risk_flags
        )
        integrity_score = float(max(5.0, min(100.0, 100.0 - penalty_points)))

        # Confidence reflects data completeness + integrity
        base_conf = 0.82 if inp.statements_verified else 0.55
        if len(inp.monthly_history) >= 12:
            base_conf += 0.08
        if len(tracks) >= 3:
            base_conf += 0.05
        if missing_fields:
            base_conf -= 0.25
        valuation_confidence = round(
            max(0.10, min(0.98, base_conf * (0.5 + 0.5 * (integrity_score / 100.0)))), 3
        )

        # ------------------------------------------------------------------
        # 5. Layer 5: Monte Carlo Cohort DCF (60m and 120m)
        # ------------------------------------------------------------------
        (
            npv_5y_p10,
            npv_5y_p50,
            npv_5y_p90,
            npv_10y_p10,
            npv_10y_p50,
            npv_10y_p90,
            yearly_cfs_p50,
            payback_months,
        ) = self._run_monte_carlo_dcf(
            cf0_annual_eur=effective_cf0_eur,
            track_weights=track_weights,
            track_ages_months=track_ages_months,
            track_y1_decays=track_year1_decays,
            track_steady_decays=track_steady_decays,
            annual_discount_rate=total_discount_rate,
            statements_verified=inp.statements_verified,
            n_simulations=n_simulations,
        )

        # Offer pricing selection:
        # Weight between 5-year and 10-year DCF based on catalog maturity (evergreen share).
        # Mature catalogs (>36-48m) have proven longevity and command 10-year + terminal tail weight;
        # young catalogs (<18m) are anchored primarily to the 5-year horizon.
        maturity_weight_10y = min(0.85, max(0.30, dollar_weighted_age_months / 60.0))
        maturity_weight_5y = 1.0 - maturity_weight_10y

        price_low_eur = round(npv_5y_p10, 2)
        price_median_eur = round(maturity_weight_5y * npv_5y_p50 + maturity_weight_10y * npv_10y_p50, 2)
        price_high_eur = round(0.35 * npv_5y_p90 + 0.65 * npv_10y_p90, 2)

        # Stage 1 cap: never quote above 5.5x on unverified self-reported numbers
        if not inp.statements_verified and effective_cf0_eur > 0:
            max_unverified_eur = effective_cf0_eur * 5.5
            price_median_eur = min(price_median_eur, round(max_unverified_eur, 2))
            price_high_eur = max(price_median_eur, min(price_high_eur, round(effective_cf0_eur * 6.5, 2)))

        denom = max(1.0, effective_cf0_eur)
        mult_low = round(price_low_eur / denom, 2) if effective_cf0_eur > 0 else 0.0
        mult_med = round(price_median_eur / denom, 2) if effective_cf0_eur > 0 else 0.0
        mult_high = round(price_high_eur / denom, 2) if effective_cf0_eur > 0 else 0.0

        # Deal Structure (Upfront vs 12m Holdback)
        deal_structure = self._build_deal_structure(
            offer_median_eur=price_median_eur,
            integrity_score=integrity_score,
            dollar_weighted_age_months=dollar_weighted_age_months,
            track_hhi=track_hhi,
            statements_verified=inp.statements_verified,
        )

        # Pipeline status & Qlero BD cross-sell scoring
        valuation_stage = (
            "STAGE_2_STATEMENT_VERIFIED" if inp.statements_verified else "STAGE_1_INDICATIVE"
        )
        if inp.representation_type == "partnership":
            pipeline_status = "PARTNERSHIP_BD"
        elif missing_fields:
            pipeline_status = "MISSING_INFO"
        elif effective_cf0_eur < 1500.0:
            pipeline_status = "DECLINED_BELOW_THRESHOLD"
        elif not inp.statements_verified:
            pipeline_status = "AWAITING_STATEMENTS"
        else:
            pipeline_status = "VALUATION_READY"

        qlero_score, qlero_reasons = self._score_bd_and_royalty_accounting_fit(inp)

        baseline_report = BaselineNormalizationReport(
            declared_ltm_eur=round(declared_ltm_eur, 2),
            statement_ltm_eur=round(statement_ltm_eur, 2) if statement_ltm_eur is not None else None,
            distributor_fee_haircut_pct=round(dist_fee_pct * 100.0, 2),
            spike_clipped_eur=round(spike_clipped_eur, 2),
            l3m_annualized_eur=round(l3m_annualized_eur, 2) if l3m_annualized_eur is not None else None,
            functional_noise_haircut_eur=round(func_noise_haircut_eur, 2),
            subthreshold_1000_streams_haircut_eur=round(subthreshold_haircut_eur, 2),
            ownership_adjusted_baseline_eur=round(ownership_adjusted_eur, 2),
            effective_cf0_eur=round(effective_cf0_eur, 2),
        )

        return CatalogValuationOutput(
            valuation_stage=valuation_stage,
            pipeline_status=pipeline_status,
            genre_family=genre_family,
            baseline=baseline_report,
            cohorts=cohorts_report,
            discount_rate=discount_breakdown,
            npv_5y_p10_eur=round(npv_5y_p10, 2),
            npv_5y_p50_eur=round(npv_5y_p50, 2),
            npv_5y_p90_eur=round(npv_5y_p90, 2),
            npv_10y_p10_eur=round(npv_10y_p10, 2),
            npv_10y_p50_eur=round(npv_10y_p50, 2),
            npv_10y_p90_eur=round(npv_10y_p90, 2),
            price_low_eur=price_low_eur,
            price_median_eur=price_median_eur,
            price_high_eur=price_high_eur,
            price_low_cents=int(round(price_low_eur * 100)),
            price_median_cents=int(round(price_median_eur * 100)),
            price_high_cents=int(round(price_high_eur * 100)),
            implied_ltm_multiple_low=mult_low,
            implied_ltm_multiple_median=mult_med,
            implied_ltm_multiple_high=mult_high,
            expected_payback_months=round(payback_months, 1),
            integrity_score=round(integrity_score, 1),
            valuation_confidence=valuation_confidence,
            track_hhi=round(track_hhi, 4),
            implied_blended_rpm_usd=round(implied_rpm_usd, 6) if implied_rpm_usd is not None else None,
            risk_flags=risk_flags,
            dtw_analysis=dtw_result,
            deal_structure=deal_structure,
            yearly_projected_cashflows_p50_eur=[round(v, 2) for v in yearly_cfs_p50],
            missing_data_fields=missing_fields,
            qlero_bd_lead_score=qlero_score,
            qlero_bd_reasons=qlero_reasons,
        )

    def _run_monte_carlo_dcf(
        self,
        cf0_annual_eur: float,
        track_weights: List[float],
        track_ages_months: List[float],
        track_y1_decays: List[float],
        track_steady_decays: List[float],
        annual_discount_rate: float,
        statements_verified: bool,
        n_simulations: int = 1000,
    ) -> Tuple[float, float, float, float, float, float, List[float], float]:
        if cf0_annual_eur <= 0:
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, [0.0] * 10, 0.0

        rng = np.random.default_rng(self.random_seed)
        n_months = 120
        months_idx = np.arange(1, n_months + 1, dtype=float)

        # Monthly discount factors (1 + r)^(-m/12)
        monthly_discount_factors = (1.0 + annual_discount_rate) ** (-months_idx / 12.0)

        # Build deterministic baseline monthly cash flow across all track cohorts
        # As a track ages forward by m months, its instantaneous annual decay rate transitions
        # smoothly from its initial decay rate toward its steady-state evergreen decay rate
        # following a Weibull-like hazard relaxation tau = 24 months.
        base_monthly_cf = np.zeros(n_months, dtype=float)
        initial_monthly_total = cf0_annual_eur / 12.0

        for w, age0, d_y1, d_steady in zip(
            track_weights, track_ages_months, track_y1_decays, track_steady_decays
        ):
            track_cf_m0 = initial_monthly_total * w
            # Decay relaxation factor as track matures over future months m = 1..120
            relaxation = np.exp(-months_idx / 24.0)
            instantaneous_annual_decay = d_steady + (d_y1 - d_steady) * relaxation
            # Convert annual decay rate at month m into monthly survival step
            monthly_retention = np.clip(1.0 - instantaneous_annual_decay, 0.15, 1.05) ** (1.0 / 12.0)
            cumulative_survival = np.cumprod(monthly_retention)
            base_monthly_cf += track_cf_m0 * cumulative_survival

        # Stochastic simulation: log-normal shocks to decay trajectory + macro stream rate drift
        sigma_decay = 0.14 if statements_verified else 0.24
        sigma_monthly_noise = 0.06 if statements_verified else 0.10

        # Shape: (n_simulations, n_months)
        # Persistent trajectory shock per simulation path (captures whether catalog decays faster/slower than prior)
        drift_shocks = rng.normal(loc=0.0, scale=sigma_decay, size=(n_simulations, 1))
        time_years = (months_idx / 12.0).reshape(1, n_months)
        trajectory_multiplier = np.exp(-drift_shocks * np.sqrt(time_years))

        # Idiosyncratic monthly noise (mean-corrected lognormal so E[noise] = 1)
        idiosyncratic = rng.normal(
            loc=-0.5 * (sigma_monthly_noise ** 2),
            scale=sigma_monthly_noise,
            size=(n_simulations, n_months),
        )
        sim_cfs = base_monthly_cf.reshape(1, n_months) * trajectory_multiplier * np.exp(idiosyncratic)

        discounted_cfs = sim_cfs * monthly_discount_factors.reshape(1, n_months)

        npv_5y_samples = np.sum(discounted_cfs[:, :60], axis=1)
        npv_10y_samples = np.sum(discounted_cfs[:, :120], axis=1)

        npv_5y_p10, npv_5y_p50, npv_5y_p90 = np.percentile(npv_5y_samples, [10, 50, 90])
        npv_10y_p10, npv_10y_p50, npv_10y_p90 = np.percentile(npv_10y_samples, [10, 50, 90])

        # Median undiscounted yearly cash flows (Years 1..10) for reporting & payback calculation
        median_monthly_undiscounted = np.median(sim_cfs, axis=0)
        yearly_cfs_p50 = [
            float(np.sum(median_monthly_undiscounted[y * 12 : (y + 1) * 12])) for y in range(10)
        ]

        # Expected payback period (in months) against recommended offer price
        target_offer = 0.60 * float(npv_5y_p50) + 0.40 * float(npv_10y_p50)
        cum_undiscounted = np.cumsum(median_monthly_undiscounted)
        reached = np.where(cum_undiscounted >= target_offer)[0]
        if len(reached) > 0:
            payback_months = float(reached[0] + 1)
        else:
            payback_months = 120.0

        return (
            float(npv_5y_p10),
            float(npv_5y_p50),
            float(npv_5y_p90),
            float(npv_10y_p10),
            float(npv_10y_p50),
            float(npv_10y_p90),
            yearly_cfs_p50,
            payback_months,
        )

    def _build_deal_structure(
        self,
        offer_median_eur: float,
        integrity_score: float,
        dollar_weighted_age_months: float,
        track_hhi: float,
        statements_verified: bool,
    ) -> DealStructureRecommendation:
        if offer_median_eur <= 0:
            return DealStructureRecommendation(
                upfront_pct=0.0,
                holdback_pct=0.0,
                upfront_eur=0.0,
                holdback_eur=0.0,
                rationale="No offer recommended until minimum royalty threshold and verification are met.",
            )

        holdback_pct = 10.0  # Baseline 10% holdback
        reasons: List[str] = []

        if dollar_weighted_age_months < 20.0:
            holdback_pct += 10.0
            reasons.append(f"young catalog dollar-age ({dollar_weighted_age_months:.1f}m)")
        if track_hhi > 0.40:
            holdback_pct += 5.0
            reasons.append(f"high track concentration (HHI {track_hhi:.2f})")
        if integrity_score < 80.0:
            holdback_pct += 10.0
            reasons.append(f"forensics risk flags (Integrity Score {integrity_score:.0f}/100)")
        if not statements_verified:
            holdback_pct = max(holdback_pct, 25.0)
            reasons.append("subject to raw CSV statement verification")

        holdback_pct = min(35.0, max(10.0, holdback_pct))
        upfront_pct = 100.0 - holdback_pct

        upfront_eur = round(offer_median_eur * (upfront_pct / 100.0), 2)
        holdback_eur = round(offer_median_eur - upfront_eur, 2)

        rationale_detail = ", ".join(reasons) if reasons else "mature diversified catalog profile"
        rationale = (
            f"{upfront_pct:.0f}% (€{upfront_eur:,.2f}) payable at closing; "
            f"{holdback_pct:.0f}% (€{holdback_eur:,.2f}) held in 12-month performance escrow "
            f"due to {rationale_detail}."
        )

        return DealStructureRecommendation(
            upfront_pct=upfront_pct,
            holdback_pct=holdback_pct,
            upfront_eur=upfront_eur,
            holdback_eur=holdback_eur,
            holdback_months=12,
            l3m_retention_covenant_pct=80.0,
            rationale=rationale,
        )

    def _score_bd_and_royalty_accounting_fit(
        self, inp: CatalogValuationInput
    ) -> Tuple[int, List[str]]:
        """
        Scores inbound applicants for Business Development / Royalty Accounting cross-sell
        based solely on their SPACE Typeform answers (no external API needed).
        """
        score = 20
        reasons: List[str] = []

        if inp.representation_type == "represented_catalog":
            score += 35
            reasons.append("Represents external catalog(s) (manager/label/agency — multi-catalog BD potential)")
        elif inp.representation_type == "partnership":
            score += 45
            reasons.append("Inbound partnership inquiry")

        if inp.royalty_basis == RoyaltyBasis.UNSURE or inp.declared_ltm_amount <= 0:
            score += 20
            reasons.append("Lacks clear net vs. gross royalty visibility across distributor statements")

        if inp.ownership_share_pct < 100.0 or (
            inp.notes and any(w in inp.notes.lower() for w in ["split", "co-owner", "collab", "producer", "share", "%"])
        ):
            score += 25
            reasons.append("Has co-owners/royalty splits requiring automated split accounting")

        if inp.rights_scope in {RightsScope.BOTH, RightsScope.PUBLISHING, RightsScope.UNKNOWN}:
            score += 15
            reasons.append("Complex multi-right scope (Masters + Publishing / rights identification needed)")

        return min(100, score), reasons
