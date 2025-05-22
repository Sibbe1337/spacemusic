import os
import uuid
from datetime import datetime
import json
import time # For duration measurement
import threading # For running consumer in a separate thread

import stripe # type: ignore
import pybreaker # type: ignore
import structlog
from sqlmodel import Session, create_engine, select

# Assuming libs is in PYTHONPATH
from libs.py_common.celery_config import create_celery_app
from libs.py_common.kafka import (
    create_avro_consumer, 
    create_avro_producer as common_create_avro_producer, # Renamed to avoid conflict
    delivery_report as kafka_delivery_report, # Rename to avoid conflict if local delivery_report is defined
    KafkaException
)

# Project root for service imports
import sys
from pathlib import Path
PROJECT_ROOT_PAYOUTS_WORKER = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT_PAYOUTS_WORKER))

from services.offers.models import Offer # To fetch offer details
from services.offers.db import DATABASE_URL as OFFERS_DB_URL # Read-only access to offers DB
from .models import LedgerEntry, LedgerEntryCreate # Payouts service's own ledger model

# Import metrics
from .metrics import (
    CELERY_TASKS_PROCESSED_TOTAL,
    CELERY_TASK_DURATION_SECONDS,
    STRIPE_PAYOUTS_TOTAL,
    STRIPE_API_LATENCY_SECONDS,
    WISE_TRANSFERS_TOTAL,
    STRIPE_CIRCUIT_BREAKER_STATE,
    LEDGER_ENTRIES_CREATED_TOTAL,
    APP_ERRORS_TOTAL,
    KAFKA_MESSAGES_CONSUMED_TOTAL, # New metric for consumer
    KAFKA_MESSAGES_PRODUCED_TOTAL, # New metric for producer
    start_worker_metrics_server
)

logger = structlog.get_logger(__name__)

# --- Configuration ---
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
STRIPE_CONNECT_ID = os.getenv("STRIPE_CONNECT_ID") # Destination Stripe Connect account ID
WISE_TOKEN = os.getenv("WISE_TOKEN")
# PAYOUTS_DB_URL for LedgerEntry - assuming a separate DB for payouts ledger for now
PAYOUTS_DB_URL = os.getenv("PAYOUTS_DB_CONNECTION_STRING", "postgresql://user:password@localhost:5434/payouts_db")
KAFKA_PAYOUT_SUCCEEDED_TOPIC = "payout.succeeded"
KAFKA_PAYOUT_REQUESTED_TOPIC = "offer.payout.requested"
KAFKA_CONSUMER_GROUP_ID_PAYOUT_REQUESTED = "payouts-worker-payout-requested-consumer"
KAFKA_PAYOUT_COMPLETED_TOPIC = "offer.payout.completed" # New Topic

# Initialize Stripe API
if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY
else:
    logger.warning("STRIPE_API_KEY not set. Stripe payouts will fail.")

# Celery App
celery_app = create_celery_app("payouts_worker")
celery_app.autodiscover_tasks(packages=["services.payouts"], related_name="worker")

# Database Engines
# For reading Offer data (assuming it's synchronous for Celery tasks)
sync_offers_db_url = OFFERS_DB_URL.replace("+asyncpg", "") if "+asyncpg" in OFFERS_DB_URL else OFFERS_DB_URL
offers_engine = create_engine(sync_offers_db_url, echo=False)
# For writing to Payouts Ledger (also synchronous)
payouts_engine = create_engine(PAYOUTS_DB_URL, echo=False)

# Circuit Breaker for Stripe
stripe_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=180) # Opens after 3 failures in 3 minutes

# Kafka Producer (Placeholder)
# from confluent_kafka import Producer

# --- Kafka Consumer for offer.payout.requested ---
OFFER_PAYOUT_REQUESTED_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "offer_payout_requested.avsc"
_offer_payout_requested_consumer = None
_offer_payout_requested_schema_str = None
_kafka_consumer_thread_stop_event = threading.Event()

def get_offer_payout_requested_consumer():
    global _offer_payout_requested_consumer, _offer_payout_requested_schema_str
    if _offer_payout_requested_consumer is None:
        try:
            if not Path(OFFER_PAYOUT_REQUESTED_SCHEMA_PATH).is_file():
                logger.error("Schema file not found for offer.payout.requested", path=str(OFFER_PAYOUT_REQUESTED_SCHEMA_PATH))
                raise FileNotFoundError(f"Schema file not found: {OFFER_PAYOUT_REQUESTED_SCHEMA_PATH}")
            with open(OFFER_PAYOUT_REQUESTED_SCHEMA_PATH, 'r') as f:
                _offer_payout_requested_schema_str = f.read()
            
            _offer_payout_requested_consumer = create_avro_consumer(
                group_id=KAFKA_CONSUMER_GROUP_ID_PAYOUT_REQUESTED,
                topics=[KAFKA_PAYOUT_REQUESTED_TOPIC],
                value_schema_str=_offer_payout_requested_schema_str
            )
            logger.info("Kafka consumer for offer.payout.requested initialized.", 
                        topic=KAFKA_PAYOUT_REQUESTED_TOPIC, group_id=KAFKA_CONSUMER_GROUP_ID_PAYOUT_REQUESTED)
        except Exception as e:
            logger.error("Failed to initialize Kafka consumer for offer.payout.requested", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(component="kafka_consumer_init", error_type="offer_payout_requested").inc()
            _offer_payout_requested_consumer = None # Ensure it's None on error
    return _offer_payout_requested_consumer

def consume_payout_requests():
    logger.info("Starting Kafka consumer loop for payout requests...")
    consumer = get_offer_payout_requested_consumer()
    if not consumer:
        logger.error("Payout request consumer not available. Exiting consume loop.")
        return

    while not _kafka_consumer_thread_stop_event.is_set():
        try:
            msg = consumer.poll(timeout=1.0) # Poll for messages

            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    # End of partition event
                    logger.debug('%%s [%%d] reached end at offset %%d\n' %
                                 (msg.topic(), msg.partition(), msg.offset()))
                elif msg.error():
                    logger.error("Kafka consumer error", error=msg.error(), topic=msg.topic())
                    APP_ERRORS_TOTAL.labels(component="kafka_consumer_poll", error_type=str(msg.error().code())).inc()
                    # Consider a small sleep on persistent errors to avoid tight loop hammering Kafka
                    time.sleep(5)
                continue

            # Message successfully consumed
            event_data = msg.value() # AvroDeserializer already converted it to a dict
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=msg.topic(), group_id=KAFKA_CONSUMER_GROUP_ID_PAYOUT_REQUESTED, status="success").inc()
            logger.info("Received offer.payout.requested event", topic=msg.topic(), partition=msg.partition(), offset=msg.offset(), key=msg.key(), data_keys=list(event_data.keys()) if event_data else [])

            if event_data and 'offer_id' in event_data:
                offer_id_str = event_data.get('offer_id')
                # Potentially pass other details from event_data to execute_payout if useful
                # e.g., recipient_details, amount_cents, currency_code
                logger.info("Dispatching execute_payout task for offer", offer_id=offer_id_str)
                execute_payout.delay(offer_id_str=offer_id_str)
            else:
                logger.warning("Consumed message missing offer_id or data", raw_message_value=msg.value())
                KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=msg.topic(), group_id=KAFKA_CONSUMER_GROUP_ID_PAYOUT_REQUESTED, status="parse_error").inc()

            consumer.commit(message=msg) # Commit offset for the processed message

        except Exception as e:
            logger.error("Exception in Kafka consumer loop for payout requests", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(component="kafka_consumer_loop", error_type="exception").inc()
            time.sleep(5) # Sleep briefly before retrying poll, to avoid tight loop on unexpected errors

    logger.info("Kafka consumer loop for payout requests stopping.")
    if consumer:
        consumer.close()

def start_kafka_listener_thread():
    """Starts the Kafka consumer loop in a daemon thread."""
    if not get_offer_payout_requested_consumer(): # Attempt to initialize if not already
        logger.error("Cannot start Kafka listener: Consumer initialization failed.")
        return

    logger.info("Starting Kafka listener thread for payout requests.")
    _kafka_consumer_thread_stop_event.clear()
    consumer_thread = threading.Thread(target=consume_payout_requests, daemon=True)
    consumer_thread.name = "PayoutsKafkaConsumerThread"
    consumer_thread.start()
    return consumer_thread

def stop_kafka_listener_thread():
    """Signals the Kafka consumer thread to stop."""
    logger.info("Signaling Kafka listener thread for payout requests to stop...")
    _kafka_consumer_thread_stop_event.set()

# --- Kafka Producer for offer.payout.completed ---
OFFER_PAYOUT_COMPLETED_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "offer_payout_completed.avsc"
_offer_payout_completed_producer = None
_offer_payout_completed_schema_str = None

def get_offer_payout_completed_producer():
    global _offer_payout_completed_producer, _offer_payout_completed_schema_str
    if _offer_payout_completed_producer is None:
        try:
            if not Path(OFFER_PAYOUT_COMPLETED_SCHEMA_PATH).is_file():
                logger.error("Schema file not found for offer.payout.completed", path=str(OFFER_PAYOUT_COMPLETED_SCHEMA_PATH))
                raise FileNotFoundError(f"Schema file not found: {OFFER_PAYOUT_COMPLETED_SCHEMA_PATH}")
            with open(OFFER_PAYOUT_COMPLETED_SCHEMA_PATH, 'r') as f:
                _offer_payout_completed_schema_str = f.read()
            
            _offer_payout_completed_producer = common_create_avro_producer( # Use renamed import
                value_schema_str=_offer_payout_completed_schema_str
            )
            logger.info("Kafka producer for offer.payout.completed initialized.", 
                        topic=KAFKA_PAYOUT_COMPLETED_TOPIC)
        except Exception as e:
            logger.error("Failed to initialize Kafka producer for offer.payout.completed", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(component="kafka_producer_init", error_type="offer_payout_completed").inc()
            _offer_payout_completed_producer = None 
    return _offer_payout_completed_producer

# --- Helper Functions with Metrics ---
def _create_ledger_entry(session: Session, offer_id: uuid.UUID, amount_cents: int, currency: str, debit: str, credit: str, ref_id: str, desc: str, type: str="payout", payout_method: str="unknown"):
    entry = LedgerEntryCreate(
        offer_id=offer_id,
        debit_account=debit,
        credit_account=credit,
        amount_cents=amount_cents,
        currency_code=currency,
        description=desc,
        transaction_type=type,
        reference_id=ref_id
    )
    db_entry = LedgerEntry.model_validate(entry)
    session.add(db_entry)
    session.commit()
    session.refresh(db_entry)
    LEDGER_ENTRIES_CREATED_TOTAL.labels(transaction_type=type, payout_method=payout_method).inc()
    logger.info("Ledger entry created", entry_id=db_entry.id, offer_id=offer_id, type=type)

@stripe_breaker
def _call_stripe_payout(offer: Offer, net_amount_cents: int, currency: str) -> str:
    """Calls Stripe Payout API. Wrapped by circuit breaker."""
    if not STRIPE_API_KEY or not STRIPE_CONNECT_ID:
        APP_ERRORS_TOTAL.labels(component="stripe_call", error_type="config_missing").inc()
        STRIPE_PAYOUTS_TOTAL.labels(outcome="config_error").inc()
        raise ValueError("Stripe API Key or Connect ID not configured.")
    
    api_call_label = "transfer_create"
    start_time = time.monotonic()
    STRIPE_CIRCUIT_BREAKER_STATE.set(0 if stripe_breaker.closed else (1 if stripe_breaker.opened else 0.5))
    try:
        transfer = stripe.Transfer.create(
            amount=net_amount_cents,
            currency=currency.lower(), # Stripe uses lowercase currency codes
            destination=STRIPE_CONNECT_ID, # The ID of the connected account to pay out to
            description=f"Payout for offer: {offer.title} (ID: {offer.id})",
            metadata={"offer_id": str(offer.id), "creator_id": str(offer.creator_id)}
        )
        STRIPE_PAYOUTS_TOTAL.labels(outcome="success").inc()
        logger.info("Stripe transfer successful", transfer_id=transfer.id, offer_id=offer.id)
        return transfer.id
    except stripe.error.StripeError as e:
        logger.error("Stripe API error during transfer", error=str(e), offer_id=offer.id)
        error_outcome = f"api_error_{e.code if e.code else 'unknown'}"
        STRIPE_PAYOUTS_TOTAL.labels(outcome=error_outcome).inc()
        APP_ERRORS_TOTAL.labels(component="stripe_call", error_type=error_outcome).inc()
        raise # Re-raise to be caught by circuit breaker and task logic
    finally:
        STRIPE_API_LATENCY_SECONDS.labels(api_call=api_call_label).observe(time.monotonic() - start_time)
        STRIPE_CIRCUIT_BREAKER_STATE.set(0 if stripe_breaker.closed else (1 if stripe_breaker.opened else 0.5))

def _call_wise_transfer(offer: Offer, net_amount_cents: int, currency: str) -> str:
    """Placeholder for calling Wise Transfer API."""
    if not WISE_TOKEN:
        APP_ERRORS_TOTAL.labels(component="wise_call", error_type="config_missing").inc()
        WISE_TRANSFERS_TOTAL.labels(outcome="config_error").inc()
        raise ValueError("Wise token not configured.")
    
    logger.info("Attempting Wise transfer as fallback", offer_id=offer.id, amount=net_amount_cents, currency=currency)
    # Actual Wise API call implementation needed here
    # This would involve creating a quote, a recipient, and then a transfer.
    # Example steps (conceptual):
    # 1. Get Wise profile ID
    # 2. Create a quote for the transfer (source currency, target currency, amount)
    # 3. Ensure recipient account exists or create one (requires bank details, email)
    # 4. Fund the transfer (e.g., from Wise balance or linked bank account)
    # 5. Confirm transfer
    time.sleep(0.5) # Simulate API call latency
    wise_transfer_id = f"wise_tx_{uuid.uuid4()}" # Placeholder
    WISE_TRANSFERS_TOTAL.labels(outcome="success").inc() # Assume success for placeholder
    logger.info("Wise transfer successful (placeholder)", transfer_id=wise_transfer_id, offer_id=offer.id)
    return wise_transfer_id

# --- Celery Task with Metrics ---
@celery_app.task(name="services.payouts.worker.execute_payout", bind=True, max_retries=3, default_retry_delay=60)
def execute_payout(self, offer_id_str: str):
    task_start_time = time.monotonic()
    task_name = self.name
    logger.info("Starting payout execution for offer", offer_id=str(offer_id_str), task_name=task_name)
    offer_id = uuid.UUID(offer_id_str)
    
    # Variables to store results for Kafka event
    payout_status_for_event = "FAILURE" # Default to FAILURE
    payout_method_for_event = "unknown"
    payout_reference_id_for_event = None
    failure_reason_for_event = "Unknown error before payout attempt"
    net_amount_cents_for_event = 0 # Will be updated if offer is found
    currency_for_event = "EUR" # Default, will be updated
    original_offer_status = "UNKNOWN" # Store original status before payout attempt

    try:
        with Session(offers_engine) as offers_session:
            offer = offers_session.exec(select(Offer).where(Offer.id == offer_id)).first()
        
        if not offer:
            logger.error("Offer not found for payout", offer_id=str(offer_id))
            APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="offer_not_found").inc()
            failure_reason_for_event = "Offer not found"
            # Still produce event even if offer not found, to signal attempt
            return {"status": "error", "message": "Offer not found"} # Celery task result

        original_offer_status = offer.status
        net_amount_cents_for_event = offer.price_median_eur if offer.price_median_eur is not None else 0
        # currency_for_event can be taken from offer if it has currency_code field

        if offer.status == "PAID_OUT": 
            logger.info("Offer already paid out. Skipping actual payout logic.", offer_id=str(offer_id), status=offer.status)
            payout_status_for_event = "SUCCESS" # Considered a success in terms of this specific task execution
            payout_method_for_event = offer.last_payout_method or "unknown" # Assuming you might store this
            payout_reference_id_for_event = offer.last_payout_reference or None
            failure_reason_for_event = None
            return {"status": "skipped", "message": "Offer already paid out"}

        if offer.price_median_eur is None:
            logger.error("Offer median price not available for payout.", offer_id=str(offer_id))
            APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="no_median_price").inc()
            failure_reason_for_event = "Median price not available"
            return {"status": "error", "message": "Median price not available"}
        
        net_amount_cents = offer.price_median_eur
        payout_currency = "EUR" 

        with Session(payouts_engine) as ledger_session: 
            try:
                payout_reference_id_for_event = _call_stripe_payout(offer, net_amount_cents, payout_currency)
                payout_method_for_event = "stripe"
                logger.info("Stripe payout processing initiated", offer_id=offer.id, stripe_ref=payout_reference_id_for_event)
                payout_status_for_event = "SUCCESS"
                failure_reason_for_event = None

            except pybreaker.CircuitBreakerError as cbe:
                logger.warning("Stripe circuit breaker is open. Attempting Wise fallback.", offer_id=offer.id, error=str(cbe))
                STRIPE_CIRCUIT_BREAKER_STATE.set(1) 
                APP_ERRORS_TOTAL.labels(component="stripe_call", error_type="circuit_breaker_open").inc()
                payout_method_for_event = "wise_attempt_after_stripe_cb_open"
                try:
                    payout_reference_id_for_event = _call_wise_transfer(offer, net_amount_cents, payout_currency)
                    payout_method_for_event = "wise"
                    logger.info("Wise payout processing initiated", offer_id=offer.id, wise_ref=payout_reference_id_for_event)
                    payout_status_for_event = "SUCCESS"
                    failure_reason_for_event = None
                except Exception as wise_e:
                    logger.error("Wise transfer also failed after Stripe failure.", offer_id=offer.id, error=str(wise_e))
                    APP_ERRORS_TOTAL.labels(component="wise_call", error_type="fallback_failure").inc()
                    WISE_TRANSFERS_TOTAL.labels(outcome="failure").inc()
                    failure_reason_for_event = f"Wise fallback failed after Stripe CB open: {str(wise_e)}"
                    # Return error for Celery task, Kafka event will reflect this in finally
                    return {"status": "error", "message": failure_reason_for_event}
            
            except stripe.error.StripeError as se:
                logger.error("Stripe API error. Attempting Wise.", offer_id=offer.id, error=str(se))
                payout_method_for_event = "wise_attempt_after_stripe_error"
                try:
                    payout_reference_id_for_event = _call_wise_transfer(offer, net_amount_cents, payout_currency)
                    payout_method_for_event = "wise"
                    payout_status_for_event = "SUCCESS"
                    failure_reason_for_event = None
                except Exception as wise_e:
                    logger.error("Wise transfer also failed after Stripe API error.", offer_id=offer.id, error=str(wise_e))
                    APP_ERRORS_TOTAL.labels(component="wise_call", error_type="fallback_failure_after_stripe_error").inc()
                    WISE_TRANSFERS_TOTAL.labels(outcome="failure").inc()
                    failure_reason_for_event = f"Wise fallback failed after Stripe API error: {str(wise_e)}"
                    return {"status": "error", "message": failure_reason_for_event}
            
            except ValueError as ve: 
                logger.critical("Configuration error for payout provider.", offer_id=offer.id, error=str(ve))
                APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="config_error").inc()
                failure_reason_for_event = f"Configuration error: {str(ve)}"
                return {"status": "error", "message": failure_reason_for_event}
            
            except Exception as e: 
                logger.error("Unexpected error during payout attempt.", offer_id=offer.id, error=str(e), exc_info=True)
                APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="unhandled_payout_attempt_exception").inc()
                failure_reason_for_event = f"Unexpected payout error: {str(e)}"
                try:
                    self.retry(exc=e) 
                except self.MaxRetriesExceededError:
                    logger.error("Max retries exceeded for payout task.", offer_id=str(offer_id))
                    APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="max_retries_exceeded").inc()
                    failure_reason_for_event = f"Max retries exceeded: {str(e)}"
                # For retry cases, the Kafka event will be sent by the final attempt. For immediate unhandled, it's sent in finally.
                return {"status": "error", "message": failure_reason_for_event} # Return for Celery, Kafka event in finally

            if payout_status_for_event == "SUCCESS" and payout_reference_id_for_event and payout_method_for_event != "unknown":
                desc = f"{payout_method_for_event.capitalize()} payout for offer {offer.id}"
                _create_ledger_entry(ledger_session, offer.id, net_amount_cents, payout_currency, 
                                     "cash_on_hand_eur", f"{payout_method_for_event}_payouts_payable_eur", 
                                     payout_reference_id_for_event, desc, type=f"{payout_method_for_event}_payout", payout_method=payout_method_for_event)
                
                with Session(offers_engine) as offers_session_update:
                    offer_to_update = offers_session_update.get(Offer, offer_id)
                    if offer_to_update:
                        offer_to_update.status = "PAID_OUT" 
                        offer_to_update.updated_at = datetime.utcnow()
                        # Store last payout method and ref if your Offer model supports it
                        # offer_to_update.last_payout_method = payout_method_for_event
                        # offer_to_update.last_payout_reference = payout_reference_id_for_event
                        offers_session_update.add(offer_to_update)
                        offers_session_update.commit()
                        logger.info("Offer status updated to PAID_OUT", offer_id=offer_id)
                    else:
                        logger.error("Offer not found for status update after payout.", offer_id=offer_id)
                        failure_reason_for_event = "Offer not found during final status update after successful payout."
                        payout_status_for_event = "FAILURE" # This is a critical data integrity issue
                        APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="offer_disappeared_post_payout").inc()

                return {"status": "success", "offer_id": str(offer.id), "method": payout_method_for_event, "reference": payout_reference_id_for_event}
            else:
                # If payout_status_for_event is not SUCCESS but no specific exception was returned from above blocks.
                if failure_reason_for_event == "Unknown error before payout attempt": # Ensure a more specific reason if possible
                    failure_reason_for_event = "Payout attempt concluded with no success and no specific error captured."
                logger.error(failure_reason_for_event, offer_id=offer_id, method=payout_method_for_event, ref=payout_reference_id_for_event)
                APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="no_provider_success_final").inc()
                return {"status": "error", "message": failure_reason_for_event}

    except Exception as e: # Broad exception for issues like DB connection for initial offer fetch
        logger.error("Outer unhandled exception in execute_payout task", error=str(e), offer_id=str(offer_id), exc_info=True)
        APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="outer_unhandled_task_exception").inc()
        failure_reason_for_event = f"Outer unhandled exception: {str(e)}"
        # Try to retry if it's a Celery task context
        if hasattr(self, 'retry'):
            try: self.retry(exc=e)
            except self.MaxRetriesExceededError: logger.error("Max retries exceeded (outer loop)", offer_id=str(offer_id))
        return {"status": "error", "message": failure_reason_for_event}
    finally:
        # Produce Kafka event for offer.payout.completed REGARDLESS OF OUTCOME (unless offer was not found initially)
        if original_offer_status != "UNKNOWN": # Means offer was found initially
            producer = get_offer_payout_completed_producer()
            if producer and _offer_payout_completed_schema_str:
                event_payload_completed = {
                    "event_id": str(uuid.uuid4()),
                    "offer_id": offer_id_str,
                    "payout_method": payout_method_for_event,
                    "reference_id": payout_reference_id_for_event if payout_reference_id_for_event else "N/A",
                    "amount_cents": net_amount_cents_for_event, # Amount attempted/paid
                    "currency_code": currency_for_event,
                    "status": payout_status_for_event, # "SUCCESS" or "FAILURE"
                    "failure_reason": failure_reason_for_event if payout_status_for_event == "FAILURE" else None,
                    "completed_at_micros": int(datetime.utcnow().timestamp() * 1_000_000)
                }
                try:
                    producer.produce(
                        topic=KAFKA_PAYOUT_COMPLETED_TOPIC,
                        key=offer_id_str,
                        value=event_payload_completed,
                        on_delivery=kafka_delivery_report
                    )
                    producer.poll(0) # Non-blocking poll
                    logger.info("offer.payout.completed event produced to Kafka", offer_id=offer_id_str, status=payout_status_for_event)
                    KAFKA_MESSAGES_PRODUCED_TOTAL.labels(topic=KAFKA_PAYOUT_COMPLETED_TOPIC, status="success").inc()
                except KafkaException as e:
                    logger.error("Kafka producer error for offer.payout.completed", error=str(e), offer_id=offer_id_str)
                    APP_ERRORS_TOTAL.labels(component="kafka_producer_payout_completed", error_type="kafka_produce_error").inc()
                    KAFKA_MESSAGES_PRODUCED_TOTAL.labels(topic=KAFKA_PAYOUT_COMPLETED_TOPIC, status="failure").inc()
                except Exception as e:
                    logger.error("Unexpected error during Kafka produce for offer.payout.completed", error=str(e), offer_id=offer_id_str, exc_info=True)
                    APP_ERRORS_TOTAL.labels(component="kafka_producer_payout_completed", error_type="kafka_produce_unexpected").inc()
                    KAFKA_MESSAGES_PRODUCED_TOTAL.labels(topic=KAFKA_PAYOUT_COMPLETED_TOPIC, status="failure").inc()
            else:
                logger.warning("Kafka producer for offer.payout.completed not available. Event not sent.", offer_id=offer_id_str)

        task_duration = time.monotonic() - task_start_time
        metric_status_celery = "success" if payout_status_for_event == "SUCCESS" else "failure"
        if original_offer_status == "PAID_OUT" and payout_status_for_event == "SUCCESS": # If skipped b/c already paid
            metric_status_celery = "skipped_already_paid"
        elif original_offer_status == "UNKNOWN": # If offer was not found for payout
             metric_status_celery = "failure_offer_not_found"
        
        CELERY_TASK_DURATION_SECONDS.labels(task_name=task_name).observe(task_duration)
        CELERY_TASKS_PROCESSED_TOTAL.labels(task_name=task_name, status=metric_status_celery).inc()
        STRIPE_CIRCUIT_BREAKER_STATE.set(0 if stripe_breaker.closed else (1 if stripe_breaker.opened else 0.5))

# Entry point for Celery worker (celery -A services.payouts.worker.celery_app worker ...)
# If also running Kafka consumer in the same process (for simplicity, not ideal for prod):
if __name__ == "__main__" or os.getenv("RUN_KAFKA_LISTENER_IN_PAYOUTS_WORKER"): # Allow explicit start
    # This block will run if the script is executed directly OR if the env var is set
    # (e.g. in the Dockerfile CMD for the worker process if you want consumer & worker together)
    logger.info("Payouts worker script entry point or RUN_KAFKA_LISTENER_IN_PAYOUTS_WORKER is set.")
    
    # Start Prometheus metrics server (if not already started by Celery worker init)
    # This needs to be idempotent or handled carefully if Celery also starts it.
    # For now, assuming start_worker_metrics_server() can be called multiple times safely or is handled.
    if not os.getenv("CELERY_WORKER_NAME"): # Avoid double start if Celery already started it
        try:
            start_worker_metrics_server() 
        except OSError as e:
            logger.error("Payouts worker Prometheus metrics server failed to start on direct run.", error=str(e))

    # Start the Kafka listener thread
    start_kafka_listener_thread()

    # Keep the main thread alive if this script is run directly for the consumer
    # For Celery worker, Celery itself keeps the process alive.
    if __name__ == "__main__" and not os.getenv("CELERY_WORKER_NAME"):
        try:
            while True:
                time.sleep(60)
                logger.debug("Payouts Kafka listener main thread alive...")
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, stopping Kafka listener main thread...")
        finally:
            stop_kafka_listener_thread()
            logger.info("Payouts Kafka listener main thread finished.") 