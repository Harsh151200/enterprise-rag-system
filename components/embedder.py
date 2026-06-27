import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

# 1. Check an environmental flag set by your terminal (defaulting to local development)
app_env = os.getenv("APP_ENV", "development")

# 2. Dynamically route the runtime configurations file path
if app_env == "production":
    load_dotenv(".env.production")
    print("[CONFIG]: System successfully bound to PRODUCTION environment.")
else:
    load_dotenv(".env")
    print("[CONFIG]: System successfully bound to LOCAL DEVELOPMENT environment.")

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
        
    print(f"Loaded {len(staged_chunks)} text segments for spatial vector translation.")
    
    # 2. Extract GitHub Models Connectivity Credentials
    github_token = os.getenv("GITHUB_TOKEN")
    base_url = os.getenv("LLM_BASE_URL", "https://models.inference.ai.azure.com")
    
    # Check if we have a valid token to skip Mock mode and use live free processing
    if github_token and not github_token.startswith("ghp_YOUR_"):
        print("Establishing live encrypted connection to GitHub Models Inference Endpoint...")
        client = OpenAI(base_url=base_url, api_key=github_token)
        EMBEDDING_MODEL_NAME=os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-large")
        is_live_mode = True
    else:
        print("! No valid GITHUB_TOKEN identified. Defaulting to Local $0 Mock Simulation...")
        import random
        is_live_mode = False

    processed_records = []

    # --- ENTERPRISE BATCH CONFIGURATION PARAMETERS ---
    BATCH_SIZE = 50  # Packs 50 chunks into 1 single HTTP request
    
    # 3. Enterprise Batch Loop Processing
    # GitHub Models free tier imposes rate limits. To be polite and prevent HTTP 429 throttling,
    # we process chunks sequentially and use a micro-sleep pause.
    print(f"Launching multi-row matrix transformation stream...")
    print("-" * 60)
    
    # for idx, chunk in enumerate(staged_chunks):
    #     chunk_id = chunk["id"]
    #     source_file = chunk["source_file"]
    #     text_content = chunk["text_content"]
        
    #     if is_live_mode:
    #         try:
    #             # Direct live connection request to OpenAI text-embedding-3-small hosted on GitHub
    #             response = client.embeddings.create(
    #                 input=text_content,
    #                 model="text-embedding-3-small"
    #             )
    #             vector = response.data[0].embedding
    #             print(f"[{idx+1}/{len(staged_chunks)}] Encoded Chunk ID: {chunk_id} from {source_file}")
                
    #             # Polite micro-sleep to honor free tier rate-limit quotas
    #             time.sleep(0.3)
                
    #         except Exception as e:
    #             print(f"API Connection Mismatch on Chunk ID {chunk_id}: {e}")
    #             print("⏸Pausing network stream for 5 seconds to clear throttles...")
    #             time.sleep(10)
    #             continue

        # else:
        #     # Consistent deterministic mock array generator fallback
        #     random.seed(int(abs(hash(text_content)) % 1e7))
        #     vector = [random.uniform(-1, 1) for _ in range(1536)]
        #     if (idx + 1) % 100 == 0 or (idx + 1) == len(staged_chunks):
        #         print(f"[Mock Mode] Computed up to segment [{idx+1}/{len(staged_chunks)}]")

        # # Append the standardized record array to the ledger
        # processed_records.append({
        #     "id": chunk_id,
        #     "source_file": source_file,
        #     "text_content": text_content,
        #     "embedding": vector
        # })

    # Loop over the chunks list in steps of BATCH_SIZE
    for i in range(0, len(staged_chunks), BATCH_SIZE):
        chunk_batch = staged_chunks[i : i + BATCH_SIZE]
        
        # Extract just the raw text strings for the API input payload
        batch_texts = [chunk["text_content"] for chunk in chunk_batch]
        
        if is_live_mode:
            try:
                # Fire a single API request for the entire batch group
                response = client.embeddings.create(
                    input=batch_texts,
                    model=EMBEDDING_MODEL_NAME,
                    dimensions=1536
                )
                
                # Unpack the returned list of 1,536-dim coordinates matching our input order
                for idx, embedding_data in enumerate(response.data):
                    original_chunk = chunk_batch[idx]
                    processed_records.append({
                        "id": original_chunk["id"],
                        "source_file": original_chunk["source_file"],
                        "text_content": original_chunk["text_content"],
                        "embedding": embedding_data.embedding
                    })
                    # print(f"Processed Chunk ID: {original_chunk['id']} from {original_chunk['source_file']} ─► Embedding Length: {len(embedding_data.embedding)}")
                
                print(f"Processed Batch [{i//BATCH_SIZE + 1}]: Chunks {i+1} to {min(i+BATCH_SIZE, len(staged_chunks))}")
                
                # Coalesce time pause to honor free tier fair-use quotas comfortably
                time.sleep(2.0)

            except Exception as e:
                print(f"API Exception on Batch starting at chunk {i+1}: {e}")
                print("Throttled. Sleeping 10 seconds before continuing...")
                time.sleep(10)
                continue

        else:
            # Mock mode generator loop fallback
            for original_chunk in chunk_batch:
                random.seed(int(abs(hash(original_chunk["text_content"])) % 1e7))
                vector = [random.uniform(-1, 1) for _ in range(1536)]
                processed_records.append({
                    "id": original_chunk["id"],
                    "source_file": original_chunk["source_file"],
                    "text_content": original_chunk["text_content"],
                    "embedding": vector
                })
            print(f"[Mock Mode] Staged Batch starting at index {i+1}")
        
        

    # 4. Commit fully serialized vector coordinates array ledger to disk
    with open(output_ledger_path, "w", encoding="utf-8") as f:
        json.dump(processed_records, f, indent=4, ensure_ascii=False)
        
    print("=" * 60)
    print(f"Milestone 2 Vector Space Completed successfully!")
    print(f"Total Vector Payloads Serialized: {len(processed_records)}")
    print(f"Output Saved to: {output_ledger_path}")
    print("=" * 60)

if __name__ == "__main__":
    generate_mass_embeddings()