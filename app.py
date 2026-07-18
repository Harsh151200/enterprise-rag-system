import sys
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from core.config import settings
from components.embedder import run_production_ingestion_pipeline
from components.orchestrator import generate_rag_response
from storage.analytics import get_platform_status_metrics, get_historical_pipeline_logs

app = FastAPI(title="Enterprise RAG Core Service Platform", version="3.0.0-alpha.4")

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

@app.get("/api/v1/status", status_code=status.HTTP_200_OK)
def get_repository_status() -> Dict[str, Any]:
    """Exposes aggregated storage status array statistics by consuming the unified analytics layer."""
    try:
        return get_platform_status_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/logs", status_code=status.HTTP_200_OK)
def get_pipeline_audit_logs() -> List[Dict[str, Any]]:
    """Returns historical execution parameters pulled directly from the audit ledger rows."""
    try:
        return get_historical_pipeline_logs(limit=10)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/query", status_code=status.HTTP_200_OK)
def process_hybrid_query(payload: QueryRequest) -> Dict[str, Any]:
    """Processes search queries and returns structured answer and citation arrays."""
    try:
        result = generate_rag_response(user_query=payload.question)
        return {
            "query": payload.question, 
            "answer": result["answer"], 
            "citations": result["citations"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/ingest", status_code=status.HTTP_202_ACCEPTED)
def trigger_pipeline_ingestion(payload: IngestRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    try:
        background_tasks.add_task(
            run_production_ingestion_pipeline,
            source_type=payload.source_type, target_path=payload.target_path,
            embedding_batch_size=payload.batch_size, max_resources=payload.limit
        )
        return {"status": "accepted", "message": "Pipeline routine scheduled into worker threads successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))