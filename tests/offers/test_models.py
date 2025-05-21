import pytest
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel, Session

# Adjust import to your actual models file location if needed
# This assumes that services/offers is in PYTHONPATH or tests are run from project root
from services.offers.models import Creator, Offer

# In-memory SQLite database for testing
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL)

@pytest.fixture(scope="function")
def setup_db():
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)

def test_creator_table_exists_and_columns(setup_db):
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "creator" in tables

    columns = inspector.get_columns("creator")
    column_names = [col['name'] for col in columns]

    assert "id" in column_names
    assert "platform_id" in column_names
    assert "platform_name" in column_names
    assert "username" in column_names
    assert "display_name" in column_names
    assert "created_at" in column_names
    assert "updated_at" in column_names

    # Check some constraints (example for unique)
    # This is a bit more involved and might require checking indexes or unique constraints directly
    # For platform_id, which should be unique:
    indexes = inspector.get_indexes('creator')
    platform_id_index = next((idx for idx in indexes if idx['column_names'] == ['platform_id']), None)
    assert platform_id_index is not None
    assert platform_id_index['unique'] == True # SQLModel creates unique=True for sa.Column(unique=True)

def test_offer_table_exists_and_columns(setup_db):
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "offer" in tables

    columns = inspector.get_columns("offer")
    column_names = [col['name'] for col in columns]

    assert "id" in column_names
    assert "creator_id" in column_names
    assert "title" in column_names
    assert "description" in column_names
    assert "amount_cents" in column_names
    assert "currency_code" in column_names
    assert "status" in column_names
    assert "created_at" in column_names
    assert "updated_at" in column_names

    # Check foreign key
    foreign_keys = inspector.get_foreign_keys('offer')
    creator_fk = next((fk for fk in foreign_keys if fk['constrained_columns'] == ['creator_id']), None)
    assert creator_fk is not None
    assert creator_fk['referred_table'] == 'creator'
    assert creator_fk['referred_columns'] == ['id']

# You can add more tests here, e.g. creating instances and checking relationships 