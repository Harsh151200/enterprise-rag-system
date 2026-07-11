import os
import json
from ingestion.connectors import LocalDirectoryConnector
from ingestion.pipeline import IngestionPipeline
from components.embedding_provider import embedding_engine
from storage.db_seeder import seed_database_at_scale

def execute_end_to_end_test():
    print("[TEST] Launching Milestone 2 Verification Execution Cycle...")
    
    # 1. Initialize the Generator Connector
    connector = LocalDirectoryConnector(directory_path="data_sandbox/test_inputs")
    file_stream = connector.fetch_all()

    # 2. Parse and Transform over the stream
    pipeline = IngestionPipeline()
    consolidated_chunks = []
    global_id = 1
    file_counter = 0

    # Iterating over the stream processes files sequentially without memory accumulation
    for file_obj in file_stream:
        file_counter += 1
        filepath = file_obj["source"]
        file_bytes = file_obj["bytes"]
        
        chunks = pipeline.process_file(filepath, file_bytes)
        
        for chunk in chunks:
            chunk["id"] = global_id
            consolidated_chunks.append(chunk)
            global_id += 1

    print(f"[TEST] Stream extraction complete. Discovered and parsed {file_counter} source files.")
    print(f"[TEST] Processing finished. Total chunks generated: {len(consolidated_chunks)}")

    # 3. Save Staged Chunks to disk
    sandbox_dir = "data_sandbox/"
    staged_chunks_path = os.path.join(sandbox_dir, "staged_chunks.json")
    with open(staged_chunks_path, "w", encoding="utf-8") as f:
        json.dump(consolidated_chunks, f, indent=4)

    # 4. Generate Embeddings
    print("[TEST] Dispatched chunks to abstract embedding provider...")
    processed_embeddings = []
    
    for chunk in consolidated_chunks:
        vector = embedding_engine.embed_text(chunk["text_content"])
        chunk["embedding"] = vector
        processed_embeddings.append(chunk)

    processed_emb_path = os.path.join(sandbox_dir, "processed_embeddings.json")
    with open(processed_emb_path, "w", encoding="utf-8") as f:
        json.dump(processed_embeddings, f, indent=4)
    print("[TEST] Embeddings catalog generated successfully.")

    # 5. Load data into database
    seed_database_at_scale(batch_size=10)
    print("[TEST] Verification Cycle finished completely.")

if __name__ == "__main__":
    execute_end_to_end_test()