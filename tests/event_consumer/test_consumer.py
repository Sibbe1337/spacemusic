# tests/event_consumer/test_consumer.py
import pytest
import json
from unittest.mock import patch, MagicMock
import uuid
from datetime import datetime

from confluent_kafka import Message # To create mock messages

# Adjust to your project structure
from services.event_consumer.consumer import main as consume_events, PAYOUT_SUCCEEDED_TOPIC, CONSUMER_GROUP_ID
# We will mock create_avro_consumer from libs.py_common.kafka

@pytest.fixture
def mock_kafka_consumer_for_event_consumer(monkeypatch):
    mock_consumer_instance = MagicMock()
    mock_consumer_instance.poll = MagicMock()
    mock_consumer_instance.commit = MagicMock()
    mock_consumer_instance.close = MagicMock()
    
    # Mock the create_avro_consumer function used within event_consumer.consumer.main
    mock_create_fn = MagicMock(return_value=mock_consumer_instance)
    monkeypatch.setattr("services.event_consumer.consumer.create_avro_consumer", mock_create_fn)
    # Also mock create_consumer if it's used as a fallback
    monkeypatch.setattr("services.event_consumer.consumer.create_consumer", mock_create_fn)
    
    return mock_consumer_instance, mock_create_fn

@patch("services.event_consumer.consumer.structlog.get_logger") # Mock logger to check output
@patch("services.event_consumer.consumer.start_metrics_server") # Mock metrics server start
@patch("services.event_consumer.consumer.Path.read_text") # Mock schema reading
def test_event_consumer_logs_payout_succeeded(
    mock_read_text: MagicMock,
    mock_start_metrics: MagicMock,
    mock_logger_get: MagicMock,
    mock_kafka_consumer_for_event_consumer: tuple[MagicMock, MagicMock],
    monkeypatch
):
    mock_consumer, mock_create_consumer_fn = mock_kafka_consumer_for_event_consumer
    mock_logger_instance = MagicMock()
    mock_logger_get.return_value = mock_logger_instance
    
    # Mock schema reading to succeed
    mock_read_text.return_value = '{"type": "record", "name": "PayoutSucceededEvent", "fields": []}' # Minimal valid Avro

    # --- Arrange: Prepare a mock Kafka message ---
    offer_id = uuid.uuid4()
    payout_event_data = {
        "offer_id": str(offer_id),
        "payout_method": "stripe",
        "reference_id": "stripe_tx_test123",
        "amount_cents": 75000, # 750 EUR
        "currency_code": "EUR",
        "timestamp": datetime.utcnow().isoformat()
    }

    # Simulate how AvroDeserializer would provide the value (as a dict)
    mock_message = MagicMock(spec=Message)
    mock_message.topic.return_value = PAYOUT_SUCCEEDED_TOPIC
    mock_message.partition.return_value = 0
    mock_message.offset.return_value = 100
    mock_message.error.return_value = None # No error
    mock_message.value.return_value = payout_event_data # Deserialized Avro message (dict)
    mock_message.key.return_value = str(offer_id).encode('utf-8')

    # Configure the consumer's poll method to return our mock message, then None to stop loop
    mock_consumer.poll.side_effect = [mock_message, None] # First poll gets message, second stops
    
    # --- Act ---
    # Temporarily patch `running` to False to make the consumer loop run once for the test
    monkeypatch.setattr("services.event_consumer.consumer.running", lambda: mock_consumer.poll.call_count <= 1)
    
    consume_events() # Run the main consumer loop

    # --- Assert ---
    mock_start_metrics.assert_called_once()
    mock_create_consumer_fn.assert_called_once_with(
        group_id=CONSUMER_GROUP_ID,
        topics=[PAYOUT_SUCCEEDED_TOPIC],
        value_schema_str=ANY # Schema string was read
    )
    mock_consumer.subscribe.assert_called_once_with([PAYOUT_SUCCEEDED_TOPIC])
    assert mock_consumer.poll.call_count >= 1 # Called at least once, maybe twice to exit
    
    # Check if the message was logged by structlog (inspect calls to the mocked logger)
    # This is a bit dependent on how you structure your logs with structlog.
    # Assuming logger.info was called with relevant data.
    found_log_call = False
    for call_args in mock_logger_instance.info.call_args_list:
        args, kwargs = call_args
        if args and args[0] == "Received payout.succeeded event":
            if kwargs.get("offer_id") == str(offer_id) and kwargs.get("payout_method") == "stripe":
                found_log_call = True
                break
    assert found_log_call, "Expected log for received payout.succeeded event not found."

    mock_consumer.commit.assert_called_once_with(message=mock_message)
    mock_consumer.close.assert_called_once()

# Add more tests: error handling, deserialization failures, etc. 