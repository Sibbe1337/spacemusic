from datetime import date
from uuid import uuid4

import pytest

from libs.catalog.models import (
    CatalogPassport,
    RoyaltyPeriod,
    RoyaltySource,
    TrackRecord,
    ValuationRequest,
)
from libs.catalog.offers import build_offer_scenarios
from libs.catalog.valuation import calculate_valuation


def make_passport(*, months: int = 12, declining: bool = False, fraud_status: str = "CLEAR") -> CatalogPassport:
    history = []
    for month in range(months):
        amount = 10_000 - (month * 500 if declining else 0)
        history.append(
            RoyaltyPeriod(
                period_start=date(2025, 1, 1),
                period_end=date(2025, 1, 28),
                gross_cents=max(amount, 1),
                source=RoyaltySource.DISTRIBUTOR,
                verified=True,
            )
        )
    return CatalogPassport(
        owner_id=uuid4(),
        artist_label="Synthetic Soundscape Catalog",
        tracks=[TrackRecord(title="Synthetic track", isrc="SE-TEST-25-00001", iswc="T-900.000.001-1")],
        territories=["EU", "US"],
        royalty_sources=[RoyaltySource.DISTRIBUTOR],
        revenue_history=history,
        metadata_completeness=1.0,
        anti_fraud_status=fraud_status,
        top_track_revenue_share=0.35,
    )


def make_request() -> ValuationRequest:
    return ValuationRequest(
        benchmark_version="synthetic-benchmark-v1",
        benchmark_multiple_low=2.0,
        benchmark_multiple_median=3.0,
        benchmark_multiple_high=4.0,
        valid_for_days=14,
        payment_terms_days=5,
    )


def test_valuation_is_reproducible_and_uses_supplied_benchmark():
    passport = make_passport()
    request = make_request()

    first = calculate_valuation(passport, request)
    second = calculate_valuation(passport, request)

    assert first.model_copy(update={"calculated_at": second.calculated_at}) == second
    assert first.benchmark_version == "synthetic-benchmark-v1"
    assert first.median_cents == 360_000
    assert first.risk_flags == []
    assert first.manual_review_required is False


def test_declining_revenue_requires_manual_review():
    result = calculate_valuation(make_passport(declining=True), make_request())

    assert "DECLINING_REVENUE" in result.risk_flags
    assert result.manual_review_required is True
    assert result.high_cents > result.median_cents > result.low_cents


def test_short_or_suspicious_history_is_flagged():
    result = calculate_valuation(make_passport(months=3, fraud_status="REVIEW"), make_request())

    assert "HISTORY_UNDER_12_MONTHS" in result.risk_flags
    assert "FRAUD_REVIEW_REQUIRED" in result.risk_flags
    assert result.confidence_score < 0.7


def test_offer_engine_always_returns_explicit_sale_choices():
    application_id = uuid4()
    passport = make_passport()
    request = make_request()
    valuation = calculate_valuation(passport, request)

    offers = build_offer_scenarios(application_id, passport, valuation, request, today=date(2026, 1, 1))

    assert [offer.sale_percentage for offer in offers] == [50, 75, 100]
    assert offers[0].cash_median_cents * 2 == offers[2].cash_median_cents
    assert offers[2].rights_retained["masters"] == 0
    assert offers[0].rights_retained["masters"] == 0.5
    assert all(offer.valid_until == date(2026, 1, 15) for offer in offers)


def test_unverified_periods_are_not_used_as_revenue_base():
    passport = make_passport()
    passport.revenue_history[0] = passport.revenue_history[0].model_copy(
        update={"gross_cents": 1_000_000, "verified": False}
    )

    result = calculate_valuation(passport, make_request())

    assert result.median_cents < 360_000
    assert result.median_cents > 300_000
    assert "DOCUMENTS_NOT_FULLY_VERIFIED" in result.risk_flags


def test_mixed_currency_history_is_rejected_without_fx_assumptions():
    payload = make_passport().model_dump(mode="python")
    payload["revenue_history"][1]["currency_code"] = "USD"

    with pytest.raises(ValueError, match="one currency"):
        CatalogPassport.model_validate(payload)
