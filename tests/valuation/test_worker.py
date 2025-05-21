import pytest
from unittest.mock import patch, MagicMock
import uuid
import pandas as pd
from datetime import datetime

# Adjust imports based on your project structure and where the worker/models are
# This assumes services/valuation and services/offers are discoverable (e.g. via PYTHONPATH)
from services.valuation.worker import run_valuation, celery_app #, get_spotify_artist_data
from services.offers.models import Offer, Creator # Assuming Offer.id is UUID as per recent changes

# Mock joblib.load for the valuation model
@pytest.fixture(scope="module") # Scope to module as model loading is global in worker
def mock_valuation_model():
    mock_model = MagicMock()
    # Define what model.predict should return: [[low, median, high, confidence]]
    mock_model.predict.return_value = [[10000, 15000, 20000, 0.85]] # e.g., 100€, 150€, 200€
    with patch('services.valuation.worker.joblib.load', return_value=mock_model) as mock_load:
        with patch('services.valuation.worker.model', new=mock_model): # Also patch the global 'model' var
            yield mock_load, mock_model

@pytest.fixture
def mock_spotify_client():
    mock_sp = MagicMock()
    mock_sp.artist.return_value = {
        "id": "test_artist_id",
        "name": "Test Artist",
        "followers": {"total": 100000},
        "popularity": 75,
        "genres": ["pop", "rock"],
        "available_markets": ["US", "GB", "DE"]
    }
    # Mock other spotipy methods if used by get_spotify_artist_data (e.g., artist_top_tracks)
    with patch('services.valuation.worker.sp', new=mock_sp):
        yield mock_sp

@pytest.fixture
def mock_redis_client():
    mock_redis = MagicMock()
    mock_redis.get.return_value = None # Simulate cache miss initially
    mock_redis.setex = MagicMock()
    with patch('services.valuation.worker.redis_client', new=mock_redis):
        yield mock_redis

@pytest.fixture
def mock_offer_session(monkeypatch):
    mock_session_instance = MagicMock()
    
    # Setup a dictionary to act as our "database" for offers
    db_offers = {}

    def mock_get_offer(model_cls, offer_id_val):
        # print(f"Mock DB: Trying to get {model_cls.__name__} with ID {offer_id_val}")
        # print(f"Mock DB: Current offers: {db_offers.keys()}")
        return db_offers.get(offer_id_val)

    def mock_exec_select_offer(select_statement):
        # A bit more complex to truly mock SQLalchemy's select().where() behavior
        # For this test, we assume it's a simple select by ID from run_valuation
        # We need to inspect the select_statement to get the offer_id if possible
        # This is a simplification; a real test might need a more robust mock or test DB.
        # For now, let's assume the test setup below will populate db_offers directly.
        # And rely on the fact that offer_id is passed to run_valuation.
        # So, effectively, run_valuation will use its offer_id argument to populate the dict.
        mock_result = MagicMock()
        # The test will populate db_offers with the offer_id used in the task.
        # We need to find *which* offer_id to return from db_offers.
        # This is tricky without parsing the select_statement. For this test, assume the test
        # that calls run_valuation will ensure the offer_id used in run_valuation exists in db_offers.
        # We'll just return the first item for simplicity for now or rely on test_run_valuation to manage state.
        # A better mock_exec_select_offer would parse the where clause.
        # This is a simplification to enable the test to proceed.
        # The test_run_valuation will create the offer and pass its id.
        # So, db_offers should contain the offer we care about.
        # If there are multiple offers in db_offers, this mock is too simple.
        # For this specific test, we will assume only one offer is relevant per test run setup.
        # found_offer = list(db_offers.values())[0] if db_offers else None
        # mock_result.first.return_value = found_offer
        # This is still problematic. The `select(Offer).where(Offer.id == offer_id)` needs a better mock.
        # Let's have `run_valuation` set up the offer in `db_offers` for the specific test.
        # The test will need to ensure db_offers has the item the select statement would find.
        class MockResult:
            def __init__(self, offer_to_find):
                self._offer_to_find = offer_to_find
            def first(self):
                return self._offer_to_find
        
        # This needs to be dynamic based on the where clause.
        # The actual test will populate db_offers with the specific offer_id
        # that run_valuation will query for.
        # So when `where(Offer.id == offer_id)` is called, we need to return that specific offer.
        # This is a placeholder. The actual test must manage this state.
        # This mock would need to understand the select_statement for a generic case.
        # For now, the test will have to set this up.
        # Let's assume there's a way to get the offer_id from the select statement
        # For now, the test will pass the created offer directly to the mock
        return MockResult(None) # Default to None, test should override this mock

    mock_session_instance.get = mock_get_offer
    mock_session_instance.exec = MagicMock(side_effect=lambda stmt: MockResult(db_offers.get(stmt.whereclause.right.value)))
    mock_session_instance.add = MagicMock(side_effect=lambda obj: db_offers.update({obj.id: obj}))
    mock_session_instance.commit = MagicMock()
    mock_session_instance.refresh = MagicMock()

    # This will be returned when `with Session(engine) as session:` is called
    mock_session_manager = MagicMock()
    mock_session_manager.__enter__.return_value = mock_session_instance
    mock_session_manager.__exit__.return_value = None

    # Patch the Session constructor used in `with Session(engine) as session:`
    monkeypatch.setattr("services.valuation.worker.Session", lambda _: mock_session_manager)
    return mock_session_instance, db_offers # Return db_offers to allow test to populate it

@pytest.fixture
def mock_kafka_producer():
    mock_producer_instance = MagicMock()
    mock_producer_instance.produce = MagicMock()
    mock_producer_instance.flush = MagicMock()
    # Patch the global kafka_producer variable in worker.py
    with patch('services.valuation.worker.kafka_producer', new=mock_producer_instance):
         yield mock_producer_instance

@patch("services.valuation.worker.get_spotify_artist_data") # Mock this helper too
def test_run_valuation_success(
    mock_get_spotify_data, 
    mock_offer_session, 
    mock_valuation_model, 
    # mock_redis_client, # Already patched globally by fixture if needed for get_spotify_artist_data
    mock_kafka_producer # Kafka producer is now globally patched
):
    mock_sql_session, db_offers_dict = mock_offer_session
    _, model_mock = mock_valuation_model # Get the model mock itself

    # 1. Prepare mock data and inputs
    test_offer_id = uuid.uuid4()
    test_creator_id = 1 # Assuming int for Creator PK for now
    
    mock_creator = Creator(
        id=test_creator_id, 
        platform_id="test_artist_id", 
        platform_name="spotify", 
        username="testartist",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    mock_offer = Offer(
        id=test_offer_id, 
        creator_id=test_creator_id, 
        title="Test Offer", 
        status="PENDING_VALUATION",
        creator=mock_creator, # Link creator for the task logic
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
        # Ensure all fields required by OfferRead etc. are present if used in task
    )
    db_offers_dict[test_offer_id] = mock_offer # Put the offer in our mock DB

    # Mock what get_spotify_artist_data returns
    mock_get_spotify_data.return_value = {
        "id": "test_artist_id",
        "name": "Test Artist",
        "followers": {"total": 123456},
        "available_markets": ["US", "GB", "DE"]
        # ... other fields expected by process_data_for_features
    }
    
    # 2. Run the task
    result = run_valuation(str(test_offer_id))

    # 3. Assertions
    assert result["status"] == "success"
    assert result["offer_id"] == str(test_offer_id)

    # Check if offer was updated in "DB"
    updated_offer_in_db = db_offers_dict[test_offer_id]
    assert updated_offer_in_db.status == "OFFER_READY"
    assert updated_offer_in_db.price_low_eur == 10000
    assert updated_offer_in_db.price_median_eur == 15000
    assert updated_offer_in_db.price_high_eur == 20000
    assert updated_offer_in_db.valuation_confidence == 0.85

    # Check SQLModel session calls
    # mock_sql_session.get.assert_called_once_with(Offer, test_offer_id)
    # With the change to select().where(), this assertion is harder. 
    # We trust the db_offers_dict mechanism for this test.
    mock_sql_session.add.assert_called_with(updated_offer_in_db)
    mock_sql_session.commit.assert_called_once()

    # Check Spotify call (via the mocked get_spotify_artist_data)
    mock_get_spotify_data.assert_called_once_with("test_artist_id")

    # Check model prediction call
    model_mock.predict.assert_called_once()
    # Can add more specific assertions on the DataFrame passed to predict if needed

    # Check Kafka publish (via the globally mocked kafka_producer)
    mock_kafka_producer.produce.assert_called_once()
    args, kwargs = mock_kafka_producer.produce.call_args
    assert args[0] == "offer.valuated"
    event_payload = json.loads(args[2]) # value is the 3rd arg (idx 2) in confluent_kafka
    assert event_payload["offer_id"] == str(test_offer_id)
    assert event_payload["status"] == "OFFER_READY"

# Add more tests: offer not found, model load failure (if not global), prediction error, Spotify API error etc.

# Example test for Celery task registration (optional)
def test_task_registered():
    assert "services.valuation.worker.run_valuation" in celery_app.tasks 