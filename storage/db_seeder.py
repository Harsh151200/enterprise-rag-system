import psycopg2
from psycopg2.extras import execute_values
from core.config import settings

def chunked_batch_generator(data_list, batch_size=250):
    """Yields successive managed slices from the data array to protect memory limits."""
    for i in range(0, len(data_list), batch_size):
        yield data_list[i : i + batch_size]

def prepare_database_table() -> None:
    """
    Ensures pgvector is active, configures an automated full-text tsvector 
    column with an optimized GIN index, and prepares tables for seeding.
    """
    print("[DATABASE] Running structural verification and advanced hybrid migrations...")
    try:
        conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
        cursor = conn.cursor()
        
        # 1. Activate spatial matrix extensions
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # # 2. Build multi-format lineage tracking properties
        # cursor.execute("ALTER TABLE sklearn_docs ADD COLUMN IF NOT EXISTS doc_format VARCHAR(50) DEFAULT 'html';")
        # cursor.execute("ALTER TABLE sklearn_docs ADD COLUMN IF NOT EXISTS chunk_index INTEGER DEFAULT 0;")
        
        # 3. Inject an automated stored full-text search vector column
        cursor.execute("""
            ALTER TABLE sklearn_docs ADD COLUMN IF NOT EXISTS text_vector tsvector 
            GENERATED ALWAYS AS (to_tsvector('english', text_content)) STORED;
        """)
        
        # 4. Generate high-speed inverted keyword lookups indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS sklearn_docs_fts_idx ON sklearn_docs USING gin(text_vector);")
        
        # 5. Flush existing data rows for a clean indexing run
        cursor.execute("TRUNCATE TABLE sklearn_docs;")
        
        conn.commit()
        print("[DATABASE] Hybrid schema definitions and structural indexes compiled successfully.")
    except Exception as e:
        print(f"[DATABASE ERROR] Baseline hybrid database setup failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise e
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

def insert_staged_vector_batch(batch_records: list[dict], internal_batch_size: int = 250) -> None:
    """
    Accepts raw text and vector objects from live memory, slices them into 
    controlled sub-batches, and safely commits them to PostgreSQL.
    """
    if not batch_records:
        return

    total_records = len(batch_records)
    print(f"[DATABASE] Received {total_records} records for indexing. Preparing inner batch slicing...")

    data_tuples = [
        (
            record["id"],
            record["text_content"],
            record.get("source_file", "unknown_source.txt"),
            record["embedding"],
            record.get("format", "txt"),
            record.get("chunk_index", 0)
        )
        for record in batch_records
    ]

    insert_query = """
        INSERT INTO sklearn_docs (id, text_content, source_file, embedding, doc_format, chunk_index)
        VALUES %s;
    """

    try:
        conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
        cursor = conn.cursor()
        
        processed_counter = 0
        for sub_batch in chunked_batch_generator(data_tuples, batch_size=internal_batch_size):
            execute_values(cursor, insert_query, sub_batch, template="(%s, %s, %s, %s::vector, %s, %s)")
            conn.commit()
            processed_counter += len(sub_batch)
            print(f"   [SYNC PROGRESS] Safe sub-batch written. Rows synced: {processed_counter}/{total_records}")

    except Exception as e:
        print(f"[DATABASE ERROR] High-speed database bulk seed transaction aborted: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise e
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()