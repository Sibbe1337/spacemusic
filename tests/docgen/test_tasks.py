import pytest
from unittest.mock import patch, MagicMock, ANY # Added for further tests
import uuid # Added for further tests
import time # Added for further tests
from threading import Event # Added for further tests

# Adjust the import path according to your project structure
# This assumes that celery_app is defined in services.docgen.tasks
from services.docgen import tasks as docgen_tasks # Import the tasks module
from services.docgen.tasks import celery_app as docgen_celery_app
from confluent_kafka import KafkaError # For mocking Kafka errors


def test_generate_termsheet_task_registered():
    """Test that the generate_termsheet Celery task is registered."""
    # The name used in the decorator @celery_app.task(name=...)
    expected_task_name = "services.docgen.tasks.generate_termsheet"
    assert expected_task_name in docgen_celery_app.tasks, f"Task {expected_task_name} not found in registered Celery tasks: {list(docgen_celery_app.tasks.keys())}" 

def test_generate_receipt_pdf_task_registered():
    """Test that the generate_receipt_pdf Celery task is registered."""
    expected_task_name = "services.docgen.tasks.generate_receipt_pdf"
    assert expected_task_name in docgen_celery_app.tasks, f"Task {expected_task_name} not found in registered Celery tasks: {list(docgen_celery_app.tasks.keys())}"

# Fixtures for Kafka messages (similar to payouts consumer tests)
@pytest.fixture
def mock_kafka_payout_completed_success_msg():
    msg = MagicMock()
    msg.error.return_value = None
    msg.value.return_value = {
        "event_id": str(uuid.uuid4()),
        "offer_id": str(uuid.uuid4()),
        "payout_method": "stripe",
        "reference_id": "stripe_tx_123",
        "amount_cents": 50000,
        "currency_code": "EUR",
        "status": "SUCCESS",
        "failure_reason": None,
        "completed_at_micros": int(time.time() * 1_000_000)
    }
    msg.topic.return_value = docgen_tasks.KAFKA_PAYOUT_COMPLETED_TOPIC
    # ... other attributes if needed by logger or commit
    return msg

@pytest.fixture
def mock_kafka_payout_completed_failure_msg(mock_kafka_payout_completed_success_msg): # Reuse success message and modify
    msg = mock_kafka_payout_completed_success_msg
    msg.value.return_value["status"] = "FAILURE"
    msg.value.return_value["failure_reason"] = "Insufficient funds"
    return msg

@patch("services.docgen.tasks.generate_receipt_pdf.delay") # Mock the Celery task's delay method
@patch("services.docgen.tasks.get_offer_payout_completed_consumer") # Mock the function that returns the consumer
@patch("services.docgen.tasks.KAFKA_MESSAGES_CONSUMED_TOTAL") 
@patch("services.docgen.tasks.logger")
def test_consume_payout_completed_event_success(
    mock_logger,
    mock_kafka_metric,
    mock_get_consumer,
    mock_generate_receipt_delay,
    mock_kafka_payout_completed_success_msg
):
    """Test consuming a successful payout.completed event."""
    mock_consumer_instance = MagicMock()
    mock_consumer_instance.poll.side_effect = [mock_kafka_payout_completed_success_msg, None]
    mock_consumer_instance.commit = MagicMock()
    mock_get_consumer.return_value = mock_consumer_instance

    docgen_tasks._docgen_kafka_consumer_thread_stop_event.set() # To make the loop run once

    docgen_tasks.consume_payout_completed_events()

    event_payload = mock_kafka_payout_completed_success_msg.value()
    mock_generate_receipt_delay.assert_called_once_with(offer_id=event_payload['offer_id'], event_data=event_payload)
    mock_consumer_instance.commit.assert_called_once_with(message=mock_kafka_payout_completed_success_msg)
    mock_kafka_metric.labels.assert_called_with(topic=docgen_tasks.KAFKA_PAYOUT_COMPLETED_TOPIC, group_id=docgen_tasks.KAFKA_CONSUMER_GROUP_ID_PAYOUT_COMPLETED, status="success")
    mock_logger.info.assert_any_call("Dispatching generate_receipt_pdf task for successful payout", offer_id=event_payload['offer_id'])

    docgen_tasks._docgen_kafka_consumer_thread_stop_event.clear() # Reset for other tests


@patch("services.docgen.tasks.generate_receipt_pdf.delay")
@patch("services.docgen.tasks.get_offer_payout_completed_consumer")
@patch("services.docgen.tasks.logger")
def test_consume_payout_completed_event_failure_status(
    mock_logger,
    mock_get_consumer,
    mock_generate_receipt_delay,
    mock_kafka_payout_completed_failure_msg
):
    """Test consuming a payout.completed event with FAILURE status."""
    mock_consumer_instance = MagicMock()
    mock_consumer_instance.poll.side_effect = [mock_kafka_payout_completed_failure_msg, None]
    mock_consumer_instance.commit = MagicMock()
    mock_get_consumer.return_value = mock_consumer_instance

    docgen_tasks._docgen_kafka_consumer_thread_stop_event.set()
    docgen_tasks.consume_payout_completed_events()

    mock_generate_receipt_delay.assert_not_called()
    mock_consumer_instance.commit.assert_called_once_with(message=mock_kafka_payout_completed_failure_msg)
    mock_logger.info.assert_any_call("Payout failed for offer, no receipt will be generated.", offer_id=ANY, reason=ANY)
    docgen_tasks._docgen_kafka_consumer_thread_stop_event.clear()


@patch("services.docgen.tasks.render_receipt_pdf_and_upload")
@patch("services.docgen.tasks.get_offer_receipt_generated_producer")
@patch("services.docgen.tasks.CELERY_TASKS_PROCESSED_TOTAL")
@patch("services.docgen.tasks.KAFKA_MESSAGES_PRODUCED_TOTAL")
@patch("services.docgen.tasks.APP_ERRORS_TOTAL") # To check it's not called on success
@patch("services.docgen.tasks.logger")
def test_generate_receipt_pdf_task_success(
    mock_logger,
    mock_app_errors,
    mock_kafka_produced_metric,
    mock_celery_processed_metric,
    mock_get_receipt_producer, 
    mock_render_and_upload,
    mock_kafka_payout_completed_success_msg # Use this to get valid event_data
):
    """Test the generate_receipt_pdf Celery task for successful execution."""
    event_data = mock_kafka_payout_completed_success_msg.value()
    offer_id = event_data['offer_id']
    
    mock_s3_url = f"https://s3.example.com/receipts/{offer_id}/receipt.pdf"
    mock_pdf_hash = "sha256_mock_hash_value"
    mock_render_and_upload.return_value = (mock_s3_url, mock_pdf_hash)

    mock_producer_instance = MagicMock()
    mock_producer_instance.produce = MagicMock()
    mock_producer_instance.poll = MagicMock()
    mock_get_receipt_producer.return_value = mock_producer_instance
    # Also mock the global schema string variable that the task checks
    docgen_tasks._offer_receipt_generated_schema_str = "{\"type\": \"string\"}" # Dummy schema

    result = docgen_tasks.generate_receipt_pdf(offer_id=offer_id, event_data=event_data)

    mock_render_and_upload.assert_called_once_with(event_data)
    assert result == {"status": "success", "offer_id": offer_id, "receipt_url": mock_s3_url}

    # Verify Kafka event production
    mock_get_receipt_producer.assert_called_once()
    mock_producer_instance.produce.assert_called_once()
    produce_args, produce_kwargs = mock_producer_instance.produce.call_args
    assert produce_kwargs["topic"] == docgen_tasks.OFFER_RECEIPT_GENERATED_TOPIC
    assert produce_kwargs["key"] == offer_id
    receipt_payload = produce_kwargs["value"]
    assert receipt_payload["offer_id"] == offer_id
    assert receipt_payload["receipt_url"] == mock_s3_url
    assert receipt_payload["receipt_hash_sha256"] == mock_pdf_hash
    assert "event_id" in receipt_payload
    assert "generated_at_micros" in receipt_payload

    mock_celery_processed_metric.labels.assert_called_with(task_name="services.docgen.tasks.generate_receipt_pdf", status="success")
    mock_kafka_produced_metric.labels.assert_called_with(topic=docgen_tasks.OFFER_RECEIPT_GENERATED_TOPIC, status="success")
    mock_app_errors.labels.assert_not_called() # No app errors expected

@patch("services.docgen.tasks.render_receipt_pdf_and_upload")
@patch("services.docgen.tasks.get_offer_receipt_generated_producer")
@patch("services.docgen.tasks.CELERY_TASKS_PROCESSED_TOTAL")
@patch("services.docgen.tasks.KAFKA_MESSAGES_PRODUCED_TOTAL") # Should not be called successfully
@patch("services.docgen.tasks.logger")
def test_generate_receipt_pdf_task_kafka_producer_unavailable(
    mock_logger,
    mock_kafka_produced_metric, 
    mock_celery_processed_metric,
    mock_get_receipt_producer, 
    mock_render_and_upload,
    mock_kafka_payout_completed_success_msg
):
    """Test generate_receipt_pdf task when Kafka producer for receipt.generated is unavailable."""
    event_data = mock_kafka_payout_completed_success_msg.value()
    offer_id = event_data['offer_id']
    
    mock_s3_url = f"https://s3.example.com/receipts/{offer_id}/receipt.pdf"
    mock_pdf_hash = "sha256_mock_hash_value"
    mock_render_and_upload.return_value = (mock_s3_url, mock_pdf_hash)

    # Simulate producer not being available
    mock_get_receipt_producer.return_value = None
    # Ensure the global schema string is also None, as the check is `if producer and _offer_receipt_generated_schema_str:`
    with patch.object(docgen_tasks, '_offer_receipt_generated_schema_str', None):
        result = docgen_tasks.generate_receipt_pdf(offer_id=offer_id, event_data=event_data)

    mock_render_and_upload.assert_called_once_with(event_data)
    # Task still returns success obiect, but logs a warning
    assert result == {"status": "success", "offer_id": offer_id, "receipt_url": mock_s3_url}
    
    mock_logger.warning.assert_any_call("Kafka producer for offer.receipt.generated not available. Event not sent.", offer_id=offer_id)
    mock_kafka_produced_metric.labels.assert_not_called() # No metric if producer is None
    mock_celery_processed_metric.labels.assert_called_with(task_name="services.docgen.tasks.generate_receipt_pdf", status="success")


@patch("services.docgen.tasks.render_receipt_pdf_and_upload")
@patch("services.docgen.tasks.get_offer_receipt_generated_producer")
@patch("services.docgen.tasks.CELERY_TASKS_PROCESSED_TOTAL")
@patch("services.docgen.tasks.KAFKA_MESSAGES_PRODUCED_TOTAL")
@patch("services.docgen.tasks.APP_ERRORS_TOTAL")
@patch("services.docgen.tasks.logger")
def test_generate_receipt_pdf_task_render_fail(
    mock_logger,
    mock_app_errors, # APP_ERRORS_TOTAL
    mock_kafka_produced_metric, 
    mock_celery_processed_metric,
    mock_get_receipt_producer,
    mock_render_and_upload,
    mock_kafka_payout_completed_success_msg # Use valid input event_data
):
    """Test generate_receipt_pdf task when PDF rendering/upload fails."""
    event_data = mock_kafka_payout_completed_success_msg.value()
    offer_id = event_data['offer_id']
    
    mock_render_and_upload.return_value = (None, None) # Simulate failure

    with pytest.raises(Exception, match=f"Failed to generate/upload receipt for offer {offer_id}"):
        docgen_tasks.generate_receipt_pdf(offer_id=offer_id, event_data=event_data)

    mock_render_and_upload.assert_called_once_with(event_data)
    mock_get_receipt_producer.assert_not_called() # Kafka producer should not be called
    mock_kafka_produced_metric.labels.assert_not_called()

    # Verify metrics for failure in pdf processing
    mock_celery_processed_metric.labels.assert_called_with(task_name="services.docgen.tasks.generate_receipt_pdf", status="failure_pdf_processing")
    # APP_ERRORS_TOTAL is called inside render_receipt_pdf_and_upload, so we don't assert it here directly for the task level unless it's a different label

# TODO: Add test for generate_receipt_pdf task when Kafka producer for receipt is unavailable
# TODO: Add tests for Kafka errors, EOF, loop stop for docgen consumer (similar to payouts consumer tests)
# TODO: Add tests for get_offer_payout_completed_consumer initialization failures 

# Tests for get_offer_payout_completed_consumer (Docgen)
@patch("services.docgen.tasks.create_avro_consumer")
@patch("services.docgen.tasks.Path.is_file", return_value=True)
@patch("builtins.open")
@patch("services.docgen.tasks.logger")
@patch("services.docgen.tasks.APP_ERRORS_TOTAL")
def test_get_docgen_consumer_init_failure(
    mock_app_errors,
    mock_logger,
    mock_open,
    mock_is_file,
    mock_create_avro_consumer
):
    """Test docgen consumer getter when create_avro_consumer fails."""
    mock_create_avro_consumer.side_effect = KafkaException("Mocked Kafka connection error for docgen")
    docgen_tasks._offer_payout_completed_consumer = None # Reset for test
    docgen_tasks._offer_payout_completed_schema_str = "{\"type\": \"string\"}" # Dummy schema
    mock_open.return_value.read.return_value = docgen_tasks._offer_payout_completed_schema_str

    consumer = docgen_tasks.get_offer_payout_completed_consumer()
    assert consumer is None
    mock_logger.error.assert_called_with(
        "Failed to initialize Kafka consumer for offer.payout.completed", 
        error=ANY, exc_info=True
    )
    mock_app_errors.labels.assert_called_once_with(component="kafka_consumer_init", error_type="offer_payout_completed")

@patch("services.docgen.tasks.Path.is_file", return_value=False)
@patch("services.docgen.tasks.logger")
@patch("services.docgen.tasks.create_avro_consumer")
def test_get_docgen_consumer_schema_file_not_found(
    mock_create_avro_consumer_not_called,
    mock_logger,
    mock_is_file
):
    """Test docgen consumer getter when schema file is not found."""
    docgen_tasks._offer_payout_completed_consumer = None # Reset for test
    docgen_tasks._offer_payout_completed_schema_str = None

    with pytest.raises(FileNotFoundError):
        docgen_tasks.get_offer_payout_completed_consumer()
    
    mock_logger.error.assert_called_with(
        "Schema file not found for offer.payout.completed", 
        path=str(docgen_tasks.OFFER_PAYOUT_COMPLETED_SCHEMA_PATH)
    )
    mock_create_avro_consumer_not_called.assert_not_called()

# Tests for consume_payout_completed_events loop (Docgen)
# Similar to payouts consumer: Kafka error, EOF, loop stop

@patch("services.docgen.tasks.generate_receipt_pdf.delay")
@patch("services.docgen.tasks.get_offer_payout_completed_consumer")
@patch("services.docgen.tasks.APP_ERRORS_TOTAL") 
@patch("services.docgen.tasks.logger")
@patch("time.sleep") 
def test_docgen_consumer_kafka_error(
    mock_sleep,
    mock_logger,
    mock_app_errors_metric,
    mock_get_consumer,
    mock_generate_receipt_delay # To assert it's not called
):
    mock_consumer_instance = MagicMock()
    kafka_error_msg = MagicMock(spec=KafkaError)
    kafka_error_msg.code.return_value = KafkaError._FAIL
    # Simulate poll returning error message once, then None to stop loop for test
    mock_consumer_instance.poll.side_effect = [kafka_error_msg, None] 
    mock_get_consumer.return_value = mock_consumer_instance

    docgen_tasks._docgen_kafka_consumer_thread_stop_event.set()
    docgen_tasks.consume_payout_completed_events()

    mock_generate_receipt_delay.assert_not_called()
    mock_logger.error.assert_any_call("Kafka consumer error for payout.completed", error=kafka_error_msg, topic=ANY)
    mock_app_errors_metric.labels.assert_any_call(component="kafka_consumer_poll", error_type=str(KafkaError._FAIL))
    mock_sleep.assert_called_once_with(5)
    docgen_tasks._docgen_kafka_consumer_thread_stop_event.clear()

@patch("services.docgen.tasks.generate_receipt_pdf.delay")
@patch("services.docgen.tasks.get_offer_payout_completed_consumer")
@patch("services.docgen.tasks.logger")
def test_docgen_consumer_eof(
    mock_logger,
    mock_get_consumer,
    mock_generate_receipt_delay # To assert it's not called
):
    mock_consumer_instance = MagicMock()
    eof_msg = MagicMock(spec=KafkaError)
    eof_msg.code.return_value = KafkaError._PARTITION_EOF
    eof_msg.topic.return_value = "sometopic"
    eof_msg.partition.return_value = 0
    eof_msg.offset.return_value = 123
    mock_consumer_instance.poll.side_effect = [eof_msg, None] 
    mock_get_consumer.return_value = mock_consumer_instance

    docgen_tasks._docgen_kafka_consumer_thread_stop_event.set()
    docgen_tasks.consume_payout_completed_events()

    mock_generate_receipt_delay.assert_not_called()
    mock_logger.debug.assert_any_call(f'{eof_msg.topic()} [{eof_msg.partition()}] reached end at offset {eof_msg.offset()}')
    mock_logger.error.assert_not_called()
    docgen_tasks._docgen_kafka_consumer_thread_stop_event.clear()

@patch("services.docgen.tasks.get_offer_payout_completed_consumer")
@patch("services.docgen.tasks.logger") 
def test_docgen_consumer_loop_stops_on_event(
    mock_logger,
    mock_get_consumer
):
    mock_consumer_instance = MagicMock()
    mock_consumer_instance.poll.return_value = None 
    mock_consumer_instance.close = MagicMock()
    mock_get_consumer.return_value = mock_consumer_instance

    docgen_tasks._docgen_kafka_consumer_thread_stop_event.clear()
    consumer_loop_thread = threading.Thread(target=docgen_tasks.consume_payout_completed_events)
    consumer_loop_thread.daemon = True
    consumer_loop_thread.start()
    time.sleep(0.1) 
    docgen_tasks._docgen_kafka_consumer_thread_stop_event.set()
    consumer_loop_thread.join(timeout=2)

    assert not consumer_loop_thread.is_alive()
    mock_consumer_instance.close.assert_called_once()
    mock_logger.info.assert_any_call("Kafka consumer loop for payout completed events stopping.")
    docgen_tasks._docgen_kafka_consumer_thread_stop_event.clear() 