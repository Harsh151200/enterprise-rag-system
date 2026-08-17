import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Depends, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from core.config import settings
from components.embedder import run_production_ingestion_pipeline
from components.orchestrator import generate_rag_response
from storage.analytics import get_platform_status_metrics, get_historical_pipeline_logs

# Configure internal logger
logger = logging.getLogger(__name__)

app = FastAPI(title="Enterprise RAG Core Service Platform", version="3.0.0-alpha.4")

# --- SECURITY MIDDLEWARE ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return api_key
# ---------------------------

class QueryRequest(BaseModel):
    question: str = Field(..., description="The query string to evaluate")

class IngestRequest(BaseModel):
    source_type: str = Field(..., description="The retrieval connector channel mechanism ('local' or 'web')")
    target_path: str = Field(..., description="The folder location path or seed URL target node")
    limit: Optional[int] = Field(None, description="Optional pluggable resource limit")
    batch_size: int = Field(50, description="The memory buffer limit used during batch vector mapping")

@app.get("/health", status_code=status.HTTP_200_OK)
def system_health_check() -> Dict[str, str]:
    return {"status": "healthy", "environment": settings.APP_ENV}

@app.get("/api/v1/status", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_api_key)])
def get_repository_status() -> Dict[str, Any]:
    try:
        return get_platform_status_metrics()
    except Exception as e:
        logger.error(f"Status endpoint failure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching system status."
        )

@app.get("/api/v1/logs", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_api_key)])
def get_pipeline_audit_logs() -> List[Dict[str, Any]]:
    try:
        return get_historical_pipeline_logs(limit=10)
    except Exception as e:
        logger.error(f"Audit log retrieval failure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pipeline audit logs."
        )

@app.post("/api/v1/query", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_api_key)])
def process_hybrid_query(payload: QueryRequest) -> Dict[str, Any]:
    try:
        result = generate_rag_response(user_query=payload.question)
        return {
            "query": payload.question, 
            "answer": result["answer"], 
            "citations": result["citations"]
        }
    except Exception as e:
        logger.error(f"RAG query execution failed for question: {payload.question} | Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process hybrid query."
        )

@app.post("/api/v1/ingest", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_api_key)])
def trigger_pipeline_ingestion(payload: IngestRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    try:
        background_tasks.add_task(
            run_production_ingestion_pipeline,
            source_type=payload.source_type, 
            target_path=payload.target_path,
            embedding_batch_size=payload.batch_size, 
            max_resources=payload.limit
        )
        return {"status": "accepted", "message": "Pipeline routine scheduled into worker threads successfully."}
    except Exception as e:
        logger.error(f"Ingestion dispatch failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule ingestion routine."
        )