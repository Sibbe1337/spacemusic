# services/offers/routes.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
import structlog
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession # Assuming async session from db.py
import json # For loading schema file
from pathlib import Path

from .db import get_session # Assuming get_session provides AsyncSession
from .models import Offer, OfferCreate, OfferRead, Creator, CreatorCreate, CreatorRead # Import all relevant models
# Import metrics for custom counters if needed (starlette-prometheus handles HTTP ones)
from .metrics import OFFERS_CREATED_TOTAL, OFFER_STATUS_UPDATES_TOTAL, APP_ERRORS_TOTAL

# Kafka imports
from libs.py_common.kafka import create_avro_producer, delivery_report

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/offers", # Standard prefix for offers related routes
    tags=["offers"],
)

# --- Kafka Producer Setup ---
OFFER_CREATED_TOPIC = "offer.created"
OFFER_CREATED_SCHEMA_PATH = Path(__file__).parent.parent.parent / "schema" / "offer_created.avsc"

_offer_created_producer = None
_offer_created_schema_str = None

def get_offer_created_producer():
    global _offer_created_producer, _offer_created_schema_str
    if _offer_created_producer is None:
        try:
            with open(OFFER_CREATED_SCHEMA_PATH, 'r') as f:
                _offer_created_schema_str = f.read()
            _offer_created_producer = create_avro_producer(value_schema_str=_offer_created_schema_str)
            logger.info("Offer.created Kafka producer initialized.", topic=OFFER_CREATED_TOPIC)
        except FileNotFoundError:
            logger.error("offer_created.avsc not found. Kafka producer for offer.created will not work.", path=str(OFFER_CREATED_SCHEMA_PATH))
            _offer_created_producer = None # Ensure it remains None if schema load fails
        except Exception as e:
            logger.error("Failed to initialize Kafka producer for offer.created", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(service_name="offers-api", error_type="kafka_producer_init", component="get_offer_created_producer").inc()
            _offer_created_producer = None # Ensure it remains None
    return _offer_created_producer

# Example CRUD functions (can be moved to a crud.py file)
async def create_db_offer(session: AsyncSession, offer_data: OfferCreate) -> Offer:
    # Here you might want to fetch or create the Creator if creator_id refers to an existing one
    # or if creator details are part of OfferCreate and need to be handled.
    # For simplicity, assume creator_id is valid and exists.
    db_offer = Offer.model_validate(offer_data)
    session.add(db_offer)
    await session.commit()
    await session.refresh(db_offer)
    # Load creator relationship for the event if needed and not auto-loaded by refresh
    # This depends on your Offer model and relationship loading strategy.
    # If Offer.creator is a relationship, ensure it's available for the Kafka event.
    # One way is to re-fetch with the relationship explicitly loaded:
    refreshed_offer_with_creator = await session.exec(
        select(Offer).options(selectinload(Offer.creator)).where(Offer.id == db_offer.id)
    )
    return refreshed_offer_with_creator.one() # Use .one() if sure it exists

@router.post("/", response_model=OfferRead, status_code=status.HTTP_201_CREATED)
async def handle_create_offer(
    offer_data: OfferCreate, 
    session: AsyncSession = Depends(get_session),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    logger.info("Received request to create offer", title=offer_data.title, creator_id=offer_data.creator_id)
    try:
        db_offer = await create_db_offer(session=session, offer_data=offer_data)
        OFFERS_CREATED_TOTAL.labels(platform_name=db_offer.creator.platform_name if db_offer.creator else "unknown").inc()
        
        # Produce Kafka event for offer.created
        producer = get_offer_created_producer()
        if producer and _offer_created_schema_str: # Ensure producer and schema are loaded
            event_payload = {
                "offer_id": str(db_offer.id),
                "creator_id": str(db_offer.creator_id), # Assuming Creator.id is also UUID for consistency with Avro
                "title": db_offer.title,
                "description": db_offer.description,
                "amount_cents": db_offer.amount_cents,
                "currency_code": db_offer.currency_code,
                "status": db_offer.status,
                "created_at_timestamp": int(db_offer.created_at.timestamp() * 1_000_000) # To microseconds
            }
            try:
                # Use background_tasks for non-blocking Kafka produce
                background_tasks.add_task(
                    producer.produce,
                    topic=OFFER_CREATED_TOPIC,
                    key=str(db_offer.id), # Use offer_id as key
                    value=event_payload,
                    on_delivery=delivery_report
                )
                # producer.poll(0) # Not strictly needed for background task, flush if critical & sync
                logger.info("offer.created event enqueued to Kafka background task", offer_id=str(db_offer.id))
            except KafkaException as e:
                logger.error("Kafka producer error for offer.created", error=str(e), offer_id=str(db_offer.id))
                APP_ERRORS_TOTAL.labels(service_name="offers-api", error_type="kafka_produce_error", component="handle_create_offer").inc()
                # Decide if failure to produce should fail the API call or just log
            except Exception as e: # Catch other unexpected errors during Kafka produce
                logger.error("Unexpected error during Kafka produce for offer.created", error=str(e), offer_id=str(db_offer.id), exc_info=True)
                APP_ERRORS_TOTAL.labels(service_name="offers-api", error_type="kafka_produce_unexpected", component="handle_create_offer").inc()

        return db_offer
    except Exception as e:
        logger.error("Failed to create offer in DB", error=str(e), exc_info=True)
        APP_ERRORS_TOTAL.labels(service_name="offers-api", error_type="db_create_offer_error", component="handle_create_offer").inc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create offer.")

# Placeholder for other routes (GET, PUT, DELETE for offers and creators)
@router.get("/{offer_id}", response_model=OfferRead)
async def handle_read_offer(offer_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    offer = await session.get(Offer, offer_id)
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    return offer

# It might be better to have a separate set of routes for /creators
@router.post("/creators/", response_model=CreatorRead, status_code=status.HTTP_201_CREATED)
async def handle_create_creator(creator_data: CreatorCreate, session: AsyncSession = Depends(get_session)):
    # Basic check for existing creator by platform_id to avoid duplicates if desired
    existing_creator_stmt = await session.exec(select(Creator).where(Creator.platform_id == creator_data.platform_id))
    existing_creator = existing_creator_stmt.first()
    if existing_creator:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Creator with platform_id {creator_data.platform_id} already exists.")
    
    db_creator = Creator.model_validate(creator_data)
    session.add(db_creator)
    await session.commit()
    await session.refresh(db_creator)
    return db_creator 