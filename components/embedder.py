import os
from ingestion.connectors import LocalDirectoryConnector
from ingestion.pipeline import IngestionPipeline
from components.embedding_provider import embedding_engine
from storage.db_seeder import prepare_database_table, insert_staged_vector_batch

def run_production_ingestion_pipeline(target_directory: str, embedding_batch_size: int = 50) -> None:
    """
    The central operational harness that stitches stream connectors, 
    parsers, batch embedders, and transactional database loaders together.
    """
    print("[ORCHESTRATOR] Initializing global pluggable ETL pipeline execution flow...")
    
    # Initialize database state and tables
    prepare_database_table()

    # Instantiate our streaming data connectors and pipeline traffic managers
    connector = LocalDirectoryConnector(directory_path=target_directory)
    file_stream = connector.fetch_all()
    pipeline = IngestionPipeline()

    global_chunk_id = 1
    processed_file_counter = 0
    staged_chunk_buffer = []

    print(f"[ORCHESTRATOR] Spawning memory-safe file stream loops over: {target_directory}")
    print("-" * 80)

    # Stream files one by one via generators to prevent memory accumulation
    for file_obj in file_stream:
        processed_file_counter += 1
        filepath = file_obj["source"]
        file_bytes = file_obj["bytes"]

        # Run file payloads through deduplication, parsing routing, and semantic transformation
        chunks = pipeline.process_file(filepath, file_bytes)
        
        for chunk in chunks:
            chunk["id"] = global_chunk_id
            staged_chunk_buffer.append(chunk)
            global_chunk_id += 1

            # Dispatch batch array to the abstract embedding vendor when the buffer fills
            if len(staged_chunk_buffer) >= embedding_batch_size:
                _execute_vector_batch_load(staged_chunk_buffer)
                staged_chunk_buffer = [] # Flush memory allocation immediately

    # Process any remaining records left inside the buffer array
    if staged_chunk_buffer:
        _execute_vector_batch_load(staged_chunk_buffer)

    print("-" * 80)
    print("[ORCHESTRATOR] Ingestion cycle execution finalized successfully.")
    print(f"[ORCHESTRATOR] Evaluated distinct resource files: {processed_file_counter}")
    print(f"[ORCHESTRATOR] Vectorized chunks synced to database instances: {global_chunk_id - 1}")


def _execute_vector_batch_load(chunk_buffer: list[dict]) -> None:
    """Helper method that isolates, embeds, and seeds a collection chunk stream."""
    print(f"[ORCHESTRATOR] Shipping vector chunk array segment. Size bounds: {len(chunk_buffer)}")
    
    # Extract structural text lists for our abstract dependency injection engine
    text_payloads = [record["text_content"] for record in chunk_buffer]
    
    try:
        # Generate model embeddings via our unified abstract engine
        vector_matrices = embedding_engine.embed_batch(text_payloads)
        
        # Maps coordinates back to their matching document objects
        for index, coordinates in enumerate(vector_matrices):
            chunk_buffer[index]["embedding"] = coordinates
            
        # Stream computed matrix records straight to PostgreSQL bulk inserter
        insert_staged_vector_batch(chunk_buffer)
        print(f"   [SYNC SUCCESS] Transmitted chunk boundaries up to unique ID: {chunk_buffer[-1]['id']}")
    except Exception as err:
        print(f"[CRITICAL ERR] Pipeline processing step failed at batch chunk sequence: {err}")