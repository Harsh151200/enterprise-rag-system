import psycopg2
from core.config import settings
from components.embedding_provider import embedding_engine

def hybrid_search(user_query: str, top_k: int = 4, oversample_factor: int = 5) -> list[dict]:
    """
    Executes a parallel hybrid search across both full-text keywords and 
    dense vector embedding dimensions within a single PostgreSQL query transaction,
    blending results via a database-calculated Reciprocal Rank Fusion (RRF) algorithm.
    """
    # 1. Generate spatial coordinates from the user query string
    try:
        query_vector = embedding_engine.embed_text(user_query)
    except Exception as e:
        print(f"[RETRIEVAL ERROR] Failed to compute spatial vector representation: {e}")
        return []

    # Calculate a wider candidate window to give both search strategies room to blend
    candidate_limit = top_k * oversample_factor

    # 2. Unified Dual-Strategy CTE RRF Query Construction
    rrf_query = """
        WITH vector_search AS (
            SELECT id, 
                   ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank
            FROM enterprise_documents
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        ),
        fts_search AS (
            SELECT id, 
                   ROW_NUMBER() OVER (ORDER BY ts_rank_cd(text_vector, plainto_tsquery('english', %s)) DESC) AS rank
            FROM enterprise_documents
            WHERE text_vector @@ plainto_tsquery('english', %s)
            ORDER BY ts_rank_cd(text_vector, plainto_tsquery('english', %s)) DESC
            LIMIT %s
        )
        SELECT 
            d.text_content, 
            d.source_file, 
            d.doc_format, 
            d.chunk_index,
            COALESCE(1.0 / (60.0 + v.rank), 0.0) + COALESCE(1.0 / (60.0 + f.rank), 0.0) AS rrf_score
        FROM enterprise_documents d
        LEFT JOIN vector_search v ON d.id = v.id
        LEFT JOIN fts_search f ON d.id = f.id
        WHERE v.id IS NOT NULL OR f.id IS NOT NULL
        ORDER BY rrf_score DESC
        LIMIT %s;
    """

    # 3. Transaction Execution Block
    try:
        conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
        cursor = conn.cursor()

        # Safely map parameter values directly to query placeholders
        query_parameters = (
            query_vector,       # vector_search window order parameter
            query_vector,       # vector_search sorting parameter
            candidate_limit,    # vector_search depth limit
            user_query,         # fts_search lexeme translation parsing target
            user_query,         # fts_search indexing lookup operator target
            user_query,         # fts_search dense ranking compilation parameter
            candidate_limit,    # fts_search depth limit
            top_k               # Final blended destination limit returning to caller
        )

        # print(rrf_query, query_parameters)

        cursor.execute(rrf_query, query_parameters)
        raw_database_rows = cursor.fetchall()

        # 4. Standardized Output Compilation
        compiled_results = [
            {
                "text": row[0],
                "source": row[1],
                "format": row[2],
                "chunk_index": row[3],
                "rrf_score": float(row[4])
            }
            for row in raw_database_rows
        ]

        print(f"[RETRIEVAL] Hybrid search completed successfully. Total results returned: {len(compiled_results)}")
        
        return compiled_results

    except Exception as e:
        print(f"[RETRIEVAL ERROR] Parallel hybrid search matrix transaction collapsed: {e}")
        return []
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()