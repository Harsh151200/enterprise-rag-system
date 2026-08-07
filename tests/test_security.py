from fastapi.testclient import TestClient
from app import app
from core.config import settings

client = TestClient(app)

def test_health_check_is_public():
    # The health check must remain public for GCP load balancers
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_protected_route_without_api_key():
    # Attempting to hit the status endpoint without a key should fail
    response = client.get("/api/v1/status")
    assert response.status_code == 401

def test_protected_route_with_invalid_api_key():
    # Attempting to hit the status endpoint with a bad key should fail
    response = client.get("/api/v1/status", headers={"X-API-Key": "invalid-key"})
    assert response.status_code == 401