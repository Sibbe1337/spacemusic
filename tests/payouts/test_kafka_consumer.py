import pytest
from unittest.mock import patch, MagicMock, ANY
import uuid
import time
from threading import Event
import threading

# Module to test
from services.payouts import worker as payouts_worker # Import the worker module
from confluent_kafka import KafkaError, KafkaException # For creating mock errors

@pytest.fixture
def mock_kafka_message_valid():
    msg = MagicMock()
    msg.error.return_value = None
    msg.value.return_value = {
        "event_id": str(uuid.uuid4()),
        "offer_id": str(uuid.uuid4()),
        "amount_cents": 50000,
        "currency_code": "EUR",
        "recipient_details": "{\"provider\":\"stripe\",\"account_id\":\"acct_123\"}",
        "requested_at_micros": int(time.time() * 1_000_000)
    }
    msg.topic.return_value = payouts_worker.KAFKA_PAYOUT_REQUESTED_TOPIC
    msg.partition.return_value = 0
    msg.offset.return_value = 100
    msg.key.return_value = "some_key"
    return msg

@pytest.fixture
def mock_kafka_message_no_offer_id():
    msg = MagicMock()
    msg.error.return_value = None
    msg.value.return_value = {
        "event_id": str(uuid.uuid4()),
        # "offer_id": str(uuid.uuid4()), # Missing offer_id
        "amount_cents": 50000,
    }
    msg.topic.return_value = payouts_worker.KAFKA_PAYOUT_REQUESTED_TOPIC
    # ... (other attributes if needed by logger)
    return msg

@pytest.fixture
def mock_kafka_message_kafka_error():
    msg = MagicMock()
    mock_err = MagicMock(spec=KafkaError)
    mock_err.code.return_value = KafkaError._FAIL # A generic failure code
    msg.error.return_value = mock_err
    msg.topic.return_value = payouts_worker.KAFKA_PAYOUT_REQUESTED_TOPIC
    return msg

@pytest.fixture
def mock_kafka_message_eof():
    msg = MagicMock()
    mock_err = MagicMock(spec=KafkaError)
    mock_err.code.return_value = KafkaError._PARTITION_EOF
    msg.error.return_value = mock_err
    msg.topic.return_value = payouts_worker.KAFKA_PAYOUT_REQUESTED_TOPIC
    # ... (other attributes if needed by logger)
    return msg


@patch("services.payouts.worker.execute_payout.delay") # Mock the Celery task's delay method
@patch("services.payouts.worker.get_offer_payout_requested_consumer") # Mock the function that returns the consumer
@patch("services.payouts.worker.KAFKA_MESSAGES_CONSUMED_TOTAL") # Mock the metric
@patch("services.payouts.worker.logger") # Mock logger
def test_consume_payout_requests_success(
    mock_logger,
    mock_kafka_metric,
    mock_get_consumer,
    mock_execute_payout_delay,
    mock_kafka_message_valid
):
    mock_consumer_instance = MagicMock()
    # Simulate poll returning a valid message once, then None to stop the loop for the test
    mock_consumer_instance.poll.side_effect = [mock_kafka_message_valid, None] 
    mock_consumer_instance.commit = MagicMock()
    mock_get_consumer.return_value = mock_consumer_instance

    # Set the stop event after the second poll (which returns None)
    payouts_worker._kafka_consumer_thread_stop_event.set() 

    payouts_worker.consume_payout_requests()

    valid_payload = mock_kafka_message_valid.value()
    mock_execute_payout_delay.assert_called_once_with(offer_id_str=valid_payload['offer_id'])
    mock_consumer_instance.commit.assert_called_once_with(message=mock_kafka_message_valid)
    mock_kafka_metric.labels.assert_called_once_with(topic=payouts_worker.KAFKA_PAYOUT_REQUESTED_TOPIC, group_id=payouts_worker.KAFKA_CONSUMER_GROUP_ID_PAYOUT_REQUESTED, status="success")
    mock_kafka_metric.labels.return_value.inc.assert_called_once()
    mock_logger.info.assert_any_call("Dispatching execute_payout task for offer", offer_id=valid_payload['offer_id'])

    # Reset the stop event for other tests if it's global
    payouts_worker._kafka_consumer_thread_stop_event.clear()

@patch("services.payouts.worker.execute_payout.delay")
@patch("services.payouts.worker.get_offer_payout_requested_consumer")
@patch("services.payouts.worker.KAFKA_MESSAGES_CONSUMED_TOTAL")
@patch("services.payouts.worker.logger")
def test_consume_payout_requests_message_no_offer_id(
    mock_logger,
    mock_kafka_metric,
    mock_get_consumer,
    mock_execute_payout_delay,
    mock_kafka_message_no_offer_id # Use the fixture for message without offer_id
):
    mock_consumer_instance = MagicMock()
    # Simulate poll returning the invalid message once, then None
    mock_consumer_instance.poll.side_effect = [mock_kafka_message_no_offer_id, None]
    mock_consumer_instance.commit = MagicMock()
    mock_get_consumer.return_value = mock_consumer_instance

    payouts_worker._kafka_consumer_thread_stop_event.set()

    payouts_worker.consume_payout_requests()

    mock_execute_payout_delay.assert_not_called() # Crucial: task should not be dispatched
    mock_consumer_instance.commit.assert_called_once_with(message=mock_kafka_message_no_offer_id) # Should still commit offset
    
    mock_logger.warning.assert_any_call(
        "Consumed message missing offer_id or data", 
        raw_message_value=mock_kafka_message_no_offer_id.value()
    )
    mock_kafka_metric.labels.assert_any_call(
        topic=payouts_worker.KAFKA_PAYOUT_REQUESTED_TOPIC, 
        group_id=payouts_worker.KAFKA_CONSUMER_GROUP_ID_PAYOUT_REQUESTED, 
        status="parse_error"
    )
    mock_kafka_metric.labels.return_value.inc.assert_called()

    payouts_worker._kafka_consumer_thread_stop_event.clear()

@patch("services.payouts.worker.execute_payout.delay")
@patch("services.payouts.worker.get_offer_payout_requested_consumer")
@patch("services.payouts.worker.APP_ERRORS_TOTAL") # Metric for general app errors
@patch("services.payouts.worker.logger")
@patch("time.sleep") # To prevent actual sleep during test
def test_consume_payout_requests_kafka_error(
    mock_sleep, # Mock for time.sleep
    mock_logger,
    mock_app_errors_metric, # Use APP_ERRORS_TOTAL as per worker code
    mock_get_consumer,
    mock_execute_payout_delay,
    mock_kafka_message_kafka_error # Use the fixture for Kafka error message
):
    mock_consumer_instance = MagicMock()
    # Simulate poll returning the error message once, then None
    mock_consumer_instance.poll.side_effect = [mock_kafka_message_kafka_error, None] 
    mock_consumer_instance.commit = MagicMock() # Should not be called on error before processing
    mock_get_consumer.return_value = mock_consumer_instance

    payouts_worker._kafka_consumer_thread_stop_event.set()

    payouts_worker.consume_payout_requests()

    mock_execute_payout_delay.assert_not_called()
    mock_consumer_instance.commit.assert_not_called() # Commit should not happen if error is before value processing
    
    mock_logger.error.assert_any_call(
        "Kafka consumer error", 
        error=mock_kafka_message_kafka_error.error(), 
        topic=mock_kafka_message_kafka_error.topic()
    )
    mock_app_errors_metric.labels.assert_any_call(
        component="kafka_consumer_poll", 
        error_type=str(KafkaError._FAIL) # As defined in the fixture
    )
    mock_app_errors_metric.labels.return_value.inc.assert_called()
    mock_sleep.assert_called_once_with(5) # Check that sleep was called

    payouts_worker._kafka_consumer_thread_stop_event.clear()

@patch("services.payouts.worker.execute_payout.delay")
@patch("services.payouts.worker.get_offer_payout_requested_consumer")
@patch("services.payouts.worker.logger")
@patch("services.payouts.worker.APP_ERRORS_TOTAL") # To ensure it's NOT called
@patch("services.payouts.worker.KAFKA_MESSAGES_CONSUMED_TOTAL") # To ensure it's NOT called for error/parse_error
def test_consume_payout_requests_eof(
    mock_kafka_metric_consumed, # KAFKA_MESSAGES_CONSUMED_TOTAL
    mock_app_errors_metric,   # APP_ERRORS_TOTAL
    mock_logger,
    mock_get_consumer,
    mock_execute_payout_delay,
    mock_kafka_message_eof # Use the fixture for EOF message
):
    mock_consumer_instance = MagicMock()
    # Simulate poll returning the EOF message once, then None
    mock_consumer_instance.poll.side_effect = [mock_kafka_message_eof, None]
    mock_consumer_instance.commit = MagicMock()
    mock_get_consumer.return_value = mock_consumer_instance

    payouts_worker._kafka_consumer_thread_stop_event.set()

    payouts_worker.consume_payout_requests()

    mock_execute_payout_delay.assert_not_called()
    mock_consumer_instance.commit.assert_not_called() # No message to commit in terms of value processing
    
    # Check for the specific debug log for EOF
    found_eof_log = False
    for call in mock_logger.debug.call_args_list:
        args, _ = call
        if args and payouts_worker.KAFKA_PAYOUT_REQUESTED_TOPIC in args[0] and "reached end at offset" in args[0]:
            found_eof_log = True
            break
    assert found_eof_log, "Expected EOF debug log was not found."

    mock_logger.error.assert_not_called() # No errors should be logged for EOF
    mock_app_errors_metric.labels.return_value.inc.assert_not_called()
    mock_kafka_metric_consumed.labels.return_value.inc.assert_not_called() # No successful or parse_error consumption

    payouts_worker._kafka_consumer_thread_stop_event.clear()

@patch("services.payouts.worker.get_offer_payout_requested_consumer")
@patch("services.payouts.worker.logger") # To check for stopping log message
def test_consumer_loop_stops_on_event(
    mock_logger,
    mock_get_consumer
):
    """Test that the consumer loop stops when the stop event is set."""
    mock_consumer_instance = MagicMock()
    # Simulate poll always returning None, so the loop relies on the event to stop
    mock_consumer_instance.poll.return_value = None 
    mock_consumer_instance.close = MagicMock() # To verify it gets called
    mock_get_consumer.return_value = mock_consumer_instance

    # Clear the event initially, then set it from another thread or after a delay
    payouts_worker._kafka_consumer_thread_stop_event.clear()

    consumer_loop_thread = threading.Thread(target=payouts_worker.consume_payout_requests)
    consumer_loop_thread.daemon = True # So it doesn't block test exit
    consumer_loop_thread.start()

    # Give the loop a moment to start and poll a few times
    time.sleep(0.1) 

    # Signal the loop to stop
    payouts_worker._kafka_consumer_thread_stop_event.set()
    
    # Wait for the thread to finish (it should exit quickly after event is set)
    consumer_loop_thread.join(timeout=2) # Join with a timeout

    assert not consumer_loop_thread.is_alive(), "Consumer thread did not stop after event was set."
    mock_consumer_instance.close.assert_called_once()
    mock_logger.info.assert_any_call("Kafka consumer loop for payout requests stopping.")

    # Clear the event again for subsequent tests
    payouts_worker._kafka_consumer_thread_stop_event.clear()

@patch("services.payouts.worker.create_avro_consumer") # Mock the actual consumer creation
@patch("services.payouts.worker.Path.is_file", return_value=True) # Assume schema file exists
@patch("builtins.open") # Mock open to simulate reading schema string
@patch("services.payouts.worker.logger")
@patch("services.payouts.worker.APP_ERRORS_TOTAL")
def test_get_offer_payout_requested_consumer_initialization_failure(
    mock_app_errors,
    mock_logger,
    mock_open,
    mock_is_file,
    mock_create_avro_consumer
):
    """Test consumer getter when create_avro_consumer fails."""
    mock_create_avro_consumer.side_effect = KafkaException("Mocked Kafka connection error")
    payouts_worker._offer_payout_requested_consumer = None # Reset for test

    consumer = payouts_worker.get_offer_payout_requested_consumer()

    assert consumer is None
    mock_logger.error.assert_called_with(
        "Failed to initialize Kafka consumer for offer.payout.requested", 
        error=ANY, 
        exc_info=True
    )
    mock_app_errors.labels.assert_called_once_with(component="kafka_consumer_init", error_type="offer_payout_requested")
    mock_app_errors.labels.return_value.inc.assert_called_once()

@patch("services.payouts.worker.Path.is_file", return_value=False) # Simulate schema file NOT found
@patch("services.payouts.worker.logger")
@patch("services.payouts.worker.APP_ERRORS_TOTAL")
@patch("services.payouts.worker.create_avro_consumer") # Ensure this isn't called
def test_get_offer_payout_requested_consumer_schema_file_not_found(
    mock_create_avro_consumer_not_called,
    mock_app_errors,
    mock_logger,
    mock_is_file # This is already patched by the decorator
):
    """Test consumer getter when schema file is not found."""
    payouts_worker._offer_payout_requested_consumer = None # Reset for test
    payouts_worker._offer_payout_requested_schema_str = None # Reset schema string

    with pytest.raises(FileNotFoundError) as excinfo:
        payouts_worker.get_offer_payout_requested_consumer()
    
    assert str(payouts_worker.OFFER_PAYOUT_REQUESTED_SCHEMA_PATH) in str(excinfo.value)
    assert payouts_worker._offer_payout_requested_consumer is None
    mock_logger.error.assert_called_with(
        "Schema file not found for offer.payout.requested", 
        path=str(payouts_worker.OFFER_PAYOUT_REQUESTED_SCHEMA_PATH)
    )
    # APP_ERRORS_TOTAL is not called in this specific path by the current get_offer_payout_requested_consumer code,
    # as FileNotFoundError is raised before. If it were to be caught and logged to APP_ERRORS_TOTAL,
    # this assertion would change.
    mock_app_errors.labels.assert_not_called()
    mock_create_avro_consumer_not_called.assert_not_called()

@patch("services.payouts.worker.Path.is_file", return_value=True) # Assume schema file itself exists
@patch("builtins.open") # Mock open to simulate reading schema string
@patch("libs.py_common.kafka.os.getenv") # Mock os.getenv specifically within the kafka lib module
@patch("services.payouts.worker.logger")
@patch("services.payouts.worker.APP_ERRORS_TOTAL")
def test_get_offer_payout_requested_consumer_no_schema_registry_url(
    mock_app_errors,
    mock_logger,
    mock_os_getenv_kafka_lib, # This is the mock for os.getenv in libs.py_common.kafka
    mock_open, # For schema file reading
    mock_is_file # For schema file existence check
):
    """Test consumer getter when SCHEMA_REGISTRY_URL is not set."""
    # Simulate os.getenv within libs.py_common.kafka.py returning None for SCHEMA_REGISTRY_URL
    # It also gets called for KAFKA_BOOTSTRAP_SERVERS, so handle that.
    def getenv_side_effect(key, default=None):
        if key == "SCHEMA_REGISTRY_URL":
            return None
        if key == "KAFKA_BOOTSTRAP_SERVERS":
            return "dummy_broker:9092" # Must return something for Consumer config
        return default
    mock_os_getenv_kafka_lib.side_effect = getenv_side_effect
    
    # Reset global SchemaRegistryClient in libs.py_common.kafka to force re-initialization
    # This is a bit intrusive but necessary as it's a global singleton
    with patch("libs.py_common.kafka._schema_registry_client", new=None):
        payouts_worker._offer_payout_requested_consumer = None # Reset for test
        payouts_worker._offer_payout_requested_schema_str = "{\"type\": \"string\"}" # Dummy schema to pass schema loading
        mock_open.return_value.read.return_value = payouts_worker._offer_payout_requested_schema_str

        consumer = payouts_worker.get_offer_payout_requested_consumer()

        assert consumer is None
        # The actual error logged would be from libs.py_common.kafka.get_schema_registry_client
        # or from create_avro_consumer if it catches the ValueError from get_schema_registry_client.
        # The payouts_worker.get_offer_payout_requested_consumer catches the top-level Exception.
        mock_logger.error.assert_called_with(
            "Failed to initialize Kafka consumer for offer.payout.requested", 
            error=ANY, # The error will be a ValueError from get_schema_registry_client
            exc_info=True
        )
        mock_app_errors.labels.assert_called_once_with(component="kafka_consumer_init", error_type="offer_payout_requested")
        mock_app_errors.labels.return_value.inc.assert_called_once()

# TODO: Review if any other specific error cases for get_offer_payout_requested_consumer are needed.

# ... (rest of the file remains unchanged) 