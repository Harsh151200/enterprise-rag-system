import os
import json
import psycopg2
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def seed_vector_database():
    #1. Load the json payload genrated in phase 2:transformation and embeddings
    json_path = os.path.join(os.getenv("RAW_DATA_DIR", "data_sandbox/"), "processed_embeddings.json")

    if not os.path.exists(json_path):
        print(f"!Error: {json_path} missing. Please execute Phase 2 first.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    # 2. Connect to PostgreSQL database
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )

        cursor = conn.cursor()

        # CRITICAL STEP: Register pgvector extension within the psycopg2 connection instance
        register_vector(conn)


        # 3. Enable pgvector extension inside the Postgres Engine
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()

        # 4. Create the schema table to house our structural semantic entries
        cursor.execute("DROP TABLE IF EXISTS sklearn_docs;")
        cursor.execute("""
            CREATE TABLE sklearn_docs (
                id INT PRIMARY KEY,
                text_content TEXT NOT NULL,
                embedding VECTOR(1536) NOT NULL
            );
        """)

        conn.commit()

        print("Database schema built. Table 'sklearn_docs' initialized.")

        # 5. Execute highly-optimized batch insertions
        print(f"Seeding database with {len(records)} records...")

        # Prepare data tuple mapping list
        insert_data = [(r['id'], r['text_content'], r['embedding']) for r in records]
        
        # execute_values is dramatically faster than looped singular INSERT queries
        query = "INSERT INTO sklearn_docs (id, text_content, embedding) VALUES %s"
        execute_values(cursor, query, insert_data)

        print("Database Seeding Complete! All vectors safely indexed inside Postgres.")
        
        conn.commit()

    except Exception as e:
        print(f"Database error: {e}")

    finally:
        if cursor in locals(): #locals gives us list of local variables
            cursor.close()
        if conn in locals():
            conn.close()

if __name__ == "__main__":
    seed_vector_database()