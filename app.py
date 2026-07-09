import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from components.orchestrator import generate_rag_response
from core.config import settings


# 1. Initialize the FastAPI Application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION
)

# 2. Define the expected incoming JSON schema using Pydantic
class QueryRequest(BaseModel):
    question: str

# 3. Define the structural outgoing JSON response schema
class QueryResponse(BaseModel):
    question: str
    answer: str

# # 4. Create an operational health-check endpoint (Standard enterprise practice)
# @app.get("/health")
# def health_check():
#     return {"status": "healthy", "database_gateway": "online"}


# =========================================================================
# MONITORING LAYER: SYSTEM HEALTH & VERSION CONTROL GATE
# =========================================================================
@app.get("/health", tags=["Monitoring"])
async def health_check():
    """
    Exposes system vitals and the running SemVer string. 
    Used by Cloud Run health probes and deployment validation scripts.
    """
    return {
        "status": "HEALTHY",
        "environment": settings.APP_ENV,
        "version": settings.APP_VERSION,
        "embedding_mode": settings.EMBEDDING_MODE
    }

# 5. Create the primary POST endpoint for RAG queries
@app.post("/api/v1/query", response_model=QueryResponse)
async def query_rag_system(payload: QueryRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question payload cannot be empty.")
        
    try:
        print(f"API Gateway: Received web query request: '{payload.question}'")
        # Trigger the orchestrator loop
        ai_response = generate_rag_response(payload.question)
        
        return QueryResponse(
            question=payload.question,
            answer=ai_response
        )
    except Exception as e:
        print(f"API Internal Server Error: {e}")
        raise HTTPException(status_code=500, detail="Internal orchestration processing failure.")

if __name__ == "__main__":
    # Standard local hosting configurations
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)