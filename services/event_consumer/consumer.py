# services/event_consumer/consumer.py
import os
import signal
import time
import structlog
from pathlib import Path
import json # Added for potential JSON decoding if not using Avro

# Assuming libs is in PYTHONPATH
from libs.py_common.kafka import create_avro_consumer, create_consumer, KafkaError, KafkaException # Added create_consumer and KafkaException

# Import metrics
from .metrics import (
    KAFKA_MESSAGES_CONSUMED_TOTAL,
    KAFKA_MESSAGE_PROCESSING_DURATION_SECONDS,
    APP_ERRORS_TOTAL,
    start_metrics_server
)

logger = structlog.get_logger(__name__)

# --- Configuration ---
CONSUMER_GROUP_ID = "event-consumer-group-payouts"
PAYOUT_SUCCEEDED_TOPIC = "payout.succeeded"
# Assuming the payout.succeeded schema is defined somewhere, e.g., schema/payout_succeeded.avsc
# For this example, we'll assume it's a simple JSON or string message if no Avro schema is specified.
# If Avro, we would need its schema string.
# PAYOUT_SUCCEEDED_SCHEMA_PATH = Path(__file__).parent.parent.parent / "schema" / "payout_succeeded.avsc"
# _payout_succeeded_schema_str = None

running = True

def shutdown_handler(signum, frame):
    global running
    logger.info("Shutdown signal received, stopping consumer...")
    running = False

def load_payout_succeeded_schema():
    # global _payout_succeeded_schema_str
    # try:
    #     with open(PAYOUT_SUCCEEDED_SCHEMA_PATH, 'r') as f:
    #         _payout_succeeded_schema_str = f.read()
    #     logger.info("payout.succeeded Avro schema loaded.")
    # except FileNotFoundError:
    #     logger.error("payout_succeeded.avsc not found. Consumer might fail on Avro messages.", path=str(PAYOUT_SUCCEEDED_SCHEMA_PATH))
    # except Exception as e:
    #     logger.error("Failed to load payout_succeeded.avsc", error=str(e))
    pass # Not using Avro for this consumer as per simpler initial requirement

def main():
    logger.info("Starting event consumer for payout.succeeded topic.")
    
    try:
        start_metrics_server() # Start Prometheus metrics server
    except OSError as e:
        logger.error("Event consumer metrics server failed to start. Port likely in use.", error=str(e))

    # load_payout_succeeded_schema()
    # if not _payout_succeeded_schema_str: # If Avro schema is strictly required
    #     logger.critical("Cannot start consumer without payout.succeeded Avro schema.")
    #     return

    # consumer = create_avro_consumer(
    #     group_id=CONSUMER_GROUP_ID, 
    #     topics=[PAYOUT_SUCCEEDED_TOPIC],
    #     value_schema_str=_payout_succeeded_schema_str
    # )
    # Using non-Avro consumer as schema isn't specified to be Avro for this example yet
    consumer = None
    try:
        consumer = create_avro_consumer( # Assuming payout.succeeded *is* Avro and schema exists
            group_id=CONSUMER_GROUP_ID,
            topics=[PAYOUT_SUCCEEDED_TOPIC],
            value_schema_str=Path(Path(__file__).parent.parent.parent / "schema" / "payout_succeeded.avsc").read_text() 
            # This line above is problematic if schema/payout_succeeded.avsc doesn't exist.
            # Fallback to simple consumer if schema is an issue:
            # consumer = create_consumer(CONSUMER_GROUP_ID, [PAYOUT_SUCCEEDED_TOPIC])
        )
    except FileNotFoundError:
        logger.error(f"Schema file for {PAYOUT_SUCCEEDED_TOPIC} not found. Falling back to non-Avro consumer.")
        APP_ERRORS_TOTAL.labels(error_type="kafka_consumer_init", component="main_consumer_setup").inc()
        consumer = create_consumer(CONSUMER_GROUP_ID, [PAYOUT_SUCCEEDED_TOPIC]) # Fallback
    except Exception as e:
        logger.error(f"Failed to create Avro consumer: {e}. Falling back to non-Avro consumer.")
        APP_ERRORS_TOTAL.labels(error_type="kafka_consumer_init", component="main_consumer_setup").inc()
        consumer = create_consumer(CONSUMER_GROUP_ID, [PAYOUT_SUCCEEDED_TOPIC]) # Fallback

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("Event consumer started. Waiting for messages...", topics=PAYOUT_SUCCEEDED_TOPIC)
    try:
        while running:
            msg = consumer.poll(timeout=1.0) # Poll for messages
            if msg is None:
                continue
            
            topic = msg.topic()
            start_time = time.monotonic()
            metric_status = "success"

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    # End of partition event
                    logger.debug(f"Reached end of partition for {topic} [{msg.partition()}]")
                elif msg.error():
                    logger.error(f"Kafka consume error for {topic}", error=msg.error())
                    APP_ERRORS_TOTAL.labels(error_type="kafka_consume_error", component="consumer_loop").inc()
                    metric_status = "error_kafka"
                KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=topic, consumer_group=CONSUMER_GROUP_ID, status=metric_status).inc()
                continue # Continue to next message or poll interval

            try:
                # Process the message (value() might be bytes or already deserialized object by AvroConsumer)
                event_data = msg.value() # If AvroConsumer, this is a dict. If Consumer, bytes.
                if isinstance(event_data, bytes): # Basic consumer might give bytes
                    event_data = json.loads(event_data.decode('utf-8'))
                
                logger.info("Received payout.succeeded event", 
                            offer_id=event_data.get("offer_id"), 
                            payout_method=event_data.get("payout_method"), 
                            reference_id=event_data.get("reference_id"),
                            amount_cents=event_data.get("amount_cents")
                )
                # Add any specific processing logic here if needed beyond logging

            except json.JSONDecodeError as e:
                logger.error("Failed to decode JSON message from Kafka", error=str(e), topic=topic)
                APP_ERRORS_TOTAL.labels(error_type="json_decode_error", component="message_processing").inc()
                metric_status = "error_deserialize"
            except Exception as e:
                logger.error("Error processing message from Kafka", error=str(e), topic=topic, exc_info=True)
                APP_ERRORS_TOTAL.labels(error_type="processing_error", component="message_processing").inc()
                metric_status = "error_processing"
            finally:
                consumer.commit(message=msg) # Commit offset for the processed message
                processing_duration = time.monotonic() - start_time
                KAFKA_MESSAGE_PROCESSING_DURATION_SECONDS.labels(topic=topic, consumer_group=CONSUMER_GROUP_ID).observe(processing_duration)
                KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=topic, consumer_group=CONSUMER_GROUP_ID, status=metric_status).inc()

    except KafkaException as ke:
        logger.critical("Critical KafkaException in consumer loop", error=str(ke), exc_info=True)
        APP_ERRORS_TOTAL.labels(error_type="kafka_critical_exception", component="consumer_loop").inc()
    except Exception as e:
        logger.critical("Unhandled exception in consumer loop", error=str(e), exc_info=True)
        APP_ERRORS_TOTAL.labels(error_type="unhandled_exception", component="consumer_loop").inc()
    finally:
        if consumer:
            logger.info("Closing Kafka consumer.")
            consumer.close()

if __name__ == "__main__":
    # Load .env file if it exists (for local development)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env") 
    # Or load from project root: load_dotenv(PROJECT_ROOT_PAYOUTS_WORKER.parent / ".env")
    
    # Configure structlog if not already configured by another entry point
    # Basic structlog setup if not done globally
    if not structlog.is_configured():
        structlog.configure(
            processors=[
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.dev.ConsoleRenderer(), # Or JSONRenderer for production
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    main() 