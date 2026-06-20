import os
import random
import psycopg2
from pgvector.psycopg2 import register_vector
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def get_query_embedding(query_text):
    """Converts the user's plain text query into a 1536-dimensional vector."""
    
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key:
        try:
            client = OpenAI()
            response = client.embeddings.create(
                input=query_text,
                model="text-embedding-3-small"
            )

            return response.data[0].embedding
        
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            return None
    else:
        print("No API key found. Using mock vector generator for query embedding.")

        # Uses a deterministic hash of the text so searching the same phrase yields the same vector
        random.seed(int(abs(hash(query_text)) % 1e7))

        return [random.uniform(-1, 1) for _ in range(1536)]
    
def semantic_search(query_text, top_k=3):
    """Queries Postgres using the pgvector cosine distance operator to find matching context."""
    
    # 1. Vectorize the incoming user prompt
    query_vector = get_query_embedding(query_text)

    if not query_vector:
        print("Could not generate embedding for query.")
        return []

    print(f"Executing vector search for: '{query_text}'")
    
    # 2. Open connection to our Docker container on port 5433
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        cursor = conn.cursor()
        
        # Register pgvector to let psycopg2 pass list variables smoothly into SQL
        register_vector(conn)

        # 3. Formulate the core pgvector Cosine Distance Query
        # <=> calculates the distance. We order by closest (ASC) and pull the Top K
        search_query = """
            SELECT id, text_content, embedding <=> %s::vector AS cosine_distance 
            FROM sklearn_docs 
            ORDER BY cosine_distance ASC 
            LIMIT %s;
        """
        
        cursor.execute(search_query, (query_vector, top_k))
        results = cursor.fetchall()
        
        print(f"Retrieved the Top-{len(results)} most semantically close documentation chunks:\n")
        
        retrieved_contexts = []
        for row in results:
            chunk_id, text, distance = row
            print(f"[Chunk ID: {chunk_id}] (Distance score: {distance:.4f})")
            print(f"{text[:250]}...\n" + "-"*50)
            retrieved_contexts.append(text)
            
        return retrieved_contexts

    except Exception as e:
        print(f"Database Search Failure: {e}")
        return []
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()


if __name__ == "__main__":
    # Test query to run our retrieval engine live!
    sample_prompt = input("Enter a search query to find relevant sklearn documentation: ")
    semantic_search(sample_prompt, top_k=3)