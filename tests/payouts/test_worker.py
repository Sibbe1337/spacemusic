from __future__ import annotations

from uuid import uuid4

from services.payouts import worker


def test_payout_task_is_registered():
    assert "services.payouts.worker.execute_payout" in worker.celery_app.tasks


def test_test_payout_is_idempotent_and_creates_one_ledger_entry(monkeypatch):
    monkeypatch.setenv("SPACE_PAYOUT_MODE", "test")
    worker.reset_test_state()
    application_id = str(uuid4())

    first = worker.execute_payout(
        application_id,
        amount_cents=12_500,
        currency_code="eur",
        recipient_token="recipient-token",
        idempotency_key="payout-001",
    )
    second = worker.execute_payout(
        application_id,
        amount_cents=12_500,
        currency_code="eur",
        recipient_token="recipient-token",
        idempotency_key="payout-001",
    )

    assert first["status"] == "success"
    assert first["idempotent_replay"] is False
    assert second["status"] == "success"
    assert second["idempotent_replay"] is True
    assert len(worker._ledger_by_idempotency) == 1
    assert first["ledger_entry"]["reference_id"] == second["provider_reference"]


def test_live_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("SPACE_PAYOUT_MODE", "live")
    worker.reset_test_state()

    result = worker.execute_payout(
        str(uuid4()),
        amount_cents=100,
        recipient_token="recipient-token",
        idempotency_key="payout-live-001",
    )

    assert result == {"status": "error", "message": "Live payout adapter is not configured"}
    assert worker._ledger_by_idempotency == {}


def test_idempotency_key_cannot_change_payout_identity(monkeypatch):
    monkeypatch.setenv("SPACE_PAYOUT_MODE", "test")
    worker.reset_test_state()
    application_id = str(uuid4())

    first = worker.execute_payout(
        application_id,
        amount_cents=100,
        currency_code="EUR",
        recipient_token="recipient-token",
        idempotency_key="payout-conflict-001",
    )
    second = worker.execute_payout(
        application_id,
        amount_cents=101,
        currency_code="EUR",
        recipient_token="recipient-token",
        idempotency_key="payout-conflict-001",
    )

    assert first["status"] == "success"
    assert second == {"status": "error", "message": "idempotency_key_conflict"}
    assert len(worker._ledger_by_idempotency) == 1


def test_payout_requires_idempotency_key(monkeypatch):
    monkeypatch.setenv("SPACE_PAYOUT_MODE", "test")
    worker.reset_test_state()

    result = worker.execute_payout(str(uuid4()), amount_cents=100)

    assert result["status"] == "error"
    assert "idempotency_key" in result["message"]
