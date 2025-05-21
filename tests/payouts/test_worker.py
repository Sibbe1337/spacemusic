import pytest
import uuid
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime

import stripe # type: ignore
import pybreaker # type: ignore

# Adjust imports based on your project structure
from services.payouts.worker import execute_payout, celery_app as payouts_celery_app, _create_ledger_entry
from services.offers.models import Offer # Assuming Offer.id is UUID
from services.payouts.models import LedgerEntry # To check ledger creation

# Fixture for a mock Offer object
@pytest.fixture
def mock_offer_for_payout():
    offer_id = uuid.uuid4()
    return Offer(
        id=offer_id,
        creator_id=uuid.uuid4(), # Assuming Creator.id is also UUID if related directly
        title="Test Payout Offer",
        status="OFFER_READY", # Status that allows payout
        price_median_eur=50000, # 500 EUR in cents
        # Add other necessary fields for Offer if accessed by the task
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

# Fixture for mocking the offers_engine session
@pytest.fixture
def mock_offers_session(monkeypatch, mock_offer_for_payout):
    mock_session_instance = MagicMock()
    # Simulate fetching the mock_offer_for_payout
    # This needs to correctly mock `session.exec(select(Offer).where(Offer.id == offer_id)).first()`
    def mock_exec_side_effect(statement):
        # Crude check if it's selecting Offer and by the right ID
        # A more robust mock would inspect the statement's where clause properly
        if statement.column_descriptions[0]["entity"] == Offer and \
           str(statement.whereclause.right.value) == str(mock_offer_for_payout.id):
            mock_result = MagicMock()
            mock_result.first.return_value = mock_offer_for_payout
            return mock_result
        mock_result_empty = MagicMock()
        mock_result_empty.first.return_value = None
        return mock_result_empty
        
    mock_session_instance.exec = MagicMock(side_effect=mock_exec_side_effect)
    mock_session_instance.get = MagicMock(return_value=mock_offer_for_payout) # For offer status update
    mock_session_instance.add = MagicMock()
    mock_session_instance.commit = MagicMock()

    mock_session_manager = MagicMock()
    mock_session_manager.__enter__.return_value = mock_session_instance
    mock_session_manager.__exit__.return_value = None
    monkeypatch.setattr("services.payouts.worker.Session", lambda engine: mock_session_manager if engine.url.database == "offers_db_mock" else MagicMock()) # Differentiate engines
    # Mock the engine itself to have a URL that we can check
    mock_engine = MagicMock()
    mock_engine.url.database = "offers_db_mock"
    monkeypatch.setattr("services.payouts.worker.offers_engine", mock_engine)
    return mock_session_instance

# Fixture for mocking the payouts_engine session (for ledger entries)
@pytest.fixture
def mock_payouts_ledger_session(monkeypatch):
    mock_session_instance = MagicMock()
    mock_session_instance.add = MagicMock()
    mock_session_instance.commit = MagicMock()
    mock_session_instance.refresh = MagicMock()

    mock_session_manager = MagicMock()
    mock_session_manager.__enter__.return_value = mock_session_instance
    mock_session_manager.__exit__.return_value = None
    # Patch the Session used with payouts_engine
    # Differentiate by engine URL or by patching Session where payouts_engine is used.
    def session_factory(engine_arg):
        if engine_arg.url.database == "payouts_db_mock":
            return mock_session_manager
        # Fallback for other engines if Session is used elsewhere unexpectedly
        real_session_manager = MagicMock() 
        real_session_manager.__enter__.return_value = MagicMock() # basic mock for other sessions
        real_session_manager.__exit__.return_value = None
        return real_session_manager

    monkeypatch.setattr("services.payouts.worker.Session", session_factory)
    mock_engine = MagicMock()
    mock_engine.url.database = "payouts_db_mock"
    monkeypatch.setattr("services.payouts.worker.payouts_engine", mock_engine)
    return mock_session_instance

@patch("services.payouts.worker.stripe.Transfer.create")
@patch("services.payouts.worker._call_wise_transfer") # Mock Wise as well
@patch("services.payouts.worker.stripe_breaker", new_callable=MagicMock) # Mock the circuit breaker itself
# @patch("services.payouts.worker.kafka_producer") # If kafka_producer is directly used and needs mocking
def test_execute_payout_stripe_success(
    # mock_kafka, 
    mock_breaker_obj, # The MagicMock instance for stripe_breaker
    mock_wise_call,
    mock_stripe_create,
    mock_offers_session, 
    mock_payouts_ledger_session, 
    mock_offer_for_payout
):
    # Ensure breaker calls the function directly (not open)
    mock_breaker_obj.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs) 

    mock_stripe_create.return_value = MagicMock(id="stripe_tx_123")
    offer_id_str = str(mock_offer_for_payout.id)

    result = execute_payout(offer_id_str)

    assert result["status"] == "success"
    assert result["method"] == "stripe"
    assert result["reference"] == "stripe_tx_123"
    mock_stripe_create.assert_called_once_with(
        amount=50000,
        currency="eur",
        destination=ANY, # os.getenv("STRIPE_CONNECT_ID")
        description=ANY,
        metadata=ANY
    )
    mock_wise_call.assert_not_called()
    # Assert ledger entry creation (via mock_payouts_ledger_session.add)
    assert mock_payouts_ledger_session.add.call_count == 1
    added_ledger_entry = mock_payouts_ledger_session.add.call_args[0][0]
    assert isinstance(added_ledger_entry, LedgerEntry)
    assert added_ledger_entry.reference_id == "stripe_tx_123"
    assert added_ledger_entry.transaction_type == "stripe_payout"

    # Assert offer status update (via mock_offers_session.add)
    assert mock_offers_session.add.call_count == 1 # Called once for status update
    updated_offer = mock_offers_session.add.call_args[0][0]
    assert updated_offer.status == "PAID_OUT"

    # mock_kafka.produce.assert_called_once() # If Kafka is mocked

@patch("services.payouts.worker.stripe.Transfer.create", side_effect=stripe.error.StripeError("Stripe Generic Error"))
@patch("services.payouts.worker._call_wise_transfer")
@patch("services.payouts.worker.stripe_breaker", new_callable=MagicMock)
# @patch("services.payouts.worker.kafka_producer")
def test_execute_payout_stripe_api_error_wise_success(
    # mock_kafka,
    mock_breaker_obj,
    mock_wise_call,
    mock_stripe_create_fails,
    mock_offers_session, 
    mock_payouts_ledger_session, 
    mock_offer_for_payout
):
    mock_breaker_obj.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)
    mock_wise_call.return_value = "wise_tx_456"
    offer_id_str = str(mock_offer_for_payout.id)

    result = execute_payout(offer_id_str)

    assert result["status"] == "success"
    assert result["method"] == "wise"
    assert result["reference"] == "wise_tx_456"
    mock_stripe_create_fails.assert_called_once()
    mock_wise_call.assert_called_once_with(mock_offer_for_payout, 50000, "EUR")
    assert mock_payouts_ledger_session.add.call_count == 1 # Ledger entry for Wise
    added_ledger_entry = mock_payouts_ledger_session.add.call_args[0][0]
    assert added_ledger_entry.reference_id == "wise_tx_456"
    assert added_ledger_entry.transaction_type == "wise_payout"

    assert mock_offers_session.add.call_count == 1
    updated_offer = mock_offers_session.add.call_args[0][0]
    assert updated_offer.status == "PAID_OUT"

@patch("services.payouts.worker._call_stripe_payout", side_effect=pybreaker.CircuitBreakerError("Stripe CB Open"))
@patch("services.payouts.worker._call_wise_transfer")
# @patch("services.payouts.worker.kafka_producer")
def test_execute_payout_stripe_circuit_breaker_open_wise_success(
    # mock_kafka,
    mock_wise_call,
    mock_stripe_call_cb_open, # This now mocks the helper _call_stripe_payout
    mock_offers_session, 
    mock_payouts_ledger_session, 
    mock_offer_for_payout
):
    mock_wise_call.return_value = "wise_tx_789"
    offer_id_str = str(mock_offer_for_payout.id)

    result = execute_payout(offer_id_str)

    assert result["status"] == "success"
    assert result["method"] == "wise"
    assert result["reference"] == "wise_tx_789"
    mock_stripe_call_cb_open.assert_called_once() # Original _call_stripe_payout was called
    mock_wise_call.assert_called_once_with(mock_offer_for_payout, 50000, "EUR")
    assert mock_payouts_ledger_session.add.call_count == 1

# Add tests for: offer not found, no median price, Stripe error + Wise error, config errors (no keys)

# Test for Celery task registration (optional)
def test_payout_task_registered():
    assert "services.payouts.worker.execute_payout" in payouts_celery_app.tasks 