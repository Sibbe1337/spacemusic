from __future__ import annotations

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from .models import CatalogPassport, OfferScenario, ValuationRequest, ValuationResult


def build_offer_scenarios(
    application_id: UUID,
    passport: CatalogPassport,
    valuation: ValuationResult,
    request: ValuationRequest,
    *,
    today: Optional[date] = None,
) -> list[OfferScenario]:
    """Build the three explicit sale choices from one valuation result."""
    effective_today = today or date.today()
    valid_until = effective_today + timedelta(days=request.valid_for_days)
    payment_date = effective_today + timedelta(days=request.payment_terms_days)
    rights = {
        "masters": passport.rights_ownership_share,
        "publishing": passport.rights_ownership_share,
        "neighboring": passport.rights_ownership_share,
    }
    exceptions = list(passport.liens_or_disputes)
    if valuation.manual_review_required:
        exceptions.extend(valuation.risk_flags)

    scenarios: list[OfferScenario] = []
    for percentage in (50, 75, 100):
        share = percentage / 100
        transferred = {key: round(value * share, 4) for key, value in rights.items()}
        retained = {key: round(value * (1 - share), 4) for key, value in rights.items()}
        scenarios.append(
            OfferScenario(
                application_id=application_id,
                version="offer-v0.1",
                sale_percentage=percentage,
                cash_low_cents=round(valuation.low_cents * share),
                cash_median_cents=round(valuation.median_cents * share),
                cash_high_cents=round(valuation.high_cents * share),
                currency_code=valuation.currency_code,
                rights_transferred=transferred,
                rights_retained=retained,
                territories=list(passport.territories),
                royalty_sources=list(passport.royalty_sources),
                payment_date=payment_date,
                valuation_version=valuation.version,
                valuation_range={
                    "low_cents": valuation.low_cents,
                    "median_cents": valuation.median_cents,
                    "high_cents": valuation.high_cents,
                },
                risk_adjustments=[
                    f"Risk adjustment factor: {valuation.risk_adjustment:.4f}",
                    *valuation.risk_flags,
                ],
                exceptions=exceptions,
                valid_until=valid_until,
            )
        )
    return scenarios
