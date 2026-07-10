import os
import json
import psycopg2
from core.config import settings

def seed_database():
    print("Starting Database Seeding Service...")
    
    # 1. Resolve local sandbox paths
    sandbox_dir = os.getenv("RAW_DATA_DIR", "data_sandbox/")
    json_path = os.path.join(sandbox_dir, "processed_embeddings.json")
    if not os.path.exists(json_path):
        print(f"Error: Seed payload data file not found at {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        embedding_records = json.load(f)
        
    total_records = len(embedding_records)
    print(f"Successfully parsed {total_records} vector records from local staging index.")
    print(f"Target Environment Connection Profile: {settings.APP_ENV}")

    # 2. Establish connection using the unified Pydantic database URI
    try:
        conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
        cursor = conn.cursor()

        # 3. Clean table state and ensure pgvector extension is present
        print("Initializing table state... Registering extensions and purging old data...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cursor.execute("TRUNCATE TABLE sklearn_docs;")
        conn.commit()

        # 4. Construct the query execution tuple structure
        data_tuples = []
        for record in embedding_records:
            data_tuples.append((
                record["id"],
                record["text_content"],
                record.get("source_file", "unknown_source.txt"),
                record["embedding"] # The 1536-dimensional array
            ))

        print("Executing monolithic bulk insertion stream into Cloud SQL...")
        insert_query = """
            INSERT INTO sklearn_docs (id, text_content, source_file, embedding)
            VALUES (%s, %s, %s, %s::vector);
        """

        # Execute structural bulk injection execution
        cursor.executemany(insert_query, data_tuples)
        conn.commit() 

        print(f"\nSUCCESS! All {total_records} records successfully seeded into the target database instance!")

    except Exception as e:
        print(f"Critical Database Seed Transaction Aborted: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    seed_database()