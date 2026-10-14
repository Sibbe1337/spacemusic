from __future__ import annotations

from statistics import pstdev

from .models import CatalogPassport, ValuationRequest, ValuationResult


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def calculate_valuation(
    passport: CatalogPassport,
    request: ValuationRequest,
) -> ValuationResult:
    """Calculate a reproducible underwriting range from verified royalty data.

    The engine does not source audience or royalty data from streaming APIs. All
    commercial assumptions are supplied as a versioned benchmark input.
    """
    periods = passport.revenue_history
    currencies = {period.currency_code for period in periods}
    if currencies and (len(currencies) > 1 or request.currency_code not in currencies):
        raise ValueError("valuation currency must match the single royalty-history currency")
    verified_periods = [period for period in periods if period.verified]
    net_history = [period.net_cents for period in verified_periods]
    average_monthly_cents = sum(net_history) / len(net_history) if net_history else 0
    verified_share = len(verified_periods) / len(periods) if periods else 0
    monthly_volatility = (
        pstdev(net_history) / average_monthly_cents
        if len(net_history) > 1 and average_monthly_cents > 0
        else 0
    )
    quarter_history = [
        sum(net_history[index : index + 3])
        for index in range(0, len(net_history), 3)
        if len(net_history[index : index + 3]) == 3
    ]
    average_quarterly_cents = sum(quarter_history) / len(quarter_history) if quarter_history else 0
    quarterly_volatility = (
        pstdev(quarter_history) / average_quarterly_cents
        if len(quarter_history) > 1 and average_quarterly_cents > 0
        else 0
    )
    volatility = max(monthly_volatility, quarterly_volatility)
    recent = sum(net_history[-3:]) / min(3, len(net_history)) if net_history else 0
    early = sum(net_history[:3]) / min(3, len(net_history)) if net_history else 0
    trend = (recent / early - 1) if early > 0 else 0

    risk_flags: list[str] = []
    explanations: list[str] = [
        f"Annualized base uses {len(periods)} month(s) of supplied royalty history.",
        f"{len(verified_periods)} of {len(periods)} period(s) are marked verified and used as the revenue base.",
        f"Monthly volatility is {monthly_volatility:.1%}; quarterly volatility is {quarterly_volatility:.1%}.",
        f"Benchmark assumptions use version {request.benchmark_version}.",
    ]

    if len(periods) < 12:
        risk_flags.append("HISTORY_UNDER_12_MONTHS")
        explanations.append("Less than 12 months of history reduces confidence.")
    if trend < -0.15:
        risk_flags.append("DECLINING_REVENUE")
        explanations.append(f"Recent average revenue is {abs(trend):.0%} below the early average.")
    if monthly_volatility > 0.5:
        risk_flags.append("HIGH_MONTHLY_VOLATILITY")
        explanations.append("Monthly royalty volatility is above the manual-review threshold.")
    if quarterly_volatility > 0.5:
        risk_flags.append("HIGH_QUARTERLY_VOLATILITY")
        explanations.append("Quarterly royalty volatility is above the manual-review threshold.")
    if passport.top_track_revenue_share is not None and passport.top_track_revenue_share > 0.6:
        risk_flags.append("HIGH_TRACK_CONCENTRATION")
        explanations.append("More than 60% of reported revenue is concentrated in one track.")
    if passport.rights_ownership_share < 1:
        risk_flags.append("RIGHTS_NOT_FULLY_OWNED")
        explanations.append("The range is reduced to the stated ownership share.")
    if passport.metadata_completeness < 0.9:
        risk_flags.append("INCOMPLETE_METADATA")
        explanations.append("Metadata completeness is below the review threshold.")
    if verified_share < 1:
        risk_flags.append("DOCUMENTS_NOT_FULLY_VERIFIED")
        explanations.append("Some royalty periods still require source-document verification.")
    if passport.anti_fraud_status != "CLEAR":
        risk_flags.append("FRAUD_REVIEW_REQUIRED")
        explanations.append("Anti-fraud review is not marked clear.")
    if passport.liens_or_disputes:
        risk_flags.append("LIENS_OR_DISPUTES_DECLARED")
        explanations.append("Declared liens or disputes require legal review before closing.")
    if any(period.adjustments_cents for period in periods):
        risk_flags.append("RETROACTIVE_ADJUSTMENTS_PRESENT")
        explanations.append("Retroactive royalty adjustments are included in the history.")
    if passport.previous_advances_cents:
        risk_flags.append("PREVIOUS_ADVANCE_DECLARED")
        explanations.append("A previous advance is declared and requires reconciliation before closing.")
    if not passport.royalty_sources:
        risk_flags.append("ROYALTY_SOURCE_MISSING")
        explanations.append("No royalty source has been declared.")
    if not passport.territories:
        risk_flags.append("TERRITORIES_MISSING")
        explanations.append("No territories have been declared.")
    if not passport.tracks:
        risk_flags.append("TRACKS_MISSING")
        explanations.append("No track-level rights records have been supplied.")
    elif any(not track.isrc and not track.iswc for track in passport.tracks):
        risk_flags.append("TRACK_IDENTIFIERS_MISSING")
        explanations.append("Some tracks are missing both ISRC and ISWC identifiers.")

    risk_adjustment = 1.0
    risk_adjustment *= 1 - _clamp(volatility * 0.2, 0, 0.2)
    risk_adjustment *= 1 + _clamp(trend * 0.25, -0.15, 0.15)
    risk_adjustment *= 0.9 + (0.1 * verified_share)
    risk_adjustment *= 0.85 + (0.15 * passport.metadata_completeness)
    if passport.anti_fraud_status == "REVIEW":
        risk_adjustment *= 0.75
    elif passport.anti_fraud_status == "PENDING":
        risk_adjustment *= 0.9
    risk_adjustment = _clamp(risk_adjustment, 0.35, 1.0)

    annualized_owned_cents = average_monthly_cents * 12 * passport.rights_ownership_share
    low_cents = round(annualized_owned_cents * request.benchmark_multiple_low * risk_adjustment)
    median_cents = round(annualized_owned_cents * request.benchmark_multiple_median * risk_adjustment)
    high_cents = round(annualized_owned_cents * request.benchmark_multiple_high * risk_adjustment)

    history_score = _clamp(len(verified_periods) / 24)
    confidence = _clamp(
        (history_score * 0.30)
        + (verified_share * 0.20)
        + (passport.metadata_completeness * 0.15)
        + (passport.rights_ownership_share * 0.15)
        + ((1 - _clamp(volatility)) * 0.10)
        + ((1.0 if passport.anti_fraud_status == "CLEAR" else 0.25) * 0.10)
    )
    manual_review_required = bool(risk_flags)

    return ValuationResult(
        version="valuation-v0.1",
        benchmark_version=request.benchmark_version,
        low_cents=max(0, low_cents),
        median_cents=max(0, median_cents),
        high_cents=max(0, high_cents),
        currency_code=request.currency_code,
        confidence_score=round(confidence, 4),
        risk_adjustment=round(risk_adjustment, 4),
        explanations=explanations,
        risk_flags=risk_flags,
        manual_review_required=manual_review_required,
    )
