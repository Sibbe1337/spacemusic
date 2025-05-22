import os
import uuid
import joblib
import pandas as pd
import yaml
import redis
import json
from datetime import timedelta
import time

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from sqlmodel import Session, create_engine, select # Using synchronous session for Celery task
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

# Assuming libs is in PYTHONPATH
from libs.py_common.celery_config import create_celery_app
from libs.py_common.kafka import create_avro_producer, delivery_report, KafkaException # Added KafkaException
# Assuming services/offers/models.py contains the Offer model definition
# This creates a dependency. Ideally, models could be in libs if shared, or use an API.
# For now, direct import path relative to a common root for services.
import sys
from pathlib import Path
# Add project root to sys.path to allow absolute-like imports for services
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))
from services.offers.models import Offer # Now this should work
from services.offers.db import DATABASE_URL as OFFERS_DB_URL # Get sync DB URL for offers
from libs.analytics.feature_pipeline import process_data_for_features # Adjusted based on typical use
# Kafka producer - placeholder. Use a proper Kafka client library like confluent-kafka-python
# from confluent_kafka import Producer

# Import metrics
from .metrics import (
    CELERY_TASKS_PROCESSED_TOTAL,
    CELERY_TASK_DURATION_SECONDS,
    SPOTIFY_API_CALLS_TOTAL,
    SPOTIFY_API_LATENCY_SECONDS,
    CACHE_HITS_TOTAL,
    CACHE_MISSES_TOTAL,
    MODEL_PREDICTIONS_TOTAL,
    APP_ERRORS_TOTAL,
    start_metrics_server
)

logger = structlog.get_logger(__name__)

# Initialize Celery app
celery_app = create_celery_app("valuation_worker")
celery_app.autodiscover_tasks(packages=["services.valuation"], related_name="worker")

# Start Prometheus metrics server for this worker
# This should ideally be called only once per worker process.
# If running multiple Celery worker processes, consider a multi-process friendly way
# or ensure each worker listens on a different port if scraped individually.
if os.getenv("CELERY_WORKER_NAME"): # Crude way to check if in Celery worker vs main module run
    try:
        start_metrics_server() # Uses default port 8001 or VALUATION_METRICS_PORT env var
    except OSError as e:
        logger.error("Failed to start Prometheus metrics server. Port likely in use.", error=str(e))
        # If this happens, metrics won't be available from this worker instance.

# Database Engine for offers (synchronous for Celery task)
# Construct a synchronous URL if OFFERS_DB_URL is async
sync_offers_db_url = OFFERS_DB_URL.replace("+asyncpg", "") if "+asyncpg" in OFFERS_DB_URL else OFFERS_DB_URL
engine = create_engine(sync_offers_db_url, echo=False) # Set echo=True for debugging SQL

# Spotify API Client
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
if SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET:
    client_credentials_manager = SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
else:
    logger.warning("Spotify client credentials not found. Spotify functionality will be disabled.")
    sp = None

# Redis Client for caching
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# Load valuation model (bundled in service folder)
MODEL_PATH = Path(__file__).parent / "model.pkl"
try:
    model = joblib.load(MODEL_PATH)
    logger.info("Valuation model loaded successfully.", model_path=str(MODEL_PATH))
except FileNotFoundError:
    logger.error("Valuation model model.pkl not found in service folder!", model_path=str(MODEL_PATH))
    model = None # Worker will fail tasks needing the model

# Load fallback rules
RULES_PATH = Path(__file__).parent / "rules.yaml"
try:
    with open(RULES_PATH, 'r') as f:
        rules_config = yaml.safe_load(f)
    logger.info("Fallback rules loaded successfully.", rules_path=str(RULES_PATH))
except FileNotFoundError:
    logger.error("Fallback rules rules.yaml not found!", rules_path=str(RULES_PATH))
    rules_config = {}

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
OFFER_VALUATED_TOPIC = "offer.valuated"

# --- Kafka Producer for offer.valuated ---
OFFER_VALUATED_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "offer_valuated.avsc"
_offer_valuated_producer = None
_offer_valuated_schema_str = None

def get_offer_valuated_producer():
    global _offer_valuated_producer, _offer_valuated_schema_str
    if _offer_valuated_producer is None:
        try:
            with open(OFFER_VALUATED_SCHEMA_PATH, 'r') as f:
                _offer_valuated_schema_str = f.read()
            # Pass delivery_report callback to create_avro_producer if it accepts it, or handle separately
            _offer_valuated_producer = create_avro_producer(value_schema_str=_offer_valuated_schema_str)
            logger.info("Offer.valuated Kafka producer initialized.", topic=OFFER_VALUATED_TOPIC)
        except FileNotFoundError:
            logger.error("offer_valuated.avsc not found. Kafka producer will not work.", path=str(OFFER_VALUATED_SCHEMA_PATH))
            _offer_valuated_producer = None # Ensure it's None if schema fails to load
        except Exception as e:
            logger.error("Failed to initialize Kafka producer for offer.valuated", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(service_name="valuation", error_type="kafka_producer_init", component="get_offer_valuated_producer").inc()
            _offer_valuated_producer = None # Ensure it's None on other init errors
    return _offer_valuated_producer

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_spotify_artist_data(artist_id: str):
    endpoint_name = "artist_details"
    if not sp:
        logger.warning("Spotify client not available.")
        SPOTIFY_API_CALLS_TOTAL.labels(endpoint=endpoint_name, status_code="error_client_unavailable").inc()
        return None
    
    cache_key = f"spotify:artist:{artist_id}"
    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            logger.info("Spotify artist data cache hit", artist_id=artist_id)
            CACHE_HITS_TOTAL.labels(cache_name="spotify_artist_data").inc()
            return json.loads(cached_data)
        CACHE_MISSES_TOTAL.labels(cache_name="spotify_artist_data").inc()
    except redis.exceptions.ConnectionError as e:
        logger.error("Redis connection error during cache get", error=str(e))
        APP_ERRORS_TOTAL.labels(service_name="valuation", error_type="redis_connection", component="cache_get").inc()
        # Fall through to API call if cache is down
    
    logger.info("Fetching Spotify artist data from API", artist_id=artist_id)
    start_time = time.monotonic()
    try:
        artist_data = sp.artist(artist_id) # Actual API call
        latency = time.monotonic() - start_time
        SPOTIFY_API_LATENCY_SECONDS.labels(endpoint=endpoint_name).observe(latency)
        SPOTIFY_API_CALLS_TOTAL.labels(endpoint=endpoint_name, status_code="200").inc()
        if artist_data:
            try:
                redis_client.setex(cache_key, timedelta(minutes=15), json.dumps(artist_data))
            except redis.exceptions.ConnectionError as e:
                logger.error("Redis connection error during cache set", error=str(e))
                APP_ERRORS_TOTAL.labels(service_name="valuation", error_type="redis_connection", component="cache_set").inc()
        return artist_data
    except spotipy.exceptions.SpotifyException as e:
        latency = time.monotonic() - start_time
        SPOTIFY_API_LATENCY_SECONDS.labels(endpoint=endpoint_name).observe(latency)
        status_code = e.http_status if hasattr(e, 'http_status') else "error_spotify_exception"
        SPOTIFY_API_CALLS_TOTAL.labels(endpoint=endpoint_name, status_code=str(status_code)).inc()
        logger.error("Spotify API error", error=str(e), artist_id=artist_id)
        APP_ERRORS_TOTAL.labels(service_name="valuation", error_type="spotify_api", component="get_artist_data").inc()
        raise # Re-raise for tenacity retry
    except Exception as e: # Catch other unexpected errors
        latency = time.monotonic() - start_time
        SPOTIFY_API_LATENCY_SECONDS.labels(endpoint=endpoint_name).observe(latency)
        SPOTIFY_API_CALLS_TOTAL.labels(endpoint=endpoint_name, status_code="error_unknown").inc()
        logger.error("Unexpected error fetching Spotify data", error=str(e), artist_id=artist_id, exc_info=True)
        APP_ERRORS_TOTAL.labels(service_name="valuation", error_type="unknown", component="get_artist_data").inc()
        raise

@celery_app.task(name="services.valuation.worker.run_valuation", bind=True)
def run_valuation(self, offer_id_str: str):
    task_start_time = time.monotonic()
    task_name = self.name # or "run_valuation"
    logger.info("Starting valuation for offer", offer_id=str(offer_id_str), task_name=task_name)
    offer_id = uuid.UUID(offer_id_str)
    status = "failure" # Default status for metrics

    try:
        with Session(engine) as session:
            offer = session.exec(select(Offer).where(Offer.id == offer_id)).first()
            if not offer:
                logger.error("Offer not found for valuation", offer_id=str(offer_id))
                APP_ERRORS_TOTAL.labels(service_name="valuation", error_type="not_found", component="db_get_offer").inc()
                status = "failure_offer_not_found"
                return {"status": "error", "message": "Offer not found"}
            
            logger.info("Offer retrieved", offer_id=str(offer_id), offer_title=offer.title, creator_id=offer.creator_id)

            spotify_data = None
            if offer.creator and offer.creator.platform_name == "spotify" and sp:
                logger.info("Fetching Spotify data for creator", creator_platform_id=offer.creator.platform_id)
                spotify_data = get_spotify_artist_data(offer.creator.platform_id)
            else:
                logger.warning("Spotify data cannot be fetched for offer.", offer_id=str(offer_id))

            raw_features_data = {
                "streams_last_month": spotify_data.get('followers', {}).get('total', 0) if spotify_data else 0,
                "country_listeners": len(spotify_data.get('available_markets', [])) if spotify_data else 0
            }
            feature_dict = process_data_for_features(raw_features_data)
            feature_df = pd.DataFrame([feature_dict])

            if not model:
                logger.error("Valuation model not loaded. Cannot predict.")
                offer.status = "VALUATION_FAILED_MODEL_MISSING"
                session.add(offer)
                session.commit()
                APP_ERRORS_TOTAL.labels(service_name="valuation", error_type="model_missing", component="predict").inc()
                MODEL_PREDICTIONS_TOTAL.labels(outcome="error_model_missing").inc()
                status = "failure_model_missing"
                return {"status": "error", "message": "Valuation model not loaded"}
            
            try:
                prediction_results = model.predict(feature_df)
                MODEL_PREDICTIONS_TOTAL.labels(outcome="success").inc()
                computed_low_eur = int(prediction_results[0][0])
                computed_median_eur = int(prediction_results[0][1])
                computed_high_eur = int(prediction_results[0][2])
                computed_confidence = float(prediction_results[0][3])
            except Exception as e:
                logger.error("Error during model prediction", error=str(e), offer_id=str(offer_id))
                offer.status = "VALUATION_FAILED_PREDICTION_ERROR"
                session.add(offer)
                session.commit()
                APP_ERRORS_TOTAL.labels(service_name="valuation", error_type="prediction_error", component="predict").inc()
                MODEL_PREDICTIONS_TOTAL.labels(outcome="error_prediction").inc()
                status = "failure_prediction_error"
                return {"status": "error", "message": f"Model prediction error: {e}"}

            # 5. Apply fallback rules
            # Example rule check from rules.yaml (needs actual flag checks)
            # stream_decline_threshold = rules_config.get('STREAM_DECLINE', {}).get('threshold', 0.3)
            # current_stream_decline = spotify_data.get('stream_decline_rate', 0) # Fictional field
            # if current_stream_decline > stream_decline_threshold and is_feature_enabled("fallback_stream_decline", offer_id):
            #    logger.info("Applying fallback rule for stream decline")
            #    computed_median_eur = max(1000, computed_median_eur * 0.8) # e.g. cap at 10 EUR or reduce by 20%

            # 6. Update offer row
            offer.price_low_eur = computed_low_eur
            offer.price_median_eur = computed_median_eur
            offer.price_high_eur = computed_high_eur
            offer.valuation_confidence = computed_confidence
            offer.status = "OFFER_READY"
            offer.updated_at = datetime.utcnow()
            session.add(offer)
            session.commit()
            session.refresh(offer)
            logger.info("Offer updated with valuation", offer_id=str(offer.id), status=offer.status)

            # 7. Produce Kafka event
            producer = get_offer_valuated_producer()
            if producer and _offer_valuated_schema_str: # Check schema loaded too
                # Ensure creator_id is UUID string for Avro schema
                # Assuming offer.creator_id is always a valid UUID if offer.creator is not loaded or None
                # The Avro schema expects a string for creator_id.
                creator_id_for_event = str(offer.creator_id)
                if offer.creator and hasattr(offer.creator, 'id') and offer.creator.id is not None:
                     creator_id_for_event = str(offer.creator.id) # Prefer ID from loaded creator if available

                event_payload = {
                    "event_id": str(uuid.uuid4()), # Add a unique event_id
                    "offer_id": str(offer.id),
                    "creator_id": creator_id_for_event,
                    "price_low_eur": offer.price_low_eur,
                    "price_median_eur": offer.price_median_eur,
                    "price_high_eur": offer.price_high_eur,
                    "valuation_confidence": offer.valuation_confidence,
                    "status": offer.status,
                    "timestamp": int(datetime.utcnow().timestamp() * 1_000_000) # Microseconds
                }
                try:
                    producer.produce(
                        topic=OFFER_VALUATED_TOPIC, 
                        key=str(offer.id), 
                        value=event_payload, 
                        on_delivery=delivery_report
                    )
                    producer.poll(0) # Trigger delivery report callbacks non-blockingly
                    logger.info("offer.valuated event produced to Kafka", offer_id=str(offer.id), payload_keys=list(event_payload.keys()))
                except KafkaException as e: # Catch specific Kafka errors
                    logger.error("Kafka producer error for offer.valuated", error=str(e), offer_id=str(offer.id))
                    APP_ERRORS_TOTAL.labels(service_name="valuation", error_type="kafka_produce_error", component="run_valuation").inc()
                except Exception as e: # Catch other unexpected errors during Kafka produce
                    logger.error("Unexpected error during Kafka produce for offer.valuated", error=str(e), offer_id=str(offer.id), exc_info=True)
                    APP_ERRORS_TOTAL.labels(service_name="valuation", error_type="kafka_produce_unexpected", component="run_valuation").inc()
            else:
                logger.warning("Kafka producer for offer.valuated not available or schema not loaded.", offer_id=str(offer.id))
            status = "success"
            return {"status": "success", "offer_id": str(offer.id), "valuation": event_payload}

    except Exception as e:
        logger.error("Unhandled exception in run_valuation task", error=str(e), offer_id=str(offer_id), exc_info=True)
        APP_ERRORS_TOTAL.labels(service_name="valuation", error_type="unhandled_exception", component="run_valuation_task").inc()
        status = "failure_unhandled_exception"
        # Consider if task should be retried for some unhandled exceptions
        raise # Re-raise to let Celery handle retry logic or mark as failed
    finally:
        task_duration = time.monotonic() - task_start_time
        CELERY_TASK_DURATION_SECONDS.labels(task_name=task_name).observe(task_duration)
        CELERY_TASKS_PROCESSED_TOTAL.labels(task_name=task_name, status=status).inc()

# To run worker: celery -A services.valuation.worker.celery_app worker -l INFO
# Remember to have Redis running.
# For the Kafka part, a Kafka broker needs to be running.
# Ensure SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET are set in env.
# Ensure DB_CONNECTION_STRING points to the offers DB.
# Ensure model.pkl and rules.yaml are in services/valuation/ 