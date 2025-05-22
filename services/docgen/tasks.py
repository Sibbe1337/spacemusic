import os
import uuid
from datetime import datetime
import time # For duration measurement
import structlog
import threading # For Kafka consumer thread
from pathlib import Path

from sqlmodel import Session, create_engine, select # Synchronous for Celery task
from sqlalchemy.orm import selectinload # To eagerly load relationships

# Assuming libs is in PYTHONPATH
from libs.py_common.celery_config import create_celery_app
from libs.py_common.kafka import (
    create_avro_consumer,
    create_avro_producer as common_create_avro_producer, # Renamed to avoid conflict if local function is named create_avro_producer
    delivery_report as kafka_delivery_report, # Renamed for clarity
    KafkaException
)

# Assuming services/offers/models.py contains the Offer model definition
# This creates a dependency. Adjust path if your structure is different or models are in libs.
import sys
PROJECT_ROOT_DOCGEN_TASK = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT_DOCGEN_TASK))

from services.offers.models import Offer, Creator # Make sure Creator is imported if offer.creator is accessed
from services.offers.db import DATABASE_URL as OFFERS_DB_URL # Get sync DB URL for offers
from .renderer import render_termsheet_pdf, render_receipt_pdf_and_upload # Import new function

# Import metrics
from .metrics import (
    CELERY_TASKS_PROCESSED_TOTAL,
    CELERY_TASK_DURATION_SECONDS,
    APP_ERRORS_TOTAL,
    KAFKA_MESSAGES_CONSUMED_TOTAL, # Added for consumer metrics
    KAFKA_MESSAGES_PRODUCED_TOTAL, # Added for new producer
    start_metrics_server
)

logger = structlog.get_logger(__name__)

# --- Configuration ---
KAFKA_PAYOUT_COMPLETED_TOPIC = "offer.payout.completed"
KAFKA_CONSUMER_GROUP_ID_PAYOUT_COMPLETED = "docgen-worker-payout-completed-consumer"

# Initialize Celery app for docgen service
celery_app = create_celery_app("docgen_worker")
# Assuming tasks might be in this file or other modules within services.docgen
celery_app.autodiscover_tasks(packages=["services.docgen"], related_name="tasks")

# --- Kafka Consumer for offer.payout.completed ---
OFFER_PAYOUT_COMPLETED_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "offer_payout_completed.avsc"
_offer_payout_completed_consumer = None
_offer_payout_completed_schema_str = None
_docgen_kafka_consumer_thread_stop_event = threading.Event()

def get_offer_payout_completed_consumer():
    global _offer_payout_completed_consumer, _offer_payout_completed_schema_str
    if _offer_payout_completed_consumer is None:
        try:
            if not Path(OFFER_PAYOUT_COMPLETED_SCHEMA_PATH).is_file():
                logger.error("Schema file not found for offer.payout.completed", path=str(OFFER_PAYOUT_COMPLETED_SCHEMA_PATH))
                raise FileNotFoundError(f"Schema file not found: {OFFER_PAYOUT_COMPLETED_SCHEMA_PATH}")
            with open(OFFER_PAYOUT_COMPLETED_SCHEMA_PATH, 'r') as f:
                _offer_payout_completed_schema_str = f.read()
            
            _offer_payout_completed_consumer = create_avro_consumer(
                group_id=KAFKA_CONSUMER_GROUP_ID_PAYOUT_COMPLETED,
                topics=[KAFKA_PAYOUT_COMPLETED_TOPIC],
                value_schema_str=_offer_payout_completed_schema_str
            )
            logger.info("Kafka consumer for offer.payout.completed initialized.", 
                        topic=KAFKA_PAYOUT_COMPLETED_TOPIC, group_id=KAFKA_CONSUMER_GROUP_ID_PAYOUT_COMPLETED)
        except Exception as e:
            logger.error("Failed to initialize Kafka consumer for offer.payout.completed", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(component="kafka_consumer_init", error_type="offer_payout_completed").inc()
            _offer_payout_completed_consumer = None 
    return _offer_payout_completed_consumer

# --- Kafka Producer Setup for offer.receipt.generated ---
OFFER_RECEIPT_GENERATED_TOPIC = "offer.receipt.generated"
OFFER_RECEIPT_GENERATED_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "offer_receipt_generated.avsc"
_offer_receipt_generated_producer = None
_offer_receipt_generated_schema_str = None

def get_offer_receipt_generated_producer():
    global _offer_receipt_generated_producer, _offer_receipt_generated_schema_str
    if _offer_receipt_generated_producer is None:
        try:
            if not Path(OFFER_RECEIPT_GENERATED_SCHEMA_PATH).is_file():
                logger.error("Schema file not found for offer.receipt.generated", path=str(OFFER_RECEIPT_GENERATED_SCHEMA_PATH))
                raise FileNotFoundError(f"Schema file not found: {OFFER_RECEIPT_GENERATED_SCHEMA_PATH}")
            with open(OFFER_RECEIPT_GENERATED_SCHEMA_PATH, 'r') as f:
                _offer_receipt_generated_schema_str = f.read()
            _offer_receipt_generated_producer = common_create_avro_producer(
                value_schema_str=_offer_receipt_generated_schema_str
            )
            logger.info("Kafka producer for offer.receipt.generated initialized.", topic=OFFER_RECEIPT_GENERATED_TOPIC)
        except Exception as e:
            logger.error("Failed to initialize Kafka producer for offer.receipt.generated", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(component="kafka_producer_init", error_type="offer_receipt_generated").inc()
            _offer_receipt_generated_producer = None
    return _offer_receipt_generated_producer

@celery_app.task(name="services.docgen.tasks.generate_receipt_pdf") 
def generate_receipt_pdf(offer_id: str, event_data: dict):
    """Generates a PDF receipt for a completed payout, uploads it to S3, and produces Kafka event."""
    task_name = "services.docgen.tasks.generate_receipt_pdf"
    logger.info("Received task to generate payout receipt", offer_id=offer_id, event_keys=list(event_data.keys()), task_name=task_name)
    status_metric_label = "failure_unknown"
    start_time = time.monotonic()
    s3_url_receipt = None
    pdf_hash_receipt = None

    try:
        if not event_data or event_data.get("status") != "SUCCESS":
            logger.warning("generate_receipt_pdf called for non-SUCCESSful or empty event. Skipping.", 
                           offer_id=offer_id, event_status=event_data.get("status"))
            status_metric_label = "skipped_not_success_event"
            return {"status": "skipped", "reason": "Payout event not SUCCESS or event_data missing"}

        s3_url_receipt, pdf_hash_receipt = render_receipt_pdf_and_upload(event_data)

        if s3_url_receipt:
            logger.info("Payout receipt PDF generated and uploaded successfully", offer_id=offer_id, s3_url=s3_url_receipt)
            status_metric_label = "success"
            
            # Produce offer.receipt.generated event
            producer = get_offer_receipt_generated_producer()
            if producer and _offer_receipt_generated_schema_str:
                receipt_event_payload = {
                    "event_id": str(uuid.uuid4()),
                    "offer_id": offer_id,
                    "receipt_url": s3_url_receipt,
                    "receipt_hash_sha256": pdf_hash_receipt,
                    "generated_at_micros": int(datetime.utcnow().timestamp() * 1_000_000)
                }
                try:
                    producer.produce(
                        topic=OFFER_RECEIPT_GENERATED_TOPIC,
                        key=offer_id,
                        value=receipt_event_payload,
                        on_delivery=kafka_delivery_report
                    )
                    producer.poll(0) # Non-blocking poll
                    logger.info("offer.receipt.generated event produced to Kafka", offer_id=offer_id)
                    KAFKA_MESSAGES_PRODUCED_TOTAL.labels(topic=OFFER_RECEIPT_GENERATED_TOPIC, status="success").inc()
                except KafkaException as e:
                    logger.error("Kafka producer error for offer.receipt.generated", error=str(e), offer_id=offer_id)
                    APP_ERRORS_TOTAL.labels(component="kafka_producer_receipt_generated", error_type="kafka_produce_error").inc()
                    KAFKA_MESSAGES_PRODUCED_TOTAL.labels(topic=OFFER_RECEIPT_GENERATED_TOPIC, status="failure").inc()
                except Exception as e:
                    logger.error("Unexpected error producing offer.receipt.generated event", error=str(e), offer_id=offer_id, exc_info=True)
                    APP_ERRORS_TOTAL.labels(component="kafka_producer_receipt_generated", error_type="kafka_produce_unexpected").inc()
                    KAFKA_MESSAGES_PRODUCED_TOTAL.labels(topic=OFFER_RECEIPT_GENERATED_TOPIC, status="failure").inc()
            else:
                logger.warning("Kafka producer for offer.receipt.generated not available. Event not sent.", offer_id=offer_id)
            
            return {"status": "success", "offer_id": offer_id, "receipt_url": s3_url_receipt}
        else:
            logger.error("Failed to generate or upload payout receipt PDF", offer_id=offer_id)
            status_metric_label = "failure_pdf_processing"
            raise Exception(f"Failed to generate/upload receipt for offer {offer_id}") 

    except Exception as e:
        logger.error("Unhandled exception in generate_receipt_pdf task", error=str(e), offer_id=offer_id, exc_info=True)
        APP_ERRORS_TOTAL.labels(error_type="unhandled_receipt_task_exception", component=task_name).inc()
        status_metric_label = "failure_exception"
        raise 
    finally:
        task_duration = time.monotonic() - start_time
        CELERY_TASK_DURATION_SECONDS.labels(task_name=task_name).observe(task_duration)
        CELERY_TASKS_PROCESSED_TOTAL.labels(task_name=task_name, status=status_metric_label).inc()

def consume_payout_completed_events():
    logger.info("Starting Kafka consumer loop for payout completed events...")
    consumer = get_offer_payout_completed_consumer()
    if not consumer:
        logger.error("Payout completed event consumer not available. Exiting consume loop.")
        return

    while not _docgen_kafka_consumer_thread_stop_event.is_set():
        try:
            msg = consumer.poll(timeout=1.0)
            if msg is None: continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.debug(f'{msg.topic()} [{msg.partition()}] reached end at offset {msg.offset()}')
                else:
                    logger.error("Kafka consumer error for payout.completed", error=msg.error(), topic=msg.topic())
                    APP_ERRORS_TOTAL.labels(component="kafka_consumer_poll", error_type=str(msg.error().code())).inc()
                    time.sleep(5)
                continue

            event_data = msg.value()
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=msg.topic(), group_id=KAFKA_CONSUMER_GROUP_ID_PAYOUT_COMPLETED, status="success").inc()
            logger.info("Received offer.payout.completed event", topic=msg.topic(), data_keys=list(event_data.keys()) if event_data else [])

            if event_data and event_data.get("status") == "SUCCESS" and "offer_id" in event_data:
                offer_id_str = event_data.get('offer_id')
                logger.info("Dispatching generate_receipt_pdf task for successful payout", offer_id=offer_id_str)
                # Pass relevant parts of event_data if needed by generate_receipt_pdf
                generate_receipt_pdf.delay(offer_id=offer_id_str, event_data=event_data)
            elif event_data and event_data.get("status") == "FAILURE":
                logger.info("Payout failed for offer, no receipt will be generated.", offer_id=event_data.get('offer_id'), reason=event_data.get('failure_reason'))
            else:
                logger.warning("Consumed payout.completed message missing data, offer_id, or status SUCCESS", raw_value=msg.value())
                KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=msg.topic(), group_id=KAFKA_CONSUMER_GROUP_ID_PAYOUT_COMPLETED, status="parse_or_filter_error").inc()
            
            consumer.commit(message=msg)
        except Exception as e:
            logger.error("Exception in Kafka consumer loop for payout.completed", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(component="kafka_consumer_loop", error_type="docgen_payout_completed_exception").inc()
            time.sleep(5)
    
    logger.info("Kafka consumer loop for payout completed events stopping.")
    if consumer: consumer.close()

def start_docgen_kafka_listener_thread():
    if not get_offer_payout_completed_consumer():
        logger.error("Cannot start Docgen Kafka listener: Consumer initialization failed.")
        return
    logger.info("Starting Kafka listener thread for payout completed events.")
    _docgen_kafka_consumer_thread_stop_event.clear()
    consumer_thread = threading.Thread(target=consume_payout_completed_events, daemon=True)
    consumer_thread.name = "DocgenPayoutCompletedConsumerThread"
    consumer_thread.start()
    return consumer_thread

def stop_docgen_kafka_listener_thread():
    logger.info("Signaling Docgen Kafka listener thread to stop...")
    _docgen_kafka_consumer_thread_stop_event.set()

if os.getenv("CELERY_WORKER_NAME"): # Check if running as a Celery worker
    try:
        start_metrics_server() # Uses default port or DOCGEN_METRICS_PORT
    except OSError as e:
        logger.error("Docgen Prometheus metrics server failed to start.", error=str(e))

# Database Engine for offers (synchronous for Celery task)
sync_offers_db_url = OFFERS_DB_URL.replace("+asyncpg", "") if "+asyncpg" in OFFERS_DB_URL else OFFERS_DB_URL
engine = create_engine(sync_offers_db_url, echo=False) # Set echo=True for debugging SQL

@celery_app.task(name="services.docgen.tasks.generate_termsheet", bind=True)
def generate_termsheet(self, offer_id_str: str):
    task_start_time = time.monotonic()
    task_name = self.name 
    logger.info("Received task to generate termsheet for offer", offer_id=str(offer_id_str), task_name=task_name)
    offer_id = uuid.UUID(offer_id_str)
    status_metric_label = "failure" # Default for metrics

    try:
        with Session(engine) as session:
            # 1. Pull offer row, ensuring creator relationship is loaded for the template
            offer = session.exec(
                select(Offer).options(selectinload(Offer.creator)).where(Offer.id == offer_id)
            ).first()

            if not offer:
                logger.error("Offer not found for termsheet generation", offer_id=str(offer_id))
                APP_ERRORS_TOTAL.labels(error_type="offer_not_found", component="generate_termsheet_task").inc()
                status_metric_label = "failure_offer_not_found"
                return {"status": "error", "message": "Offer not found"}
            
            if offer.status != "OFFER_READY":
                logger.warning("Offer is not in OFFER_READY state. Termsheet generation skipped.", 
                               offer_id=str(offer_id), current_status=offer.status)
                # This check prevents re-processing or processing offers not meant for docgen yet.
                # The subscription to status == 'OFFER_READY' should ideally be handled by the eventing system
                # that triggers this task.
                status_metric_label = "skipped_status_not_ready"
                return {"status": "skipped", "message": f"Offer status is {offer.status}, not OFFER_READY"}

            logger.info("Offer retrieved for termsheet", offer_id=str(offer_id), offer_title=offer.title)

            # 2. Render PDF, upload to S3, get URL and hash
            s3_url, pdf_hash_val = render_termsheet_pdf(offer) # This function is in renderer.py

            if not s3_url or not pdf_hash_val:
                logger.error("Failed to render or upload PDF for termsheet.", offer_id=str(offer_id))
                APP_ERRORS_TOTAL.labels(error_type="pdf_render_upload_failed", component="generate_termsheet_task").inc()
                status_metric_label = "failure_pdf_processing"
                # Optionally update offer status to DOCGEN_FAILED here if needed
                return {"status": "error", "message": "PDF rendering or S3 upload failed"}

            # 3. Update offer row with pdf_url and pdf_hash
            offer.pdf_url = s3_url
            offer.pdf_hash = pdf_hash_val
            offer.status = "TERMSHEET_GENERATED" # Example new status
            offer.updated_at = datetime.utcnow()
            session.add(offer)
            session.commit()
            session.refresh(offer)

            logger.info("Termsheet generated and offer updated successfully.", 
                        offer_id=str(offer_id), pdf_url=s3_url, pdf_hash=pdf_hash_val, new_status=offer.status)
            status_metric_label = "success"
            return {"status": "success", "offer_id": str(offer_id), "pdf_url": s3_url, "pdf_hash": pdf_hash_val}

    except Exception as e:
        logger.error("Unhandled exception in generate_termsheet task", error=str(e), offer_id=str(offer_id), exc_info=True)
        APP_ERRORS_TOTAL.labels(error_type="unhandled_exception", component="generate_termsheet_task").inc()
        status_metric_label = "failure_unhandled_exception"
        raise # Re-raise for Celery to handle retries/failure
    finally:
        task_duration = time.monotonic() - task_start_time
        CELERY_TASK_DURATION_SECONDS.labels(task_name=task_name).observe(task_duration)
        CELERY_TASKS_PROCESSED_TOTAL.labels(task_name=task_name, status=status_metric_label).inc()

# How this task is triggered:
# - If Offer service directly calls this: from services.docgen.tasks import generate_termsheet; generate_termsheet.delay(str(offer.id))
# - If using an event bus (e.g., Kafka consumer in docgen service):
#   A separate consumer process would listen to "offer.ready" topic,
#   then call generate_termsheet.delay(offer_id_from_event).
# The prompt says "subscribed via Celery to offers.status == 'OFFER_READY'".
# This typically implies Celery is not the direct subscriber to a DB status change,
# but rather that another component (e.g., the Offers API after setting status to OFFER_READY,
# or a dedicated event listener) would *then* dispatch this Celery task.
# For a pure Celery solution based on status, one might use Celery Beat to periodically check for such offers,
# or have the Offer service explicitly send a task to the docgen queue upon status change. 

# Logic to start the consumer thread if running as a standalone script or specific env var is set
if __name__ == "__main__" or os.getenv("RUN_KAFKA_LISTENER_IN_DOCGEN_WORKER"):
    logger.info("Docgen worker script entry point or RUN_KAFKA_LISTENER_IN_DOCGEN_WORKER is set.")
    if not os.getenv("CELERY_WORKER_NAME"): 
        try: start_metrics_server()
        except OSError as e: logger.error("Docgen metrics server failed to start on direct run.", error=str(e))
    
    start_docgen_kafka_listener_thread()

    if __name__ == "__main__" and not os.getenv("CELERY_WORKER_NAME"):
        try:
            while True: time.sleep(60); logger.debug("Docgen Kafka listener main thread alive...")
        except KeyboardInterrupt: logger.info("Keyboard interrupt, stopping Docgen Kafka listener main thread...")
        finally: stop_docgen_kafka_listener_thread(); logger.info("Docgen Kafka listener main thread finished.") 