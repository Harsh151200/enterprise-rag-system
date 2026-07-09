import psycopg2
from core.config import settings
from components.embedding_provider import embedding_engine

def semantic_search(user_query: str, top_k: int = 3) -> list[dict]:
    """
    Translates a user query into a vector using the abstract provider, 
    then fetches the most semantically relevant documentation blocks from Cloud SQL.
    """
    # 1. Route the query string through the abstract embedding provider
    try:
        query_vector = embedding_engine.embed_text(user_query)
    except Exception as e:
        print(f"Retrieval Error: Failed to embed user query. Details: {e}")
        return []

    # 2. Establish connection using the Pydantic validated environment URI
    try:
        conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
        cursor = conn.cursor()
        
        # Note: The <=> operator computes cosine distance natively in pgvector.
        # We explicitly cast to ::vector to ensure strict PostgreSQL data type matching.
        search_query = """
            SELECT text_content, source_file 
            FROM sklearn_docs 
            ORDER BY embedding <=> %s::vector 
            LIMIT %s;
        """
        
        cursor.execute(search_query, (query_vector, top_k))
        results = cursor.fetchall()
        
        # 3. Format and return the dictionary list matching the orchestrator's expectations
        retrieved_records = [
            {"text": row[0], "source": row[1]} for row in results
        ]
        
        return retrieved_records

    except Exception as e:
        print(f"Database Retrieval Execution Failed: {e}")
        return []
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()