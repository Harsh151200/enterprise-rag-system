import os
from ingestion.connectors import LocalDirectoryConnector, DynamicWebCrawlerConnector
from ingestion.pipeline import IngestionPipeline
from components.embedding_provider import embedding_engine
from storage.db_seeder import prepare_database_table, insert_staged_vector_batch

def run_production_ingestion_pipeline(
    source_type: str = "local", 
    target_path: str = "data_sandbox/test_inputs", 
    embedding_batch_size: int = 50,
    max_resources: int = None
) -> None:
    """
    The master orchestrator upgraded to support pluggable ingestion limits
    across local folder paths or live web documentation networks.
    """
    print(f"[ORCHESTRATOR] Initializing pluggable ETL pipeline execution [Mode: {source_type.upper()}]...")
    
    # Reset database structures and run dynamic migrations
    prepare_database_table()
    pipeline = IngestionPipeline()

    # 1. Pluggable Connector Resolution
    if source_type.lower() == "web":
        # Target the official stable scikit-learn documentation ecosystem
        print(f"[ORCHESTRATOR] Spawning Web Crawler Connector targeting: {target_path}")
        crawler = DynamicWebCrawlerConnector(
            seed_url=target_path,
            domain_lock="scikit-learn.org",
            path_filter="/stable/",
            max_pages=max_resources or 50 # Fallback safety limit if none provided
        )
        file_stream = crawler.crawl_tree()
    else:
        print(f"[ORCHESTRATOR] Spawning Local Directory Connector reading: {target_path}")
        connector = LocalDirectoryConnector(directory_path=target_path)
        file_stream = connector.fetch_all()

    global_chunk_id = 1
    processed_counter = 0
    staged_chunk_buffer = []

    print("-" * 80)

    # 2. Lazy Stream Processing Loop
    for file_obj in file_stream:
        processed_counter += 1
        filepath = file_obj["source"]
        file_bytes = file_obj["bytes"]

        # Run payload through deduplication, formatting parser, and text chunker
        chunks = pipeline.process_file(filepath, file_bytes)
        
        for chunk in chunks:
            chunk["id"] = global_chunk_id
            staged_chunk_buffer.append(chunk)
            global_chunk_id += 1

            # Dispatch batch array when the buffer fills up
            if len(staged_chunk_buffer) >= embedding_batch_size:
                _execute_vector_batch_load(staged_chunk_buffer)
                staged_chunk_buffer = []

        # 3. Pluggable Guardrail Verification
        if max_resources and processed_counter >= max_resources:
            print(f"[GUARDRAIL] Pluggable boundary hit ({max_resources} resources). Truncating stream execution.")
            break

    # Flush any remaining text slices left over in the buffer array
    if staged_chunk_buffer:
        _execute_vector_batch_load(staged_chunk_buffer)

    print("-" * 80)
    print("[ORCHESTRATOR] Ingestion execution cycle concluded successfully.")
    print(f"[ORCHESTRATOR] Total items fully extracted: {processed_counter}")
    print(f"[ORCHESTRATOR] Total database vector rows indexed: {global_chunk_id - 1}")


def _execute_vector_batch_load(chunk_buffer: list[dict]) -> None:
    """Helper method that handles batch text embedding calculations and uploads."""
    print(f"[ORCHESTRATOR] Dispatching vector matrix batch of size: {len(chunk_buffer)}")
    
    # CRITICAL FIX: Prepend Nomic's required document prefix to the text stream
    text_payloads = [f"search_document: {record['text_content']}" for record in chunk_buffer]
    
    try:
        # The model processes the prefixed strings
        vector_matrices = embedding_engine.embed_batch(text_payloads)
        
        for index, coordinates in enumerate(vector_matrices):
            chunk_buffer[index]["embedding"] = coordinates
            
        # The raw (unprefixed) chunks inside chunk_buffer are pushed to the DB
        insert_staged_vector_batch(chunk_buffer, internal_batch_size=250)
        print(f"    [SYNC SUCCESS] Synchronized chunks up to ID: {chunk_buffer[-1]['id']}")
    except Exception as err:
        print(f"[CRITICAL ERROR] Failed processing batch slice chunk sequence: {err}")