import os
import json
import psycopg2
from psycopg2.extras import execute_values
from core.config import settings

def chunked_batch_generator(data_list, batch_size=250):
    """Yield successive managed slices from the master dataset array."""
    for i in range(0, len(data_list), batch_size):
        yield data_list[i : i + batch_size]

def seed_database_at_scale(batch_size=250):
    print("Initializing Scaled Database Batch Seeding Engine...")
    
    # 1. Locate the 400MB processed embeddings matrix
    sandbox_dir = os.getenv("RAW_DATA_DIR", "data_sandbox/")
    json_path = os.path.join(sandbox_dir, "processed_embeddings.json")
    if not os.path.exists(json_path):
        print(f"Error: Master seed payload file not found at {json_path}")
        return

    print("Loading JSON catalog file into local memory memory workspace...")
    with open(json_path, "r", encoding="utf-8") as f:
        embedding_records = json.load(f)
        
    total_records = len(embedding_records)
    print(f"Successfully extracted {total_records} high-dimensional vector records.")
    print(f"Target Profile Environment: {settings.APP_ENV} | Batch Slice Bounds: {batch_size}")

    # 2. Open our connection canal via our centralized Pydantic settings layer
    try:
        conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
        cursor = conn.cursor()

        # 3. Purge historical records to prepare for a clean indexing run
        print("Clearing stale table records and preparing extensions...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cursor.execute("TRUNCATE TABLE sklearn_docs;")
        conn.commit() # Flush truncation immediately

        # 4. Restructure records into optimized execution lists
        print("Reformatting vector structures into schema injection tuples...")
        data_tuples = [
            (
                record["id"],
                record["text_content"],
                record.get("source_file", "unknown_source.txt"),
                record["embedding"] # Our 1536-dimension float coordinate array
            )
            for record in embedding_records
        ]

        # 5. Execute Generative Batch Streaming
        insert_query = """
            INSERT INTO sklearn_docs (id, text_content, source_file, embedding)
            VALUES %s;
        """
        
        print(f"Streaming data arrays in safe batch blocks of {batch_size} rows...")
        processed_counter = 0
        
        for batch in chunked_batch_generator(data_tuples, batch_size=batch_size):
            # execute_values compiles multiple rows into a single high-speed bulk INSERT string
            execute_values(cursor, insert_query, batch, template="(%s, %s, %s, %s::vector)")
            
            # CRITICAL STEP: Commit every batch immediately to flush Cloud SQL memory limits
            conn.commit()
            
            processed_counter += len(batch)
            print(f"Progress Milestone: Chunk write successful. Rows synced: {processed_counter}/{total_records}")

        print(f"\nMETRIC ACHIEVEMENT: All {total_records} records successfully seeded into the core instance!")

    except Exception as e:
        print(f"Critical Scaled Database Ingestion Aborted: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    # Slicing at 250 rows balancing network transmission packet speed with memory isolation
    seed_database_at_scale(batch_size=250)