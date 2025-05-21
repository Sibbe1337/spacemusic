import os
import uuid
from datetime import datetime
import json
import time # For duration measurement

import stripe # type: ignore
import pybreaker # type: ignore
import structlog
from sqlmodel import Session, create_engine, select

# Assuming libs is in PYTHONPATH
from libs.py_common.celery_config import create_celery_app

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
    metric_status = "failure_unknown" 

    try:
        with Session(offers_engine) as offers_session:
            offer = offers_session.exec(select(Offer).where(Offer.id == offer_id)).first()
        
        if not offer:
            logger.error("Offer not found for payout", offer_id=str(offer_id))
            APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="offer_not_found").inc()
            metric_status = "failure_offer_not_found"
            return {"status": "error", "message": "Offer not found"}

        if offer.status == "PAID_OUT": # Or similar terminal success status
            logger.info("Offer already paid out. Skipping.", offer_id=str(offer_id), status=offer.status)
            metric_status = "skipped_already_paid"
            return {"status": "skipped", "message": "Offer already paid out"}

        # 2. Calculate net_amount (e.g., median_eur, assuming it's in cents)
        if offer.price_median_eur is None:
            logger.error("Offer median price not available for payout.", offer_id=str(offer_id))
            APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="no_median_price").inc()
            metric_status = "failure_no_price"
            return {"status": "error", "message": "Median price not available"}
        net_amount_cents = offer.price_median_eur
        payout_currency = "EUR" # Assuming EUR, adjust if dynamic from offer

        payout_reference_id = None
        payout_method = None

        with Session(payouts_engine) as ledger_session: # Session for our ledger
            try:
                # 3. Call Stripe Payout (Transfer to Connected Account)
                payout_reference_id = _call_stripe_payout(offer, net_amount_cents, payout_currency)
                payout_method = "stripe"
                logger.info("Stripe payout processing initiated", offer_id=offer.id, stripe_ref=payout_reference_id)

            except pybreaker.CircuitBreakerError as cbe:
                logger.warning("Stripe circuit breaker is open. Attempting Wise fallback.", offer_id=offer.id, error=str(cbe))
                STRIPE_CIRCUIT_BREAKER_STATE.set(1) # Mark as open for gauge
                APP_ERRORS_TOTAL.labels(component="stripe_call", error_type="circuit_breaker_open").inc()
                try:
                    payout_reference_id = _call_wise_transfer(offer, net_amount_cents, payout_currency)
                    payout_method = "wise"
                    logger.info("Wise payout processing initiated", offer_id=offer.id, wise_ref=payout_reference_id)
                except Exception as wise_e:
                    logger.error("Wise transfer also failed after Stripe failure.", offer_id=offer.id, error=str(wise_e))
                    APP_ERRORS_TOTAL.labels(component="wise_call", error_type="fallback_failure").inc()
                    WISE_TRANSFERS_TOTAL.labels(outcome="failure").inc()
                    metric_status = "failure_wise_fallback"
                    # self.update_state(state='FAILURE', meta=f'Wise fallback failed: {wise_e}')
                    # Not re-raising here to ensure finally block runs for Celery metrics
                    return {"status": "error", "message": f"Wise fallback failed: {wise_e}"}
            
            except stripe.error.StripeError as se:
                logger.error("Stripe API error (not caught by CB or CB closed). Attempting Wise.", offer_id=offer.id, error=str(se))
                try:
                    payout_reference_id = _call_wise_transfer(offer, net_amount_cents, payout_currency)
                    payout_method = "wise"
                except Exception as wise_e:
                    logger.error("Wise transfer also failed after Stripe API error.", offer_id=offer.id, error=str(wise_e))
                    APP_ERRORS_TOTAL.labels(component="wise_call", error_type="fallback_failure_after_stripe_error").inc()
                    WISE_TRANSFERS_TOTAL.labels(outcome="failure").inc()
                    metric_status = "failure_wise_after_stripe_error"
                    return {"status": "error", "message": f"Wise fallback failed: {wise_e}"}
            
            except ValueError as ve: # For config errors like missing API keys
                logger.critical("Configuration error for payout provider.", offer_id=offer.id, error=str(ve))
                APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="config_error").inc()
                metric_status = "failure_config_error"
                # This is likely a non-retryable error from Celery task perspective
                # self.update_state(state='FAILURE', meta=f'Config error: {ve}')
                return {"status": "error", "message": f"Configuration error: {ve}"}
            
            except Exception as e: # Catch-all for other unexpected errors during payout attempts
                logger.error("Unexpected error during payout attempt.", offer_id=offer.id, error=str(e), exc_info=True)
                APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="unhandled_task_exception").inc()
                # Potentially retry depending on the error type
                try:
                    self.retry(exc=e) # Use Celery's retry mechanism
                except self.MaxRetriesExceededError:
                    logger.error("Max retries exceeded for payout task.", offer_id=str(offer_id))
                    APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="max_retries_exceeded").inc()
                metric_status = "failure_max_retries_exceeded"
                return {"status": "error", "message": f"Unexpected payout error after retries: {e}"}

            if payout_reference_id and payout_method:
                # 4. On success, insert ledger entries (debit cash, credit payouts_payable)
                desc = f"{payout_method.capitalize()} payout for offer {offer.id}"
                _create_ledger_entry(ledger_session, offer.id, net_amount_cents, payout_currency, 
                                     "cash_on_hand_eur", f"{payout_method}_payouts_payable_eur", 
                                     payout_reference_id, desc, type=f"{payout_method}_payout", payout_method=payout_method)
                
                # Mark offer as paid in offers_db
                with Session(offers_engine) as offers_session_update:
                    offer_to_update = offers_session_update.get(Offer, offer_id)
                    if offer_to_update:
                        offer_to_update.status = "PAID_OUT" # Example new status
                        offer_to_update.updated_at = datetime.utcnow()
                        offers_session_update.add(offer_to_update)
                        offers_session_update.commit()
                        logger.info("Offer status updated to PAID_OUT", offer_id=offer_id)
                    else:
                        logger.error("Offer not found for status update after payout.", offer_id=offer_id)
                        # This is problematic, ledger entries made but offer status not updated.
                        # Needs careful handling/reconciliation strategy.

                # 5. Publish Kafka event payout.succeeded
                event_payload = {
                    "offer_id": str(offer.id),
                    "payout_method": payout_method,
                    "reference_id": payout_reference_id,
                    "amount_cents": net_amount_cents,
                    "currency": payout_currency,
                    "timestamp": datetime.utcnow().isoformat()
                }
                # kafka_producer.produce(KAFKA_PAYOUT_SUCCEEDED_TOPIC, key=str(offer.id), value=json.dumps(event_payload))
                # kafka_producer.flush()
                logger.info("Kafka event payout.succeeded produced (placeholder)", topic=KAFKA_PAYOUT_SUCCEEDED_TOPIC, payload=event_payload)

                metric_status = "success"
                return {"status": "success", "offer_id": str(offer_id), "method": payout_method, "reference": payout_reference_id}
            else:
                # Should have been caught by specific exceptions, but as a safeguard
                logger.error("Payout attempt concluded with no reference ID or method.", offer_id=offer_id)
                APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="no_provider_success").inc()
                metric_status = "failure_no_provider_success"
                return {"status": "error", "message": "Payout failed with no clear provider success"}

    except Exception as e:
        logger.error("Unhandled exception in execute_payout task", error=str(e), offer_id=str(offer_id), exc_info=True)
        APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="unhandled_task_exception").inc()
        metric_status = "failure_unhandled_task_exception"
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for payout task.", offer_id=str(offer_id))
            APP_ERRORS_TOTAL.labels(component="execute_payout", error_type="max_retries_exceeded").inc()
        # Return structure for unhandled/retried cases to avoid Celery's default behavior if not desired
        return {"status": "error", "message": f"Unhandled exception: {str(e)}"} 
    finally:
        task_duration = time.monotonic() - task_start_time
        CELERY_TASK_DURATION_SECONDS.labels(task_name=task_name).observe(task_duration)
        CELERY_TASKS_PROCESSED_TOTAL.labels(task_name=task_name, status=metric_status).inc()
        # Update circuit breaker state metric one last time for this task execution path
        STRIPE_CIRCUIT_BREAKER_STATE.set(0 if stripe_breaker.closed else (1 if stripe_breaker.opened else 0.5))

# Celery worker command: celery -A services.payouts.worker.celery_app worker -l INFO -Q payouts 