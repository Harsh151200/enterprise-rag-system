import os
import json
from langchain_text_splitters import RecursiveCharacterTextSplitter

def process_dynamic_sandbox_directory():
    # 1. Align paths with your crawler's new folder topology
    sandbox_dir = os.getenv("RAW_DATA_DIR", "data_sandbox/")
    target_input_dir = os.path.join(sandbox_dir, "raw", "scikit_learn")
    
    # Define an enterprise chunk configuration
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    
    all_chunks_payload = []
    global_chunk_id = 1
    
    # Safety check: Ensure the target input directory actually exists
    if not os.path.exists(target_input_dir):
        print(f"Error: Target directory '{target_input_dir}' not found. Run crawler first.")
        return

    # 2. Update filter to target your custom 'dynamic_' prefix files
    target_files = [f for f in os.listdir(target_input_dir) if f.startswith("dynamic_") and f.endswith(".txt")]
    
    print(f"Initializing batch chunking for {len(target_files)} dynamically harvested assets...")
    print(f"Reading from: {target_input_dir}\n" + "-"*50)
    
    for file_name in target_files:
        file_path = os.path.join(target_input_dir, file_name)
        
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
            
        # Execute the recursive semantic character split
        text_slices = splitter.split_text(raw_text)
        print(f"Segmented: {file_name} ──► Generated {len(text_slices)} chunks")
        
        for segment in text_slices:
            # Build the tracking record ledger entry
            record = {
                "id": global_chunk_id,
                "source_file": file_name,
                "text_content": segment
            }
            all_chunks_payload.append(record)
            global_chunk_id += 1
            
    # 3. Save the consolidated chunk index down to a centralized stage file
    output_ledger = os.path.join(sandbox_dir, "staged_chunks.json")
    with open(output_ledger, "w", encoding="utf-8") as f:
        json.dump(all_chunks_payload, f, indent=4, ensure_ascii=False)
        
    print("\n" + "="*60)
    print(f"Success! Scaled processing finished.")
    print(f"Total Chunks Extracted: {len(all_chunks_payload)}")
    print(f"Centralized Ledger Saved to: {output_ledger}")
    print("="*60)

if __name__ == "__main__":
    process_dynamic_sandbox_directory()