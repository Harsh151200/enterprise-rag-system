import os
import json
import random
from openai import OpenAI
from dotenv import load_dotenv
from transformer import chunk_documentation

load_dotenv()

def generate_embeddings():
    """Generate embeddings for the text chunks using OpenAI's API."""
    
    # 1. Fetch text chunks
    chunks = chunk_documentation()
    if not chunks:
        print("No chunks found to embed.")
        return
    
    # Initialize the OpenAI client (grabs key automatically from OPENAI_API_KEY env var)
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI() if api_key else None

    processed_records = []
    print(f"Starting vector generation for {len(chunks)} chunks...")

    for i, chunk in enumerate(chunks):
        if client:
            try:
                # 2. Live production API call to OpenAI
                response = client.embeddings.create(
                    input=chunk,
                    model="text-embedding-3-small"
                )
                # Extract the 1,536-dimensional array of floats
                vector = response.data[0].embedding

            except Exception as e:
                print(f"API Error on chunk {i}: {e}")
                break
        else:
            # 3. Mock embedder: Generates a deterministic pseudo-vector
            # This allows us to test our architecture without any cost or API dependency.
            if i == 0:
                print("No API key found. Utilizing local mock vector simulator ($0 development mode).")
            
            random.seed(i)
            vector = [random.uniform(-1, 1) for _ in range(1536)]

        # 4. Structure the payload exactly how a vector database expects it
        record = {
            "id": i,
            "text_content": chunk,
            "embedding": vector
        }

        processed_records.append(record)
        
        if (i + 1) % 10 == 0 or (i + 1) == len(chunks):
            print(f" Progress: Embedded {i + 1}/{len(chunks)} chunks.")

    # 5. Save the text + high-dimensional vectors locally to a JSON file
    output_path = os.path.join(os.getenv("RAW_DATA_DIR", "data_sandbox/"), "processed_embeddings.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(processed_records, f, indent=4)

    print(f"Vector Dimensionality Verified: {len(processed_records[0]['embedding'])} dimensions.")


if __name__ == "__main__":
    generate_embeddings()