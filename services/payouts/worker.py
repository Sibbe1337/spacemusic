"""Fail-closed payout task with a deterministic local adapter.

The seller API owns the durable payout intent and ledger transaction. This Celery
task remains available for asynchronous processing, but it never calls a real
provider in local/test mode and has no provider fallback that could double-pay.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from hashlib import sha256
from typing import Dict, Optional
from uuid import NAMESPACE_URL, UUID, uuid5

from libs.catalog.payouts import LedgerEntry, PayoutResult, TestPayoutAdapter
from libs.py_common.celery_config import create_celery_app

from .metrics import (
    APP_ERRORS_TOTAL,
    CELERY_TASK_DURATION_SECONDS,
    CELERY_TASKS_PROCESSED_TOTAL,
    LEDGER_ENTRIES_CREATED_TOTAL,
)

celery_app = create_celery_app("payouts_worker")
_test_adapter = TestPayoutAdapter()
_ledger_by_idempotency: Dict[str, LedgerEntry] = {}
_request_fingerprints: Dict[str, tuple[str, int, str, str]] = {}


def _payout_mode() -> str:
    return os.getenv("SPACE_PAYOUT_MODE", "test").lower()


def _intent_id(idempotency_key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"spacemusic:payout:{idempotency_key}")


def _ledger_for(result: PayoutResult, application_id: UUID) -> LedgerEntry:
    return LedgerEntry(
        payout_intent_id=result.payout_intent_id,
        application_id=application_id,
        debit_account="seller_payouts",
        credit_account="cash_clearing",
        amount_cents=result.amount_cents,
        currency_code=result.currency_code,
        reference_id=result.provider_reference,
    )


def _request_fingerprint(
    application_id: UUID,
    amount_cents: int,
    currency_code: str,
    recipient_token: str,
) -> tuple[str, int, str, str]:
    """Bind an idempotency key to request identity without retaining the token."""
    return (
        str(application_id),
        amount_cents,
        currency_code.upper(),
        sha256(recipient_token.encode("utf-8")).hexdigest(),
    )


@celery_app.task(name="services.payouts.worker.execute_payout")
def execute_payout(
    application_id_str: str,
    amount_cents: Optional[int] = None,
    currency_code: str = "EUR",
    recipient_token: str = "test-recipient-token",
    idempotency_key: Optional[str] = None,
) -> Dict[str, object]:
    """Execute one idempotent payout request in the configured mode.

    Live provider wiring is intentionally not bundled into this task. A live
    deployment must supply a reviewed adapter behind the same protocol rather
    than silently changing the local test behavior.
    """
    started = datetime.now(timezone.utc)
    status = "failure"
    try:
        application_id = UUID(application_id_str)
        if amount_cents is None or amount_cents <= 0:
            return {"status": "error", "message": "A positive amount_cents is required"}
        if not idempotency_key:
            return {"status": "error", "message": "idempotency_key is required"}
        if not recipient_token:
            return {"status": "error", "message": "recipient_token is required"}
        if _payout_mode() != "test":
            APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="live_adapter_unavailable").inc()
            return {"status": "error", "message": "Live payout adapter is not configured"}

        normalized_currency = currency_code.upper()
        fingerprint = _request_fingerprint(
            application_id, amount_cents, normalized_currency, recipient_token
        )
        existing_fingerprint = _request_fingerprints.get(idempotency_key)
        if existing_fingerprint and existing_fingerprint != fingerprint:
            APP_ERRORS_TOTAL.labels(
                component="execute_payout", error_type="idempotency_key_conflict"
            ).inc()
            return {"status": "error", "message": "idempotency_key_conflict"}

        existing_ledger = _ledger_by_idempotency.get(idempotency_key)
        if existing_ledger:
            status = "success"
            return {
                "status": "success",
                "payout_intent_id": str(existing_ledger.payout_intent_id),
                "provider_reference": existing_ledger.reference_id,
                "ledger_entry_id": str(existing_ledger.id),
                "idempotent_replay": True,
            }

        result = _test_adapter.create_payout(
            payout_intent_id=_intent_id(idempotency_key),
            amount_cents=amount_cents,
            currency_code=normalized_currency,
            recipient_token=recipient_token,
            idempotency_key=idempotency_key,
        )
        ledger_entry = _ledger_for(result, application_id)
        _ledger_by_idempotency[idempotency_key] = ledger_entry
        _request_fingerprints[idempotency_key] = fingerprint
        LEDGER_ENTRIES_CREATED_TOTAL.labels(
            transaction_type="payout",
            payout_method="test",
        ).inc()
        status = "success"
        return {
            "status": "success",
            "payout": result.model_dump(mode="json"),
            "ledger_entry": ledger_entry.model_dump(mode="json"),
            "idempotent_replay": False,
        }
    except (ValueError, TypeError) as exc:
        APP_ERRORS_TOTAL.labels(component="execute_payout", error_type=type(exc).__name__).inc()
        return {"status": "error", "message": str(exc)}
    finally:
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        CELERY_TASK_DURATION_SECONDS.labels(task_name="services.payouts.worker.execute_payout").observe(elapsed)
        CELERY_TASKS_PROCESSED_TOTAL.labels(
            task_name="services.payouts.worker.execute_payout",
            status=status,
        ).inc()


def reset_test_state() -> None:
    """Clear deterministic state between isolated worker tests."""
    _test_adapter._results.clear()
    _ledger_by_idempotency.clear()
    _request_fingerprints.clear()
