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

@patch("services.payouts.worker.APP_ERRORS_TOTAL")
@patch("services.payouts.worker.stripe.Transfer.create") # Mock to prevent actual calls
@patch("services.payouts.worker._call_wise_transfer")   # Mock to prevent actual calls
def test_execute_payout_offer_not_found(
    mock_wise_call, 
    mock_stripe_create, 
    mock_app_errors_total, 
    mock_offers_session, 
    mock_payouts_ledger_session # Fixture needed even if not directly used, due to session patching
):
    """Test that execute_payout handles the case where the offer is not found."""
    # Configure the mock_offers_session.exec().first() to return None
    # This simulates the offer not being found in the database.
    mock_session_instance = mock_offers_session # This is already the MagicMock instance from the fixture
    
    # Modify the side_effect of the exec mock specifically for this test if needed,
    # or ensure the default fixture behavior for non-matching IDs returns None.
    # The current mock_offers_session fixture already returns None if the ID doesn't match mock_offer_for_payout.id.
    # For a truly non-existent ID, we can refine the mock:
    def specific_exec_side_effect(statement):
        # Always return a mock that results in .first() being None for this test
        mock_result_empty = MagicMock()
        mock_result_empty.first.return_value = None
        return mock_result_empty
    mock_session_instance.exec = MagicMock(side_effect=specific_exec_side_effect)

    non_existent_offer_id = uuid.uuid4()
    result = execute_payout(str(non_existent_offer_id))

    assert result["status"] == "error"
    assert result["message"] == "Offer not found"
    
    # Verify that no payment provider calls were made
    mock_stripe_create.assert_not_called()
    mock_wise_call.assert_not_called()
    
    # Verify no ledger entries were made
    mock_payouts_ledger_session.add.assert_not_called()
    
    # Verify offer status was not attempted to be updated (since it wasn't found)
    # The mock_offers_session.add is used for status updates in successful paths
    mock_offers_session.add.assert_not_called() 

    # Verify metrics
    mock_app_errors_total.labels.assert_called_once_with(component="execute_payout", error_type="offer_not_found")
    mock_app_errors_total.labels.return_value.inc.assert_called_once()

@patch("services.payouts.worker.APP_ERRORS_TOTAL")
@patch("services.payouts.worker.stripe.Transfer.create") # Mock to prevent actual calls
@patch("services.payouts.worker._call_wise_transfer")   # Mock to prevent actual calls
def test_execute_payout_no_median_price(
    mock_wise_call,
    mock_stripe_create,
    mock_app_errors_total,
    mock_offers_session,      # Used to return the modified offer
    mock_payouts_ledger_session, # Fixture needed
    mock_offer_for_payout     # The offer fixture to modify
):
    """Test that execute_payout handles an offer with no median price."""
    # Modify the offer to have no median price
    mock_offer_for_payout.price_median_eur = None

    # Ensure the mock_offers_session returns this modified offer
    # The mock_offers_session.exec is already set up in the fixture to return mock_offer_for_payout
    # if the ID matches. We'll use the ID from mock_offer_for_payout.
    # To be absolutely sure mock_session_instance.exec returns our modified mock_offer_for_payout:
    def mock_exec_for_this_test(statement):
        if str(statement.whereclause.right.value) == str(mock_offer_for_payout.id):
            mock_result = MagicMock()
            mock_result.first.return_value = mock_offer_for_payout # This is our modified one
            return mock_result
        mock_result_empty = MagicMock()
        mock_result_empty.first.return_value = None
        return mock_result_empty
    mock_offers_session.exec = MagicMock(side_effect=mock_exec_for_this_test)


    offer_id_str = str(mock_offer_for_payout.id)
    result = execute_payout(offer_id_str)

    assert result["status"] == "error"
    assert result["message"] == "Median price not available"

    mock_stripe_create.assert_not_called()
    mock_wise_call.assert_not_called()
    mock_payouts_ledger_session.add.assert_not_called()
    mock_offers_session.add.assert_not_called() # No status update should occur

    # Verify metrics
    mock_app_errors_total.labels.assert_called_once_with(component="execute_payout", error_type="no_median_price")
    mock_app_errors_total.labels.return_value.inc.assert_called_once()

@patch("services.payouts.worker.APP_ERRORS_TOTAL")
@patch("services.payouts.worker.WISE_TRANSFERS_TOTAL") # To check Wise failure metric
@patch("services.payouts.worker.stripe_breaker", new_callable=MagicMock) # To mock Stripe call path
@patch("services.payouts.worker._call_wise_transfer") # Mock the Wise call itself
def test_execute_payout_stripe_and_wise_fail(
    mock_wise_call_fails, # This will mock _call_wise_transfer
    mock_stripe_breaker_obj, # This mocks the stripe_breaker decorator's behavior
    mock_wise_transfers_total,
    mock_app_errors_total,
    mock_offers_session, 
    mock_payouts_ledger_session, 
    mock_offer_for_payout
):
    """Test payout failure when both Stripe and Wise attempts fail."""
    # 1. Configure Stripe path to fail (e.g., Stripe API error)
    # We achieve this by making the stripe_breaker execute a function that raises StripeError
    def simulated_stripe_call_failure(*args, **kwargs):
        raise stripe.error.StripeError("Simulated Stripe API Error")
    
    # The stripe_breaker fixture in other tests is set to directly call the wrapped function.
    # Here, we want the breaker to call our failing function when _call_stripe_payout is attempted.
    # So, we need to mock _call_stripe_payout itself or ensure the breaker calls our failing function.
    # Easiest is to mock _call_stripe_payout to raise the error, assuming the breaker calls it.
    # Let's adjust the mock_stripe_breaker_obj to simulate this behavior.
    # The stripe_breaker is applied to _call_stripe_payout.
    # We need to ensure that when _call_stripe_payout (via the breaker) is invoked, it raises an error.
    # One way: mock_stripe_breaker_obj.side_effect will apply to the *decorator itself* which is complex.
    # A simpler approach for this specific test: patch _call_stripe_payout directly *after* the breaker has been applied to it.
    # However, the existing tests patch stripe.Transfer.create which is *inside* _call_stripe_payout.
    # Let's use the existing pattern: mock_stripe_breaker_obj allows the call, and stripe.Transfer.create (mocked elsewhere if needed, or here) fails.
    
    # For this test, let's assume _call_stripe_payout is called (breaker is closed or allows it)
    # and then it internally fails due to stripe.Transfer.create raising an error.
    # We can patch stripe.Transfer.create if it's not already patched, or ensure the main 
    # _call_stripe_payout (which is what the worker calls) raises the error.

    # To make _call_stripe_payout itself fail as if Stripe API returned an error:
    # This is more direct than mocking stripe.Transfer.create for this specific test focus.
    with patch("services.payouts.worker._call_stripe_payout", side_effect=stripe.error.StripeError("Simulated Stripe API Error")) as mock_actual_stripe_call:
        # 2. Configure Wise call to fail
        # _call_wise_transfer is already mocked by mock_wise_call_fails
        mock_wise_call_fails.side_effect = Exception("Simulated Wise API Error") # Generic Exception or httpx.RequestError

        offer_id_str = str(mock_offer_for_payout.id)
        result = execute_payout(offer_id_str)

        assert result["status"] == "error"
        # The message will depend on which error is caught last by execute_payout's logic.
        # If Stripe fails, it attempts Wise. If Wise then fails, the message should reflect the Wise failure.
        assert "Wise fallback failed" in result["message"] or "Wise transfer also failed" in result["message"]

        mock_actual_stripe_call.assert_called_once()
        mock_wise_call_fails.assert_called_once_with(mock_offer_for_payout, 50000, "EUR")
        
        mock_payouts_ledger_session.add.assert_not_called()
        mock_offers_session.add.assert_not_called() # No status update should occur

        # Verify APP_ERRORS_TOTAL metrics (called for Stripe error, then for Wise error)
        # This gets a bit tricky with multiple calls to .labels().inc()
        # We check that it was called with the expected error types.
        app_error_calls = mock_app_errors_total.labels.call_args_list
        # print(f"APP_ERRORS_TOTAL calls: {app_error_calls}") # For debugging
        
        # Check for Stripe error metric (could be api_error or circuit_breaker related if we didn't mock _call_stripe_payout so directly)
        # Since we directly mock _call_stripe_payout to throw StripeError, the execute_payout should log it.
        # The actual label might be more specific like 'stripe_call' and some e.code
        # For simplicity, we assume a general error logging from execute_payout's StripeError handling path.
        
        # Check for Wise error metric
        found_wise_error_metric = False
        for call in app_error_calls:
            if call[1].get('component') == 'wise_call' and call[1].get('error_type') in ['fallback_failure', 'fallback_failure_after_stripe_error']:
                found_wise_error_metric = True
                break
        assert found_wise_error_metric, "Wise failure metric was not recorded correctly on APP_ERRORS_TOTAL"
        # mock_app_errors_total.labels.return_value.inc.assert_any_call() # Ensure inc was called

        # Verify WISE_TRANSFERS_TOTAL metric for failure
        mock_wise_transfers_total.labels.assert_called_with(outcome="failure")
        mock_wise_transfers_total.labels.return_value.inc.assert_called_once()

# Test for Celery task registration (optional)
def test_payout_task_registered():
    assert "services.payouts.worker.execute_payout" in payouts_celery_app.tasks 