import psycopg2
from psycopg2.extras import execute_values
from core.config import settings

def chunked_batch_generator(data_list, batch_size=250):
    """Yields successive managed slices from the data array to protect memory limits."""
    for i in range(0, len(data_list), batch_size):
        yield data_list[i : i + batch_size]

def prepare_database_table() -> None:
    """
    Executes idempotent DDL migrations. Safely initializes extensions, 
    custom types, tables, constraints, and optimized vector/FTS indexes.
    """
    print("[DATABASE] Running complete enterprise schema layout migrations...")
    try:
        conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
        cursor = conn.cursor()
        
        # 1. Initialize core system extensions
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # 2. Check and provision custom enumeration types safely
        cursor.execute("SELECT 1 FROM pg_type WHERE typname = 'pipeline_status_enum';")
        if not cursor.fetchone():
            print("[DATABASE] Creating system custom type: pipeline_status_enum")
            cursor.execute("CREATE TYPE pipeline_status_enum AS ENUM ('RUNNING', 'SUCCESS', 'FAILED');")
        
        # 3. Provision primary document datastore with exact dimension constraint bounds
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS public.enterprise_documents (
                id serial4 NOT NULL,
                text_content text NOT NULL,
                source_file varchar(500) NOT NULL,
                embedding public.vector({settings.EMBEDDING_DIMENSION}) NULL,
                doc_format varchar(50) DEFAULT 'unknown'::character varying NULL,
                chunk_index int4 DEFAULT 0 NULL,
                text_vector tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, text_content)) STORED NULL,
                CONSTRAINT enterprise_documents_pkey PRIMARY KEY (id)
            );
        """)
        
        # 4. Bind structural indexes for the primary document datastore
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS enterprise_documents_embedding_hnsw_idx 
            ON public.enterprise_documents USING hnsw (embedding vector_cosine_ops);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS enterprise_documents_fts_idx 
            ON public.enterprise_documents USING gin (text_vector);
        """)
        
        # 5. Provision the real-time background tracking ledger datastore
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public.pipeline_runs (
                run_id uuid DEFAULT gen_random_uuid() NOT NULL,
                pipeline_name varchar(100) NOT NULL,
                environment varchar(20) NOT NULL,
                status public.pipeline_status_enum DEFAULT 'RUNNING'::pipeline_status_enum NULL,
                records_extracted int4 DEFAULT 0 NULL,
                records_transformed int4 DEFAULT 0 NULL,
                records_indexed int4 DEFAULT 0 NULL,
                started_at timestamptz DEFAULT CURRENT_TIMESTAMP NULL,
                completed_at timestamptz NULL,
                error_message text NULL,
                CONSTRAINT pipeline_runs_pkey PRIMARY KEY (run_id)
            );
        """)
        
        # 6. Bind optimized operational lookup tracking indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started 
            ON public.pipeline_runs USING btree (started_at DESC);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status 
            ON public.pipeline_runs USING btree (status);
        """)
        
        conn.commit()
        print("[DATABASE] Full relational enterprise schema and indices are synchronized.")
    except Exception as e:
        print(f"[DATABASE ERROR] Structural schema migration execution collapsed: {e}")
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

    # FIXED: Dropped the explicit record["id"] key assignment
    data_tuples = [
        (
            record["text_content"],
            record.get("source_file", "unknown_source.txt"),
            record["embedding"],
            record.get("doc_format", record.get("format", "unknown")),
            record.get("chunk_index", 0)
        )
        for record in batch_records
    ]

    # FIXED: Omitted explicit id insertion to let PostgreSQL handle auto-increment native sequences
    insert_query = """
        INSERT INTO enterprise_documents (text_content, source_file, embedding, doc_format, chunk_index)
        VALUES %s;
    """

    try:
        conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
        cursor = conn.cursor()
        
        processed_counter = 0
        for sub_batch in chunked_batch_generator(data_tuples, batch_size=internal_batch_size):
            execute_values(cursor, insert_query, sub_batch, template="(%s, %s, %s::vector, %s, %s)")
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