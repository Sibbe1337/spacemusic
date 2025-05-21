# tests/valuation/test_kafka_producer.py
import pytest
import uuid
from unittest.mock import patch, MagicMock
from datetime import datetime
from sqlmodel import Session # For type hinting

from services.valuation.worker import run_valuation # The task to test
from services.offers.models import Offer, Creator # Models used
from libs.py_common.kafka import delivery_report # Callback

# This test will focus on the Kafka production part of the run_valuation task.
# It assumes other parts of the task (DB interaction, Spotify, model prediction) are mocked
# or handled by other unit/integration tests.

@pytest.fixture
def mock_valuation_offer():
    offer_id = uuid.uuid4()
    creator_id = uuid.uuid4() # Assuming Creator.id is UUID for consistency
    return Offer(
        id=offer_id,
        creator_id=creator_id,
        creator=Creator(id=creator_id, platform_id="spotify_test", platform_name="spotify", username="test_val_user", created_at=datetime.utcnow(), updated_at=datetime.utcnow()),
        title="Valuation Kafka Test Offer",
        status="OFFER_READY", # Status must be OFFER_READY for event to be produced
        price_low_eur=10000,
        price_median_eur=15000,
        price_high_eur=20000,
        valuation_confidence=0.85,
        amount_cents=15000, # Example
        currency_code="EUR", # Example
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

@patch("services.valuation.worker.get_offer_valuated_producer")
@patch("services.valuation.worker.Session") # Mock the DB session context manager
@patch("services.valuation.worker.get_spotify_artist_data") # Mock Spotify calls
@patch("services.valuation.worker.process_data_for_features") # Mock feature processing
@patch("services.valuation.worker.model") # Mock the loaded ML model
def test_run_valuation_produces_kafka_event(
    mock_ml_model: MagicMock,
    mock_process_features: MagicMock,
    mock_get_spotify: MagicMock,
    mock_sqlmodel_session: MagicMock, # This is the Session class for `with Session(engine) as session:`
    mock_get_kafka_producer: MagicMock,
    mock_valuation_offer: Offer
):
    # --- Arrange ---
    # Mock Kafka Producer
    mock_producer_instance = MagicMock()
    mock_producer_instance.produce = MagicMock()
    mock_get_kafka_producer.return_value = mock_producer_instance
    with patch("services.valuation.worker._offer_valuated_schema_str", "mocked_schema_string"):

        # Mock DB session interactions
        mock_session_ctx_mgr = MagicMock() # Mock for the `with ... as session` part
        mock_session_instance = MagicMock(spec=Session)
        mock_session_ctx_mgr.__enter__.return_value = mock_session_instance
        mock_session_ctx_mgr.__exit__.return_value = None
        mock_sqlmodel_session.return_value = mock_session_ctx_mgr
        
        # Mock the offer returned by session.exec(select(...)).first()
        mock_db_result = MagicMock()
        mock_db_result.first.return_value = mock_valuation_offer
        mock_session_instance.exec.return_value = mock_db_result

        # Mock Spotify, feature processing, and model prediction to return valid data
        mock_get_spotify.return_value = {"followers": {"total": 5000}, "available_markets": ["US", "DE"]}
        mock_process_features.return_value = {"feature1": 10, "feature2": 20} # Example dict
        # Model predict should return [[low, median, high, confidence]]
        # These values should match what's set on mock_valuation_offer for assertion consistency
        mock_ml_model.predict.return_value = [[ 
            mock_valuation_offer.price_low_eur,
            mock_valuation_offer.price_median_eur,
            mock_valuation_offer.price_high_eur,
            mock_valuation_offer.valuation_confidence
        ]]

        # --- Act ---
        # The task is not bind=True in the provided snippet, so we call it directly
        # If it were bind=True, we'd need to mock `self` or use `task.s().delay()` approach
        result = run_valuation(str(mock_valuation_offer.id))

        # --- Assert ---
        assert result["status"] == "success"
        mock_get_kafka_producer.assert_called_once()
        mock_producer_instance.produce.assert_called_once()

        args, kwargs = mock_producer_instance.produce.call_args
        assert kwargs.get("topic") == "offer.valuated"
        assert kwargs.get("key") == str(mock_valuation_offer.id)
        
        produced_value = kwargs.get("value")
        assert produced_value["offer_id"] == str(mock_valuation_offer.id)
        assert produced_value["creator_id"] == str(mock_valuation_offer.creator_id)
        assert produced_value["price_low_eur"] == mock_valuation_offer.price_low_eur
        assert produced_value["price_median_eur"] == mock_valuation_offer.price_median_eur
        assert produced_value["price_high_eur"] == mock_valuation_offer.price_high_eur
        assert produced_value["valuation_confidence"] == mock_valuation_offer.valuation_confidence
        assert produced_value["status"] == "OFFER_READY"
        assert "timestamp" in produced_value
        assert kwargs.get("on_delivery") == delivery_report 