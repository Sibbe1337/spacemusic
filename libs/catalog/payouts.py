from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PayoutResult(BaseModel):
    payout_intent_id: UUID
    status: str
    provider_reference: str
    amount_cents: int = Field(ge=0)
    currency_code: str
    idempotency_key: str
    created_at: datetime


class PayoutAdapter(Protocol):
    def create_payout(
        self,
        *,
        payout_intent_id: UUID,
        amount_cents: int,
        currency_code: str,
        recipient_token: str,
        idempotency_key: str,
    ) -> PayoutResult: ...


class TestPayoutAdapter:
    """Deterministic adapter. It never contacts Stripe, Wise, or a bank."""

    __test__ = False

    def __init__(self) -> None:
        self._results: dict[str, PayoutResult] = {}

    def create_payout(
        self,
        *,
        payout_intent_id: UUID,
        amount_cents: int,
        currency_code: str,
        recipient_token: str,
        idempotency_key: str,
    ) -> PayoutResult:
        existing = self._results.get(idempotency_key)
        if existing:
            return existing
        token_fingerprint = sha256(recipient_token.encode("utf-8")).hexdigest()[:12]
        provider_reference = f"test_payout_{token_fingerprint}_{sha256(idempotency_key.encode()).hexdigest()[:12]}"
        result = PayoutResult(
            payout_intent_id=payout_intent_id,
            status="SUCCEEDED",
            provider_reference=provider_reference,
            amount_cents=amount_cents,
            currency_code=currency_code,
            idempotency_key=idempotency_key,
            created_at=datetime.now(timezone.utc),
        )
        self._results[idempotency_key] = result
        return result


class LedgerEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    payout_intent_id: UUID
    application_id: UUID
    debit_account: str
    credit_account: str
    amount_cents: int = Field(ge=0)
    currency_code: str
    reference_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
