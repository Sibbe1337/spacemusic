# services/offers/routes.py
import uuid
import asyncio # For SSE sleep
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request # Added Request for SSE
from fastapi.responses import StreamingResponse # For SSE
import structlog
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession # Assuming async session from db.py
import json # For loading schema file
from pathlib import Path
from datetime import datetime # For timestamp in new event
import threading # For Kafka consumer thread
import time # For sleep in Kafka consumer loop

from .db import get_session # Assuming get_session provides AsyncSession
from .models import Offer, OfferCreate, OfferRead, Creator, CreatorCreate, CreatorRead, OfferStatus # Import OfferStatus
# Import metrics for custom counters if needed (starlette-prometheus handles HTTP ones)
from .metrics import OFFERS_CREATED_TOTAL, OFFER_STATUS_UPDATES_TOTAL, APP_ERRORS_TOTAL, KAFKA_MESSAGES_CONSUMED_TOTAL # Added KAFKA_MESSAGES_CONSUMED_TOTAL

# Kafka imports
from libs.py_common.kafka import (
    create_avro_producer, 
    create_avro_consumer, # Added
    delivery_report as kafka_delivery_report, # Renamed for clarity
    KafkaException
)

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/offers", # Standard prefix for offers related routes
    tags=["offers"],
)

# --- Kafka Producer Setup for offer.created ---
OFFER_CREATED_TOPIC = "offer.created"
OFFER_CREATED_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "offer_created.avsc"
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
            logger.error("offer_created.avsc not found.", path=str(OFFER_CREATED_SCHEMA_PATH))
            _offer_created_producer = None 
        except Exception as e:
            logger.error("Failed to initialize Kafka producer for offer.created", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(service_name="offers-api", error_type="kafka_producer_init", component="get_offer_created_producer").inc()
            _offer_created_producer = None
    return _offer_created_producer

# --- Kafka Producer Setup for offer.payout.requested ---
OFFER_PAYOUT_REQUESTED_TOPIC = "offer.payout.requested"
OFFER_PAYOUT_REQUESTED_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "offer_payout_requested.avsc"
_offer_payout_requested_producer = None
_offer_payout_requested_schema_str = None

def get_offer_payout_requested_producer():
    global _offer_payout_requested_producer, _offer_payout_requested_schema_str
    if _offer_payout_requested_producer is None:
        try:
            with open(OFFER_PAYOUT_REQUESTED_SCHEMA_PATH, 'r') as f:
                _offer_payout_requested_schema_str = f.read()
            _offer_payout_requested_producer = create_avro_producer(value_schema_str=_offer_payout_requested_schema_str)
            logger.info("Offer.payout.requested Kafka producer initialized.", topic=OFFER_PAYOUT_REQUESTED_TOPIC)
        except FileNotFoundError:
            logger.error("offer_payout_requested.avsc not found.", path=str(OFFER_PAYOUT_REQUESTED_SCHEMA_PATH))
            _offer_payout_requested_producer = None
        except Exception as e:
            logger.error("Failed to initialize Kafka producer for offer.payout.requested", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(service_name="offers-api", error_type="kafka_producer_init", component="get_offer_payout_requested_producer").inc()
            _offer_payout_requested_producer = None
    return _offer_payout_requested_producer

# --- Kafka Consumer Setup for Offer Updates (for SSE) ---
OFFER_UPDATES_CONSUMER_GROUP_ID = "offers-api-sse-fanout"
OFFER_VALUATED_TOPIC = "offer.valuated"
OFFER_PAYOUT_COMPLETED_TOPIC = "offer.payout.completed"
# Schemas (ensure these files exist in schema/)
OFFER_VALUATED_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "offer_valuated.avsc"
OFFER_PAYOUT_COMPLETED_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "offer_payout_completed.avsc"

_offer_updates_consumer = None
_offer_valuated_schema_str = None
_offer_payout_completed_schema_str = None
_offers_api_kafka_consumer_stop_event = threading.Event()

# We need a way to map topic to schema for a multi-topic consumer
# For now, let's assume we might use separate consumers or a more complex deserializer if schemas differ significantly
# Sticking to one consumer for simplicity, assuming AvroDeserializer can handle it if schemas are registered
# Or, more robustly, use specific deserializers per topic if needed.

# For this example, we'll focus on consuming and then deciding what to broadcast.
# A single consumer for multiple topics is fine if the AvroDeserializer is set up generally
# or if we inspect the topic and then decode with the correct schema.
# The create_avro_consumer in libs expects a single value_schema_str. 
# This implies we might need two consumer instances if schemas are different and not auto-detected by topic.

# Simpler approach: One consumer, generic Avro deserialization, then check topic for specifics.
# This requires Schema Registry to have schemas registered with subject name strategy that allows resolution.

# Let's create a generic consumer first that can be expanded.
# We will need to load ALL schemas this consumer might encounter.

_offer_updates_event_loop = None # To run async broadcast_deal_update from sync consumer thread

def get_offer_updates_consumer():
    global _offer_updates_consumer # Removed schema string globals as they are not needed here anymore
    if _offer_updates_consumer is None:
        try:
            # Schemas are no longer loaded here; AvroDeserializer will use Schema Registry
            _offer_updates_consumer = create_avro_consumer(
                group_id=OFFER_UPDATES_CONSUMER_GROUP_ID,
                topics=[OFFER_VALUATED_TOPIC, OFFER_PAYOUT_COMPLETED_TOPIC],
                value_schema_str=None # Explicitly pass None or omit
            )
            logger.info("Kafka consumer for offer updates (SSE) initialized to use Schema Registry for deserialization.")
        except Exception as e:
            logger.error("Failed to initialize Kafka consumer for offer updates (SSE)", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(service_name="offers-api", component="kafka_sse_consumer_init", error_type=str(type(e).__name__)).inc()
            _offer_updates_consumer = None
    return _offer_updates_consumer

def consume_offer_updates_for_sse(loop: asyncio.AbstractEventLoop):
    logger.info("Starting Kafka consumer loop for SSE offer updates...")
    consumer = get_offer_updates_consumer()
    if not consumer:
        logger.error("Offer updates SSE consumer not available. Exiting loop.")
        return

    while not _offers_api_kafka_consumer_stop_event.is_set():
        try:
            msg = consumer.poll(timeout=1.0)
            if msg is None: continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF: continue
                logger.error("Kafka SSE consumer error", error=msg.error(), topic=msg.topic())
                APP_ERRORS_TOTAL.labels(service_name="offers-api", component="kafka_sse_consumer_poll", error_type=str(msg.error().code())).inc()
                time.sleep(5)
                continue
            
            event_data = msg.value()
            topic = msg.topic()
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=topic, group_id=OFFER_UPDATES_CONSUMER_GROUP_ID, status="success").inc()
            logger.info("SSE Consumer: Received event", topic=topic, data_keys=list(event_data.keys()) if event_data else [])

            sse_event_type = "UNKNOWN_EVENT"
            if topic == OFFER_VALUATED_TOPIC:
                sse_event_type = "OFFER_VALUATED"
            elif topic == OFFER_PAYOUT_COMPLETED_TOPIC:
                sse_event_type = "OFFER_PAYOUT_COMPLETED"
            
            # Run the async broadcast function in the main event loop
            asyncio.run_coroutine_threadsafe(broadcast_deal_update({"type": sse_event_type, "payload": event_data}), loop)
            consumer.commit(message=msg)
        except Exception as e:
            logger.error("Exception in Kafka SSE consumer loop", error=str(e), exc_info=True)
            APP_ERRORS_TOTAL.labels(service_name="offers-api", component="kafka_sse_consumer_loop", error_type="exception").inc()
            time.sleep(5)
    
    logger.info("Kafka consumer loop for SSE offer updates stopping.")
    if consumer: consumer.close()

_sse_consumer_thread = None

async def start_sse_kafka_listener():
    global _sse_consumer_thread, _offer_updates_event_loop
    if not get_offer_updates_consumer():
        logger.error("Cannot start SSE Kafka listener: Consumer init failed.")
        return
    if _sse_consumer_thread and _sse_consumer_thread.is_alive():
        logger.info("SSE Kafka listener thread already running.")
        return
    
    _offer_updates_event_loop = asyncio.get_event_loop()
    _offers_api_kafka_consumer_stop_event.clear()
    _sse_consumer_thread = threading.Thread(target=consume_offer_updates_for_sse, args=(_offer_updates_event_loop,), daemon=True)
    _sse_consumer_thread.name = "OffersApiSseKafkaConsumerThread"
    _sse_consumer_thread.start()
    logger.info("SSE Kafka listener thread started.")

async def stop_sse_kafka_listener():
    global _sse_consumer_thread
    logger.info("Signaling SSE Kafka listener thread to stop...")
    _offers_api_kafka_consumer_stop_event.set()
    if _sse_consumer_thread and _sse_consumer_thread.is_alive():
        _sse_consumer_thread.join(timeout=5)
        if _sse_consumer_thread.is_alive():
            logger.warning("SSE Kafka listener thread did not stop in time.")
    _sse_consumer_thread = None
    logger.info("SSE Kafka listener thread stopped.")

# --- SSE Endpoint for Deal Updates ---
# In-memory store for active SSE client queues (simple approach for single instance)
# For multi-instance setup, a shared message broker like Redis pub/sub would be needed.
active_sse_clients: list[asyncio.Queue] = []

async def deal_event_generator(request: Request):
    queue = asyncio.Queue()
    active_sse_clients.append(queue)
    try:
        while True:
            # Wait for an event to be put into this client's queue
            # Or send periodic heartbeats to keep connection alive
            try:
                event_data_json = await asyncio.wait_for(queue.get(), timeout=15) # Wait for 15s
                yield f"data: {event_data_json}\n\n" # SSE format: data: <json_string>\n\n
                queue.task_done() # Mark as processed
            except asyncio.TimeoutError:
                # Send a heartbeat comment to keep the connection alive
                yield ":heartbeat\n\n"
            
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info("SSE client disconnected (detected by request.is_disconnected())")
                break
    except asyncio.CancelledError:
        logger.info("SSE connection cancelled/closed by client.")
    finally:
        if queue in active_sse_clients:
            active_sse_clients.remove(queue)
        logger.info(f"SSE client queue removed. Active clients: {len(active_sse_clients)}")

@router.get("/events/deals", response_class=StreamingResponse)
async def stream_deal_events(request: Request):
    """Endpoint for Server-Sent Events to stream deal updates."""
    # Set headers for SSE
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no", # For Nginx if it's in front
    }
    return StreamingResponse(deal_event_generator(request), headers=headers)

# Function to be called by Kafka consumer or other parts of the app to send updates to SSE clients
async def broadcast_deal_update(deal_update_data: dict):
    """Broadcasts a deal update to all connected SSE clients."""
    if not active_sse_clients:
        logger.debug("No active SSE clients to broadcast update to.")
        return

    event_data_json = json.dumps(deal_update_data) # Ensure it's a JSON string
    logger.info(f"Broadcasting deal update to {len(active_sse_clients)} SSE client(s)", data_keys=list(deal_update_data.keys()))
    for queue in active_sse_clients:
        try:
            await queue.put(event_data_json)
        except Exception as e:
            logger.error("Failed to put message in an SSE client queue", error=str(e), exc_info=True)

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
                "event_id": str(uuid.uuid4()),
                "offer_id": str(db_offer.id),
                "creator_id": str(db_offer.creator_id),
                "title": db_offer.title,
                "description": db_offer.description,
                "amount_cents": db_offer.amount_cents,
                "currency_code": db_offer.currency_code,
                "status": db_offer.status.value, # Use enum value
                "created_at_timestamp": int(db_offer.created_at.timestamp() * 1_000_000)
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

        # After successfully creating/updating offer in DB and sending Kafka event
        # Broadcast to SSE clients (example with OfferRead model)
        offer_read_data = OfferRead.model_validate(db_offer).model_dump_json()
        await broadcast_deal_update({"type": "OFFER_CREATED", "payload": json.loads(offer_read_data)})
        return db_offer
    except Exception as e:
        logger.error("Failed to create offer in DB", error=str(e), exc_info=True)
        APP_ERRORS_TOTAL.labels(service_name="offers-api", error_type="db_create_offer_error", component="handle_create_offer").inc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create offer.")

@router.post("/{offer_id}/request-payout", status_code=status.HTTP_202_ACCEPTED)
async def handle_request_payout(
    offer_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    logger.info("Received request for payout for offer", offer_id=str(offer_id))
    offer = await session.get(Offer, offer_id)
    if not offer:
        APP_ERRORS_TOTAL.labels(service_name="offers-api", error_type="offer_not_found", component="handle_request_payout").inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")

    if offer.status != OfferStatus.OFFER_READY:
        logger.warning("Payout requested for offer not in OFFER_READY state", offer_id=str(offer_id), current_status=offer.status.value)
        APP_ERRORS_TOTAL.labels(service_name="offers-api", error_type="invalid_status_for_payout", component="handle_request_payout").inc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Offer status is {offer.status.value}, must be OFFER_READY to request payout.")

    # Update offer status (optional, depends on your state machine)
    # offer.status = OfferStatus.PAYOUT_REQUESTED # Assuming this status exists
    # offer.updated_at = datetime.utcnow()
    # session.add(offer)
    # await session.commit()
    # await session.refresh(offer)
    # OFFER_STATUS_UPDATES_TOTAL.labels(new_status=OfferStatus.PAYOUT_REQUESTED.value).inc()

    producer = get_offer_payout_requested_producer()
    if producer and _offer_payout_requested_schema_str:
        # TODO: Determine how to get recipient_details. For now, placeholder.
        # This might come from the Offer model, Creator model, or a separate system.
        recipient_details_placeholder = f"recipient_details_for_creator_{offer.creator_id}"
        
        event_payload = {
            "event_id": str(uuid.uuid4()),
            "offer_id": str(offer.id),
            "amount_cents": offer.price_median_eur, # Assuming payout is based on median price
            "currency_code": "EUR", # Assuming EUR, adjust if needed
            "recipient_details": recipient_details_placeholder, 
            "requested_at_micros": int(datetime.utcnow().timestamp() * 1_000_000)
        }
        try:
            background_tasks.add_task(
                producer.produce,
                topic=OFFER_PAYOUT_REQUESTED_TOPIC,
                key=str(offer.id),
                value=event_payload,
                on_delivery=delivery_report
            )
            logger.info("offer.payout.requested event enqueued to Kafka background task", offer_id=str(offer.id))
        except KafkaException as e:
            logger.error("Kafka producer error for offer.payout.requested", error=str(e), offer_id=str(offer.id))
            APP_ERRORS_TOTAL.labels(service_name="offers-api", error_type="kafka_produce_error", component="handle_request_payout").inc()
            # Decide if API should fail if Kafka publish fails
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to enqueue payout request event.")
        except Exception as e:
            logger.error("Unexpected error during Kafka produce for offer.payout.requested", error=str(e), offer_id=str(offer.id), exc_info=True)
            APP_ERRORS_TOTAL.labels(service_name="offers-api", error_type="kafka_produce_unexpected", component="handle_request_payout").inc()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error processing payout request.")
    else:
        logger.error("Kafka producer for offer.payout.requested not available or schema not loaded. Cannot send event.", offer_id=str(offer.id))
        # This is a critical internal error if producer is expected to be available
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Payout processing system unavailable.")

    # After successfully enqueuing offer.payout.requested
    await broadcast_deal_update({
        "type": "OFFER_PAYOUT_REQUESTED", 
        "payload": {"offer_id": str(offer_id), "status": "PAYOUT_REQUESTED"} # Example
    })
    return {"message": "Offer payout request enqueued successfully", "offer_id": str(offer.id)}

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

# Modify FastAPI startup/shutdown to manage Kafka consumer for SSE
@router.on_event("startup")
async def on_offers_api_startup():
    # Initialize producers if not already done (idempotent call)
    get_offer_created_producer()
    get_offer_payout_requested_producer()
    # Start the Kafka consumer for SSE updates
    await start_sse_kafka_listener()
    logger.info("Offers API startup: Kafka producers and SSE consumer listener initialized/started.")

@router.on_event("shutdown")
async def on_offers_api_shutdown():
    # Stop the Kafka consumer for SSE updates
    await stop_sse_kafka_listener()
    # Note: Producers are typically not explicitly closed unless specific resource cleanup is needed.
    # The underlying librdkafka handles connection management.
    logger.info("Offers API shutdown: SSE consumer listener stopped.") 