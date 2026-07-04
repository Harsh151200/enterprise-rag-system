import os
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv
import random

# Check an environmental flag set by your terminal (defaulting to local development)
app_env = os.getenv("APP_ENV", "development")

# Dynamically route the runtime configurations file path
if app_env == "production":
    load_dotenv(".env.production")
    print("[CONFIG]: System successfully bound to PRODUCTION environment.")
else:
    load_dotenv(".env")
    print("[CONFIG]: System successfully bound to LOCAL DEVELOPMENT environment.")

def get_query_embedding(query_text):
    """Converts the user's plain text query into a 1536-dimensional vector using live MRL truncation."""
    github_token = os.getenv("GITHUB_TOKEN")
    base_url = os.getenv("LLM_BASE_URL", "https://models.inference.ai.azure.com")

    if github_token and not github_token.startswith("ghp_YOUR_"):
        try:
            # Connect standard OpenAI SDK client directly to GitHub's inference cloud
            client = OpenAI(base_url=base_url, api_key=github_token)
            
            # Using text-embedding-3-large truncated down to 1536 dimensions
            response = client.embeddings.create(
                input=[query_text],
                model="text-embedding-3-large",
                dimensions=1536
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"GitHub Models Embedding API Error: {e}")
            return None
    else:
        print("Critical Error: GITHUB_TOKEN not configured in .env.production. Using fallback deterministic random embedding for development purposes.")
        
        # Uses a deterministic hash of the text so searching the same phrase yields the same vector
        # Comment this section when fully developed and connected to the live embedding API.
        random.seed(int(abs(hash(query_text)) % 1e7))

        return [random.uniform(-1, 1) for _ in range(1536)]
    
        # return false
    

def semantic_search(query_text, top_k=3):
    """Queries Postgres using pgvector to find relevant context along with file metadata."""
    query_vector = get_query_embedding(query_text)

    if not query_vector:
        print("Could not generate embedding for query.")
        return []

    print(f"Executing live vector search for: '{query_text}'")

    # Extract database credentials
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        cursor = conn.cursor()
        
        # Core query: Extract text_content AND the new source_file metadata column
        search_query = """
            SELECT id, text_content, source_file, embedding <=> %s::vector AS cosine_distance 
            FROM sklearn_docs 
            ORDER BY cosine_distance ASC 
            LIMIT %s;
        """
        
        cursor.execute(search_query, (query_vector, top_k))
        results = cursor.fetchall()
        
        print(f"Retrieved Top-{len(results)} semantically close documentation chunks.\n")
        
        retrieved_contexts = []
        for row in results:
            chunk_id, text, source_file, distance = row
            print(f" ──► [Chunk ID: {chunk_id}] [Source: {source_file}] (Distance: {distance:.4f})")
            
            # Pack as structured dictionary payloads so the orchestrator can separate context from citations
            retrieved_contexts.append({
                "text": text,
                "source": source_file
            })
            
        return retrieved_contexts

    except Exception as e:
        print(f"Database Search Failure: {e}")
        return []
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    sample_prompt = input("Enter a search query to test the upgraded retrieval core: ")
    semantic_search(sample_prompt, top_k=3)