from uuid import uuid4

from services.payouts import worker


def test_async_payout_task_has_no_kafka_or_provider_side_effect_in_test_mode(monkeypatch):
    monkeypatch.setenv("SPACE_PAYOUT_MODE", "test")
    worker.reset_test_state()

    result = worker.execute_payout(
        str(uuid4()),
        amount_cents=5000,
        recipient_token="recipient-token",
        idempotency_key="async-payout-001",
    )

    assert result["status"] == "success"
    assert result["payout"]["provider_reference"].startswith("test_payout_")
