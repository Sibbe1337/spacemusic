"""
SPACE Dynamic Time Warping (DTW) Trajectory & Lifecycle Archetype Engine
(`services/valuation/dtw_matcher.py`)

Provides non-linear time-elastic shape matching for music catalog cash-flow series:
1. `sakoe_chiba_dtw_distance`: Band-constrained DTW distance normalized by path length,
   allowing phase-shifted or stretched song lifecycles (e.g. Month-2 vs Month-6 peak)
   to be matched accurately without distorting macro time scales.
2. `prefix_subsequence_dtw`: Matches an observed N-month track/catalog history against
   the prefix of longer (36-60 month) historical reference curves and projects the
   empirical continuation ($k$-NN Gaussian kernel weighted).
3. Canonical Lifecycle Archetypes:
   - `VIRAL_SPIKE_CRASH`: TikTok/phonk/meme rapid spike followed by 75-90% collapse
   - `FRONTLINE_BURN_IN`: Classic release peak in months 1-3 followed by L-shaped stabilization
   - `ALGORITHMIC_PROLONGED_PLATEAU`: Slow 4-8 month algorithmic discovery climb + broad plateau
   - `EVERGREEN_STEADY`: Flat/low-volatility mature catalog trajectory
   - `ARTIFICIAL_STEP_PLATEAU`: Rectangular step-function (flat -> sudden flat plateau -> cliff)
     characteristic of paid bot/playlist campaigns.
4. `compute_cross_track_dtw_synchrony`: Detects whether multiple tracks released at different
   dates exhibit suspiciously synchronized spikes in the same calendar window.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field


class LifecycleArchetype(str, Enum):
    VIRAL_SPIKE_CRASH = "VIRAL_SPIKE_CRASH"
    FRONTLINE_BURN_IN = "FRONTLINE_BURN_IN"
    ALGORITHMIC_PROLONGED_PLATEAU = "ALGORITHMIC_PROLONGED_PLATEAU"
    EVERGREEN_STEADY = "EVERGREEN_STEADY"
    ARTIFICIAL_STEP_PLATEAU = "ARTIFICIAL_STEP_PLATEAU"


class DTWMatchResult(BaseModel):
    matched_archetype: LifecycleArchetype
    dtw_distance: float
    similarity_score: float  # 0.0 to 1.0
    archetype_distances: Dict[str, float] = Field(default_factory=dict)
    is_artificial_step_plateau: bool = False
    dtw_implied_year1_retention: float = 0.80
    dtw_implied_annual_decay_rate: float = 0.20
    dtw_blend_weight: float = 0.0
    cross_track_synchrony_score: Optional[float] = None


def normalize_shape_curve(series: List[float] | np.ndarray) -> np.ndarray:
    """
    Peak-normalizes a non-negative time series into [0, 1] so DTW compares pure
    lifecycle geometry independent of absolute Euro volume.
    """
    arr = np.asarray(series, dtype=float)
    arr = np.maximum(0.0, arr)
    peak = float(np.max(arr)) if arr.size > 0 else 0.0
    if peak <= 1e-9:
        return np.zeros_like(arr)
    return arr / peak


def sakoe_chiba_dtw_distance(
    s1: List[float] | np.ndarray,
    s2: List[float] | np.ndarray,
    window: int = 3,
    normalize_inputs: bool = True,
) -> float:
    """
    Computes length-normalized Root-Mean-Square Dynamic Time Warping (DTW) distance
    between series `s1` and `s2` with a Sakoe-Chiba warping band of `window` months.
    """
    x = normalize_shape_curve(s1) if normalize_inputs else np.asarray(s1, dtype=float)
    y = normalize_shape_curve(s2) if normalize_inputs else np.asarray(s2, dtype=float)

    n, m = len(x), len(y)
    if n == 0 or m == 0:
        return 1.0

    # Ensure window is at least large enough to connect (0,0) to (n-1, m-1)
    w = max(window, abs(n - m))
    cost = np.full((n + 1, m + 1), np.inf, dtype=float)
    cost[0, 0] = 0.0

    for i in range(1, n + 1):
        j_start = max(1, i - w)
        j_end = min(m, i + w)
        xi = x[i - 1]
        for j in range(j_start, j_end + 1):
            dist_sq = (xi - y[j - 1]) ** 2
            prev_min = min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])
            cost[i, j] = dist_sq + prev_min

    total_cost = cost[n, m]
    if not np.isfinite(total_cost):
        return 1.0
    return float(math.sqrt(total_cost / float(max(n, m))))


def _build_canonical_archetype_library() -> Dict[LifecycleArchetype, List[Tuple[np.ndarray, float]]]:
    """
    Generates canonical 36-month normalized reference trajectories `(curve_36m, post_obs_annual_decay)`
    for each of the 5 lifecycle archetypes, including phase-shifted variants.
    """
    t = np.arange(36, dtype=float)

    # 1. VIRAL_SPIKE_CRASH: sharp spike at month 1-3, then 80%+ collapse
    viral_a = np.exp(-((t - 1.0) / 1.8) ** 2) * 0.92 + 0.08 * np.exp(-t / 18.0)
    viral_b = np.where(t < 3, (t + 1) / 4.0, np.exp(-(t - 3.0) / 2.2) * 0.90 + 0.10 * np.exp(-(t - 3.0) / 20.0))

    # 2. FRONTLINE_BURN_IN: release peak in month 0-2, Weibull burn-in stabilizing around 30-40% of peak
    burn_a = 0.65 * np.exp(-((t / 6.5) ** 0.85)) + 0.35 * np.exp(-t / 60.0)
    t_shifted = np.maximum(0.0, t - 1.0)
    burn_b = np.where(t < 2, 0.7 + 0.3 * t, 0.60 * np.exp(-((t_shifted / 7.5) ** 0.85)) + 0.40 * np.exp(-t / 65.0))

    # 3. ALGORITHMIC_PROLONGED_PLATEAU: gradual build over months 1-6, broad plateau, gentle 10% annual decay
    algo_a = np.where(t <= 5, 0.35 + 0.65 * (t / 5.0), np.exp(-(t - 5.0) / 85.0))
    algo_b = np.where(t <= 7, 0.25 + 0.75 * np.sin((t / 7.0) * (math.pi / 2.0)), np.exp(-(t - 7.0) / 75.0))

    # 4. EVERGREEN_STEADY: mature flatline oscillating gently between 0.88 and 1.00
    ever_a = 0.95 * np.exp(-t / 360.0) + 0.04 * np.cos(t * 0.5)
    ever_b = 0.97 * np.exp(-t / 420.0) - 0.03 * np.sin(t * 0.4)

    # 5. ARTIFICIAL_STEP_PLATEAU: low baseline -> sudden vertical step to flat ceiling -> sudden drop
    step_a = np.ones(36, dtype=float) * 0.08
    step_a[3:9] = 1.00  # 6-month rectangular bot/playlist block
    step_b = np.ones(36, dtype=float) * 0.10
    step_b[5:11] = 1.00  # Late rectangular block right before sale!
    step_c = np.ones(36, dtype=float) * 0.07
    step_c[2:7] = 0.98

    return {
        LifecycleArchetype.VIRAL_SPIKE_CRASH: [
            (normalize_shape_curve(viral_a), 0.58),
            (normalize_shape_curve(viral_b), 0.54),
        ],
        LifecycleArchetype.FRONTLINE_BURN_IN: [
            (normalize_shape_curve(burn_a), 0.24),
            (normalize_shape_curve(burn_b), 0.22),
        ],
        LifecycleArchetype.ALGORITHMIC_PROLONGED_PLATEAU: [
            (normalize_shape_curve(algo_a), 0.09),
            (normalize_shape_curve(algo_b), 0.10),
        ],
        LifecycleArchetype.EVERGREEN_STEADY: [
            (normalize_shape_curve(ever_a), 0.025),
            (normalize_shape_curve(ever_b), 0.020),
        ],
        LifecycleArchetype.ARTIFICIAL_STEP_PLATEAU: [
            (normalize_shape_curve(step_a), 0.65),
            (normalize_shape_curve(step_b), 0.68),
            (normalize_shape_curve(step_c), 0.65),
        ],
    }


CANONICAL_LIBRARY = _build_canonical_archetype_library()


def _detect_rectangular_step_geometry(norm_series: np.ndarray) -> bool:
    """
    Supplements DTW archetype distance with a direct geometric check for
    unnatural rectangular step functions (e.g., low floor -> 3+ months of near-constant
    high plateau -> optional cliff), typical of paid fixed-volume playlisting.
    """
    if len(norm_series) < 6:
        return False

    high_mask = norm_series >= 0.78
    low_mask = norm_series <= 0.25
    n_high = int(np.sum(high_mask))
    n_low = int(np.sum(low_mask))
    n_mid = len(norm_series) - n_high - n_low

    # If series spends almost all its time at either floor (<=0.25) or ceiling (>=0.78)
    # with almost no organic transition months, and the ceiling has abnormally low variance:
    if n_high >= 3 and n_low >= 2 and n_mid <= 1:
        high_vals = norm_series[high_mask]
        if float(np.std(high_vals)) < 0.045:
            return True
    return False


def evaluate_dtw_lifecycle(
    monthly_series: List[float],
    window: int = 3,
    sigma: float = 0.35,
    max_blend_weight: float = 0.55,
    step_threshold: float = 0.18,
) -> Optional[DTWMatchResult]:
    """
    Matches an observed monthly royalty/stream series (minimum 6 months) against
    SPACE's canonical DTW lifecycle templates using prefix DTW matching.
    Returns the best-matching `LifecycleArchetype`, Gaussian-kernel-weighted annual
    decay rate, and artificial step-plateau fraud flag.
    """
    clean = [max(0.0, float(v)) for v in monthly_series if v is not None]
    if len(clean) < 6 or max(clean) <= 0:
        return None

    obs = normalize_shape_curve(clean)
    n_obs = min(len(obs), 24)
    obs_window = obs[-n_obs:]

    archetype_best_dist: Dict[str, float] = {}
    kernel_weights: List[float] = []
    kernel_decays: List[float] = []

    best_arch = LifecycleArchetype.FRONTLINE_BURN_IN
    best_dist = float("inf")

    for arch, variants in CANONICAL_LIBRARY.items():
        min_d_for_arch = float("inf")
        for ref_curve, ref_decay in variants:
            # Prefix subsequence match: compare observed N months against prefix of reference curve
            ref_prefix = normalize_shape_curve(ref_curve[:n_obs])
            d = sakoe_chiba_dtw_distance(obs_window, ref_prefix, window=window, normalize_inputs=False)
            if d < min_d_for_arch:
                min_d_for_arch = d

            # Gaussian kernel weight for k-NN trajectory continuation
            w = math.exp(-(d * d) / (2.0 * sigma * sigma))
            kernel_weights.append(w)
            kernel_decays.append(ref_decay)

        archetype_best_dist[arch.value] = round(min_d_for_arch, 4)
        if min_d_for_arch < best_dist:
            best_dist = min_d_for_arch
            best_arch = arch

    # Check rectangular step-plateau geometry
    rect_detected = _detect_rectangular_step_geometry(obs_window)
    is_step_plateau = (
        best_arch == LifecycleArchetype.ARTIFICIAL_STEP_PLATEAU and best_dist <= step_threshold
    ) or rect_detected
    if rect_detected:
        best_arch = LifecycleArchetype.ARTIFICIAL_STEP_PLATEAU
        best_dist = min(best_dist, 0.11)
        archetype_best_dist[LifecycleArchetype.ARTIFICIAL_STEP_PLATEAU.value] = round(best_dist, 4)

    w_sum = sum(kernel_weights) or 1e-9
    dtw_annual_decay = sum(w * dec for w, dec in zip(kernel_weights, kernel_decays)) / w_sum
    if is_step_plateau:
        dtw_annual_decay = max(dtw_annual_decay, 0.55)

    similarity = float(math.exp(-best_dist / 0.30))
    # Blend weight increases with number of observed months (6..24) and match similarity
    obs_factor = min(1.0, len(clean) / 18.0)
    blend_weight = round(min(max_blend_weight, obs_factor * similarity * max_blend_weight), 4)

    return DTWMatchResult(
        matched_archetype=best_arch,
        dtw_distance=round(best_dist, 4),
        similarity_score=round(similarity, 4),
        archetype_distances=archetype_best_dist,
        is_artificial_step_plateau=is_step_plateau,
        dtw_implied_year1_retention=round(1.0 - dtw_annual_decay, 4),
        dtw_implied_annual_decay_rate=round(dtw_annual_decay, 4),
        dtw_blend_weight=blend_weight,
    )


def compute_cross_track_dtw_synchrony(
    track_monthly_series: List[List[float]],
    window: int = 1,
) -> Optional[float]:
    """
    Computes average pairwise DTW similarity across multiple tracks in a catalog.
    When >=3 distinct tracks with non-flat volatility exhibit near-identical synchronized
    shapes (e.g. synchrony > 0.88 with high coefficient of variation), it signals
    catalog-wide artificial playlisting.
    """
    valid = [
        normalize_shape_curve(s)
        for s in track_monthly_series
        if len(s) >= 6 and max(s) > 0 and np.std(normalize_shape_curve(s)) > 0.18
    ]
    if len(valid) < 3:
        return None

    min_len = min(len(v) for v in valid)
    if min_len < 6:
        return None

    trimmed = [v[-min_len:] for v in valid[:8]]
    sims: List[float] = []
    for i in range(len(trimmed)):
        for j in range(i + 1, len(trimmed)):
            d = sakoe_chiba_dtw_distance(trimmed[i], trimmed[j], window=window, normalize_inputs=False)
            sims.append(math.exp(-d / 0.25))

    return round(float(np.mean(sims)), 4) if sims else None
