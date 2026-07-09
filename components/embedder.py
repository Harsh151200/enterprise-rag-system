import os
import json
from dotenv import load_dotenv
from components.embedding_provider import create_embedding_provider
from components.transformer import chunk_documentation

load_dotenv()

def generate_embeddings():
    """Generate embeddings for the text chunks using OpenAI's API."""
    
    # 1. Fetch text chunks
    chunks = chunk_documentation()
    if not chunks:
        print("No chunks found to embed.")
        return
    
    embedding_provider = create_embedding_provider(
        model="text-embedding-3-small", dimensions=1536
    )
    using_openai = os.getenv("OPENAI_API_KEY") is not None

    processed_records = []
    print(f"Starting vector generation for {len(chunks)} chunks...")

    for i, chunk in enumerate(chunks):
        if i == 0 and not using_openai:
            print(
                "No API key found. Utilizing local mock vector simulator ($0 development mode)."
            )
        try:
            vector = embedding_provider.embed_text(chunk)
        except Exception as e:
            print(f"Embedding error on chunk {i}: {e}")
            break

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

    if processed_records:
        print(
            f"Vector Dimensionality Verified: {len(processed_records[0]['embedding'])} dimensions."
        )


if __name__ == "__main__":
    generate_embeddings()