import os
import psycopg2
from ingestion.connectors import LocalDirectoryConnector, DynamicWebCrawlerConnector
from ingestion.pipeline import IngestionPipeline
from components.embedding_provider import embedding_engine
from storage.db_seeder import insert_staged_vector_batch
from storage.pipeline_logger import PipelineLogger
from core.config import settings

def _is_file_already_processed(source_file: str) -> bool:
    """
    Executes a fast query against the database to check if a document 
    has already been indexed, preventing redundant API calls and duplicate data.
    """
    query = "SELECT 1 FROM enterprise_documents WHERE source_file = %s LIMIT 1;"
    try:
        conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
        cursor = conn.cursor()
        cursor.execute(query, (source_file,))
        exists = cursor.fetchone() is not None
        return exists
    except Exception as e:
        print(f"[DEDUPLICATION WARNING] Database check failed: {e}")
        return False
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()


def run_production_ingestion_pipeline(
    source_type: str = "local", 
    target_path: str = "data_sandbox/test_inputs", 
    embedding_batch_size: int = 100,
    max_resources: int = None
) -> None:
    """
    The master EMBEDDER orchestrator upgraded to support pluggable ingestion limits,
    database-backed deduplication safeguards, and live run auditing metrics.
    """
    # 1. Initialize audit log session entry
    audit_logger = PipelineLogger()
    run_id = audit_logger.start_run(pipeline_name=f"ETL_INGESTION_{source_type.upper()}")

    chunk_counter = 0
    processed_counter = 0
    skipped_counter = 0
    staged_chunk_buffer = []

    try:
        print(f"[EMBEDDER] Initializing pluggable ETL pipeline execution [Run ID: {run_id}, Mode: {source_type.upper()}]...")
        
        pipeline = IngestionPipeline()

        # Pluggable Connector Resolution
        if source_type.lower() == "web":
            print(f"[EMBEDDER] Spawning Web Crawler Connector targeting: {target_path}")
            crawler = DynamicWebCrawlerConnector(
                seed_url=target_path,
                domain_lock="scikit-learn.org",
                path_filter="/stable/",
                max_pages=max_resources or 50
            )
            file_stream = crawler.crawl_tree()
        else:
            print(f"[EMBEDDER] Spawning Local Directory Connector reading: {target_path}")
            connector = LocalDirectoryConnector(directory_path=target_path)
            file_stream = connector.fetch_all()

        print("-" * 80)

        # 2. Lazy Stream Processing Loop
        for file_obj in file_stream:
            filepath = file_obj["source"]
            file_bytes = file_obj["bytes"]

            # Deduplication Guardrail: Skip if already in the database
            if _is_file_already_processed(filepath):
                print(f"   [DEDUPLICATION SKIP] File already indexed in database: {filepath}")
                skipped_counter += 1
                continue

            processed_counter += 1
            
            # Run payload through formatting parser, and text chunker
            chunks = pipeline.process_file(filepath, file_bytes)
            
            for chunk in chunks:
                staged_chunk_buffer.append(chunk)
                chunk_counter += 1

                # Dispatch batch array when the buffer fills up
                if len(staged_chunk_buffer) >= embedding_batch_size:
                    _execute_vector_batch_load(staged_chunk_buffer)
                    staged_chunk_buffer = []

            # Pluggable Guardrail Verification
            if max_resources and processed_counter >= max_resources:
                print(f"[GUARDRAIL] Pluggable boundary hit ({max_resources} resources). Truncating stream execution.")
                break

        # Flush any remaining text slices left over in the buffer array
        if staged_chunk_buffer:
            _execute_vector_batch_load(staged_chunk_buffer)

        print("-" * 80)
        print("[EMBEDDER] Ingestion execution cycle concluded successfully.")
        print(f"[EMBEDDER] Total items skipped (Deduplication): {skipped_counter}")
        print(f"[EMBEDDER] Total new items fully extracted: {processed_counter}")
        print(f"[EMBEDDER] Total new database vector rows indexed: {chunk_counter}")

        # 3. Log a clean SUCCESS state checkpoint to the audit ledger rows
        audit_logger.complete_run(
            run_id=run_id,
            extracted=processed_counter,
            transformed=chunk_counter,
            indexed=chunk_counter
        )

    except Exception as runtime_error:
        print(f"[EMBEDDER CRITICAL FAIL] Ingestion crashed: {runtime_error}")
        # 4. Log the FAILED checkpoint along with error messages to the database
        audit_logger.fail_run(
            run_id=run_id,
            error=runtime_error,
            extracted=processed_counter,
            transformed=chunk_counter,
            indexed=chunk_counter
        )
        raise runtime_error


def _execute_vector_batch_load(chunk_buffer: list[dict]) -> None:
    """Helper method that handles batch text embedding calculations and uploads."""
    print(f"[EMBEDDER] Dispatching vector matrix batch of size: {len(chunk_buffer)}")
    
    # FIXED: The provider engine handles its own task prefix internally to prevent double-prefixing.
    text_payloads = [record['text_content'] for record in chunk_buffer]
    
    try:
        vector_matrices = embedding_engine.embed_batch(text_payloads)
        
        for index, coordinates in enumerate(vector_matrices):
            chunk_buffer[index]["embedding"] = coordinates
            
        insert_staged_vector_batch(chunk_buffer, internal_batch_size=250)
        print("[SYNC SUCCESS] Synchronized chunks to database with vector embeddings.")
    except Exception as err:
        print(f"[CRITICAL ERROR] Failed processing batch slice chunk sequence: {err}")