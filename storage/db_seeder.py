import os
import json
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Check an environmental flag set by your terminal (defaulting to local development)
app_env = os.getenv("APP_ENV", "development")

# Dynamically route the runtime configurations file path
if app_env == "production":
    load_dotenv(".env.production")
    print("[CONFIG]: System successfully bound to PRODUCTION environment.")
else:
    load_dotenv(".env")
    print("[CONFIG]: System successfully bound to LOCAL DEVELOPMENT environment.")


def seed_mass_vector_database():
    sandbox_dir = os.getenv("RAW_DATA_DIR", "data_sandbox/")
    embeddings_json_path = os.path.join(sandbox_dir, "processed_embeddings.json")
    
    # 1. Structural Validation Guardrail
    if not os.path.exists(embeddings_json_path):
        print(f"Error: Processed embeddings ledger '{embeddings_json_path}' not found.")
        return
        
    with open(embeddings_json_path, "r", encoding="utf-8") as f:
        vector_data = json.load(f)
        
    if not vector_data:
        print("Warning: The embeddings file is empty. Nothing to seed.")
        return

    # Extract database credentials
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    
    print(f"🔌 Initializing connection to Postgres Target Container [{db_host}:{db_port}]...")
    
    try:
        connection = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        cursor = connection.cursor()
        
        # 2. Prevent Data Duplication (Wipe old PoC records cleanly)
        print("Clearing out legacy tracking records from 'sklearn_docs' table...")
        cursor.execute("TRUNCATE TABLE sklearn_docs;")
        
        # 3. Prepare the Mass Batch Ingestion Payload List
        # We restructure the JSON items into a flat list of tuples for psycopg2
        db_records_batch = [
            (record["id"], record["source_file"], record["text_content"], record["embedding"])
            for record in vector_data
        ]
        
        # Explicitly cast the incoming float list to a vector type (%s::vector)
        insert_query = """
            INSERT INTO sklearn_docs (id, source_file, text_content, embedding)
            VALUES %s;
        """
        
        print(f"⚡ Bulk-inserting {len(db_records_batch)} vector arrays into the data core...")
        
        # execute_values executes a single optimized compilation query behind the scenes
        execute_values(
            cursor, 
            insert_query, 
            db_records_batch, 
            template="(%s, %s, %s, %s::vector)"
        )
        
        # Commit transaction to disk
        connection.commit()
        
        print("=" * 60)
        print(f"Database Seeding Milestone Complete!")
        print(f"Total Active Rows Injected and Indexed: {len(db_records_batch)}")
        print("=" * 60)
        
    except Exception as e:
        print(f"Database Transaction Processing Failure: {e}")
        if 'connection' in locals():
            connection.rollback()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    seed_mass_vector_database()