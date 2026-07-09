import os
import json
import time
from core.config import settings
from components.embedding_provider import embedding_engine

def generate_mass_embeddings():
    sandbox_dir = os.getenv("RAW_DATA_DIR", "data_sandbox/")
    input_ledger_path = os.path.join(sandbox_dir, "staged_chunks.json")
    output_ledger_path = os.path.join(sandbox_dir, "processed_embeddings.json")
    
    # 1. Verification Guardrail Check
    if not os.path.exists(input_ledger_path):
        print(f"Error: Compiled chunks ledger '{input_ledger_path}' not found. Run transformer first.")
        return
        
    with open(input_ledger_path, "r", encoding="utf-8") as f:
        staged_chunks = json.load(f)
        
    print(f"Loaded {len(staged_chunks)} text segments.")
    print(f"Active Embedding Mode: {settings.EMBEDDING_MODE}")
    
    processed_records = []
    BATCH_SIZE = 50  # Packs 50 chunks into 1 request/computation
    
    print(f"Launching multi-row matrix transformation stream...")
    print("-" * 60)

    # 2. Enterprise Batch Loop Processing
    for i in range(0, len(staged_chunks), BATCH_SIZE):
        chunk_batch = staged_chunks[i : i + BATCH_SIZE]
        
        # Extract just the raw text strings for the input payload
        batch_texts = [chunk["text_content"] for chunk in chunk_batch]
        
        try:
            # Route through the abstract provider (Instantly handles Local CPU vs Cloud API)
            vectors = embedding_engine.embed_batch(batch_texts)
            
            # Unpack and remap the returned vectors to their source dictionaries
            for idx, vector in enumerate(vectors):
                original_chunk = chunk_batch[idx]
                processed_records.append({
                    "id": original_chunk["id"],
                    "source_file": original_chunk["source_file"],
                    "text_content": original_chunk["text_content"],
                    "embedding": vector
                })
            
            print(f"Processed Batch [{i//BATCH_SIZE + 1}]: Chunks {i+1} to {min(i+BATCH_SIZE, len(staged_chunks))}")
            
            # Apply a polite throttle only if we are using the remote rate-limited Cloud API
            if settings.EMBEDDING_MODE == "CLOUD":
                time.sleep(1.0)

        except Exception as e:
            print(f"Exception on Batch starting at chunk {i+1}: {e}")
            if settings.EMBEDDING_MODE == "CLOUD":
                print("⏸ Throttled or Network Error. Sleeping 10 seconds before continuing...")
                time.sleep(10)
            continue

    # 3. Commit fully serialized vector coordinates array ledger to disk
    with open(output_ledger_path, "w", encoding="utf-8") as f:
        json.dump(processed_records, f, indent=4, ensure_ascii=False)
        
    print("=" * 60)
    print(f"Embedding Pipeline Completed Successfully!")
    print(f"Total Vector Payloads Serialized: {len(processed_records)}")
    print(f"Output Saved to: {output_ledger_path}")
    print("=" * 60)

if __name__ == "__main__":
    generate_mass_embeddings()