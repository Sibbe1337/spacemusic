from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from libs.catalog.models import CatalogPassport, RoyaltyPeriod, RoyaltySource, ValuationRequest
from services.valuation.worker import celery_app, run_valuation


def _inputs() -> tuple[CatalogPassport, ValuationRequest]:
    passport = CatalogPassport(
        owner_id=uuid4(),
        artist_label="Synthetic Soundscape",
        territories=["EU", "US"],
        royalty_sources=[RoyaltySource.DISTRIBUTOR],
        revenue_history=[
            RoyaltyPeriod(
                period_start=date(2025, month, 1),
                period_end=date(2025, month, 28),
                gross_cents=10_000,
                source=RoyaltySource.DISTRIBUTOR,
                verified=True,
            )
            for month in range(1, 13)
        ],
        metadata_completeness=1.0,
        anti_fraud_status="CLEAR",
        rights_ownership_share=1.0,
    )
    request = ValuationRequest(
        benchmark_version="synthetic-v1",
        benchmark_multiple_low=2.0,
        benchmark_multiple_median=3.0,
        benchmark_multiple_high=4.0,
        valid_for_days=14,
        payment_terms_days=5,
    )
    return passport, request


def test_worker_uses_supplied_inputs_and_returns_three_offer_scenarios(monkeypatch):
    monkeypatch.delenv("VALUATION_PUBLISH_EVENTS", raising=False)
    passport, request = _inputs()

    result = run_valuation(
        passport.model_dump(mode="json"),
        request.model_dump(mode="json"),
    )

    assert result["status"] == "success"
    assert result["event_published"] is False
    assert result["valuation"]["benchmark_version"] == "synthetic-v1"
    assert {offer["sale_percentage"] for offer in result["offers"]} == {50, 75, 100}


def test_worker_rejects_unordered_benchmark_inputs():
    passport, request = _inputs()
    invalid_request = request.model_copy(update={"benchmark_multiple_high": 1.0})

    with pytest.raises(ValueError):
        run_valuation(
            passport.model_dump(mode="json"),
            invalid_request.model_dump(mode="json"),
        )


def test_task_is_registered():
    assert "services.valuation.worker.run_valuation" in celery_app.tasks
