import os
import uuid
from datetime import datetime
import time # For duration measurement
import structlog

from sqlmodel import Session, create_engine, select # Synchronous for Celery task
from sqlalchemy.orm import selectinload # To eagerly load relationships

# Assuming libs is in PYTHONPATH
from libs.py_common.celery_config import create_celery_app

# Assuming services/offers/models.py contains the Offer model definition
# This creates a dependency. Adjust path if your structure is different or models are in libs.
import sys
from pathlib import Path
PROJECT_ROOT_DOCGEN_TASK = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT_DOCGEN_TASK))

from services.offers.models import Offer, Creator # Make sure Creator is imported if offer.creator is accessed
from services.offers.db import DATABASE_URL as OFFERS_DB_URL # Get sync DB URL for offers
from .renderer import render_termsheet_pdf # The main PDF generation function

# Import metrics
from .metrics import (
    CELERY_TASKS_PROCESSED_TOTAL,
    CELERY_TASK_DURATION_SECONDS,
    APP_ERRORS_TOTAL,
    start_metrics_server
)

logger = structlog.get_logger(__name__)

# Initialize Celery app for docgen service
celery_app = create_celery_app("docgen_worker")
celery_app.autodiscover_tasks(packages=["services.docgen"], related_name="tasks")

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