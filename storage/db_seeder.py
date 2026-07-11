import os
import json
import psycopg2
from psycopg2.extras import execute_values
from core.config import settings

def chunked_batch_generator(data_list, batch_size=250):
    for i in range(0, len(data_list), batch_size):
        yield data_list[i : i + batch_size]

def seed_database_at_scale(batch_size=250):
    print("[INFO] Initializing Scaled Database Batch Seeding Engine...")
    
    sandbox_dir = os.getenv("RAW_DATA_DIR", "data_sandbox/")
    json_path = os.path.join(sandbox_dir, "processed_embeddings.json")
    if not os.path.exists(json_path):
        print(f"[ERROR] Master seed payload file not found at {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        embedding_records = json.load(f)
        
    total_records = len(embedding_records)
    print(f"[INFO] Successfully extracted {total_records} high-dimensional vector records.")

    try:
        conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
        cursor = conn.cursor()

        print("[INFO] Clearing stale table records and preparing extensions...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cursor.execute("TRUNCATE TABLE sklearn_docs;")
        conn.commit()

        print("[INFO] Reformatting vector structures into schema injection tuples...")
        data_tuples = [
            (
                record["id"],
                record["text_content"],
                record.get("source_file", "unknown_source.txt"),
                record["embedding"],
                record.get("format", "html"),
                record.get("chunk_index", 0)
            )
            for record in embedding_records
        ]

        insert_query = """
            INSERT INTO sklearn_docs (id, text_content, source_file, embedding, doc_format, chunk_index)
            VALUES %s;
        """
        
        processed_counter = 0
        for batch in chunked_batch_generator(data_tuples, batch_size=batch_size):
            execute_values(cursor, insert_query, batch, template="(%s, %s, %s, %s::vector, %s, %s)")
            conn.commit()
            processed_counter += len(batch)
            print(f"   [SUCCESS] Chunk write successful. Rows synced: {processed_counter}/{total_records}")

    except Exception as e:
        print(f"[ERROR] Critical Scaled Database Ingestion Aborted: {e}")
        if 'conn' in locals(): conn.rollback()
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    seed_database_at_scale(batch_size=250)