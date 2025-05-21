import pytest
from fastapi.testclient import TestClient
from services.spacemusic.main import app # Assuming spacemusic service is in PYTHONPATH

client = TestClient(app)

def test_read_root_spacemusic(): # Renamed to be more specific if other API tests exist
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to SpaceMusic Service"}

# Add more tests for the spacemusic API here 