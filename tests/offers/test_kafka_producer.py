# tests/offers/test_kafka_producer.py
import pytest
import uuid
from unittest.mock import patch, MagicMock
from fastapi import BackgroundTasks # To mock/verify background task usage
from sqlmodel import Session # For type hinting if needed
from datetime import datetime

# Adjust to your project structure
from services.offers.routes import handle_create_offer # The endpoint to test
from services.offers.models import OfferCreate, Offer, Creator # Models used
from libs.py_common.kafka import delivery_report # if used as callback

@pytest.mark.asyncio
@patch("services.offers.routes.get_offer_created_producer")
@patch("services.offers.routes.create_db_offer")
async def test_handle_create_offer_produces_kafka_event(
    mock_create_db_offer: MagicMock,
    mock_get_kafka_producer: MagicMock,
):
    # --- Arrange ---
    mock_producer_instance = MagicMock()
    mock_producer_instance.produce = MagicMock()
    mock_get_kafka_producer.return_value = mock_producer_instance
    
    # Ensure _offer_created_schema_str is also "loaded" for the if condition in route
    # This can be done by patching the global _offer_created_schema_str in routes module
    with patch("services.offers.routes._offer_created_schema_str", "mocked_schema_string"):

        test_offer_id = uuid.uuid4()
        test_creator_id = uuid.uuid4() # Assuming creator ID is UUID now for consistency with Avro
        
        mock_created_db_offer = Offer(
            id=test_offer_id,
            creator_id=test_creator_id,
            creator=Creator(id=test_creator_id, platform_id="test_platform", platform_name="test", username="testuser", created_at=datetime.utcnow(), updated_at=datetime.utcnow()), # Mock creator
            title="Kafka Test Offer",
            description="Testing Kafka production",
            amount_cents=10000,
            currency_code="EUR",
            status="PENDING_VALUATION",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            price_low_eur=None, price_median_eur=None, price_high_eur=None, valuation_confidence=None, # Add new fields
            pdf_url=None, pdf_hash=None
        )
        mock_create_db_offer.return_value = mock_created_db_offer

        offer_create_data = OfferCreate(
            creator_id=test_creator_id,
            title="Kafka Test Offer",
            description="Testing Kafka production",
            amount_cents=10000,
            currency_code="EUR",
            status="PENDING_VALUATION"
        )
        
        mock_session = MagicMock(spec=Session) # AsyncSession would be from sqlmodel.ext.asyncio.session
        mock_background_tasks = BackgroundTasks()

        # --- Act ---
        await handle_create_offer(offer_data=offer_create_data, session=mock_session, background_tasks=mock_background_tasks)

        # --- Assert ---
        mock_create_db_offer.assert_called_once_with(session=mock_session, offer_data=offer_create_data)
        
        # Check if producer was obtained
        mock_get_kafka_producer.assert_called_once()
        
        # Check if producer.produce was added to background_tasks
        # This requires inspecting what add_task was called with.
        assert len(mock_background_tasks.tasks) == 1
        task = mock_background_tasks.tasks[0]
        assert task.func == mock_producer_instance.produce
        
        # Check the arguments passed to producer.produce via the background task
        # task.args contains the positional arguments
        # task.kwargs contains the keyword arguments
        produce_args = task.args
        produce_kwargs = task.kwargs
        
        assert produce_kwargs.get("topic") == "offer.created"
        assert produce_kwargs.get("key") == str(test_offer_id)
        
        expected_payload = {
            "offer_id": str(test_offer_id),
            "creator_id": str(test_creator_id),
            "title": "Kafka Test Offer",
            "description": "Testing Kafka production",
            "amount_cents": 10000,
            "currency_code": "EUR",
            "status": "PENDING_VALUATION",
            "created_at_timestamp": int(mock_created_db_offer.created_at.timestamp() * 1_000_000)
        }
        assert produce_kwargs.get("value") == expected_payload
        assert produce_kwargs.get("on_delivery") == delivery_report

# Add similar tests for valuation_worker producing offer.valuated
# Add tests for event_consumer consuming payout.succeeded (more complex, may need Kafka test container or better confluent_kafka mocks) 