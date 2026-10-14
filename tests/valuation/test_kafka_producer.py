from __future__ import annotations

from unittest.mock import MagicMock, patch

from libs.catalog.models import CatalogPassport, RoyaltyPeriod, RoyaltySource, ValuationRequest
from services.valuation import worker


def test_event_publishing_is_opt_in(monkeypatch):
    monkeypatch.delenv("VALUATION_PUBLISH_EVENTS", raising=False)
    worker._valuation_producer = None
    assert worker.get_valuation_producer() is None


def test_valuation_event_uses_application_id_and_versioned_values(monkeypatch):
    monkeypatch.setenv("VALUATION_PUBLISH_EVENTS", "true")
    passport = CatalogPassport(
        owner_id="00000000-0000-0000-0000-000000000001",
        artist_label="Catalog",
        revenue_history=[
            RoyaltyPeriod(
                period_start="2025-01-01",
                period_end="2025-01-28",
                gross_cents=1000,
                source=RoyaltySource.DISTRIBUTOR,
                verified=True,
            )
        ],
    )
    request = ValuationRequest(
        benchmark_version="bench-v1",
        benchmark_multiple_low=1,
        benchmark_multiple_median=2,
        benchmark_multiple_high=3,
    )
    producer = MagicMock()
    worker._valuation_producer = producer
    with patch.object(worker, "get_valuation_producer", return_value=producer):
        result = worker.run_valuation(
            passport.model_dump(mode="json"),
            request.model_dump(mode="json"),
        )

    assert result["status"] == "success"
    payload = producer.produce.call_args.kwargs["value"]
    assert payload["application_id"] == str(passport.id)
    assert payload["valuation_version"] == "valuation-v0.1"
    assert payload["benchmark_version"] == "bench-v1"
    worker._valuation_producer = None
