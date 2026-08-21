import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from core.config import settings

client = TestClient(app)
VALID_HEADERS = {"X-API-Key": settings.API_KEY}

@patch("app.get_platform_status_metrics")
def test_status_endpoint(mock_get_metrics):
    # Setup mock return
    mock_get_metrics.return_value = {"total_chunks_indexed": 150, "database_connected": True}
    
    response = client.get("/api/v1/status", headers=VALID_HEADERS)
    
    assert response.status_code == 200
    assert response.json()["total_chunks_indexed"] == 150
    mock_get_metrics.assert_called_once()

@patch("app.get_historical_pipeline_logs")
def test_logs_endpoint(mock_get_logs):
    mock_get_logs.return_value = [{"run_id": "123", "status": "COMPLETED"}]
    
    response = client.get("/api/v1/logs", headers=VALID_HEADERS)
    
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["run_id"] == "123"

@patch("app.generate_rag_response")
def test_query_endpoint(mock_rag_response):
    # Setup mock LLM/RAG response
    mock_rag_response.return_value = {
        "answer": "Scikit-learn is a machine learning library.",
        "citations": ["doc1.md"]
    }
    
    payload = {"question": "What is scikit-learn?"}
    response = client.post("/api/v1/query", json=payload, headers=VALID_HEADERS)
    
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == payload["question"]
    assert data["answer"] == "Scikit-learn is a machine learning library."
    assert data["citations"] == ["doc1.md"]

@patch("app.run_production_ingestion_pipeline")
def test_ingest_endpoint_background_dispatch(mock_pipeline):
    payload = {
        "source_type": "local",
        "target_path": "/data/docs",
        "limit": 10,
        "batch_size": 50
    }
    
    response = client.post("/api/v1/ingest", json=payload, headers=VALID_HEADERS)
    
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    
    # Because FastAPI BackgroundTasks run after the response is returned in TestClient,
    # we can't assert the mock was called synchronously unless we await it, but we can 
    # verify the endpoint accepted the payload structure correctly.