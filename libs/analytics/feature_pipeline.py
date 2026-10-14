"""Deterministic feature extraction for royalty evidence.

This module intentionally contains no streaming-platform client. Features are
derived from the evidence already supplied to the Catalog Passport.
"""

from __future__ import annotations

from statistics import pstdev
from typing import Any, Dict, Iterable, Mapping


def _amounts(periods: Iterable[Mapping[str, Any]]) -> list[float]:
    values = []
    for period in periods:
        gross = float(period.get("gross_cents", 0))
        adjustments = float(period.get("adjustments_cents", 0))
        values.append(max(0.0, gross + adjustments))
    return values


def process_data_for_features(raw_data: Mapping[str, Any]) -> Dict[str, float]:
    """Return reviewable royalty features from a passport-shaped mapping."""
    periods = raw_data.get("revenue_history", []) or []
    amounts = _amounts(periods)
    average = sum(amounts) / len(amounts) if amounts else 0.0
    volatility = pstdev(amounts) / average if len(amounts) > 1 and average else 0.0
    recent = sum(amounts[-3:]) / min(3, len(amounts)) if amounts else 0.0
    early = sum(amounts[:3]) / min(3, len(amounts)) if amounts else 0.0
    trend = recent / early - 1 if early else 0.0
    verified_count = sum(1 for period in periods if period.get("verified", False))
    return {
        "months_of_history": float(len(amounts)),
        "average_monthly_net_cents": round(average, 4),
        "monthly_volatility": round(volatility, 6),
        "recent_trend": round(trend, 6),
        "verified_period_share": round(verified_count / len(amounts), 6) if amounts else 0.0,
        "metadata_completeness": float(raw_data.get("metadata_completeness", 0.0)),
        "rights_ownership_share": float(raw_data.get("rights_ownership_share", 0.0)),
    }
