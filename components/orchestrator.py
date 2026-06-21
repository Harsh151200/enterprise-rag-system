import os
from openai import OpenAI
from dotenv import load_dotenv
# Import our search mechanism directly from the storage package
from storage.retriever import semantic_search

# Load environment variables from .env file
load_dotenv()

def generate_rag_response(user_query):
    """Generates a RAG response by retrieving relevant context and querying OpenAI's GPT model or mock generator."""
    
    print("Orchestrator Step 1: Quering the vector database for relevant context...")

    # 1. Retrieve the Top-3/k closest text chunks from our Postgres Docker container
    retrieved_chunks = semantic_search(user_query, top_k=3)

    if not retrieved_chunks:
        print("Warning: No relevant documentation blocks retrieved from database.")
        context_str = "No verified documentation snippets available."
    else:
        # 2. Flatten the list of text chunks into a single clean string block
        context_str = "\n\n--- DOCUMENTATION CHUNK ---\n".join(retrieved_chunks)

    # 3. Formulate the strict grounding System Prompt
    system_prompt = (
        "You are an enterprise AI technical support engineer specialized in scikit-learn.\n"
        "Your core directive is to answer the user's question using ONLY the provided documentation context blocks.\n"
        "Adhere to these strict operational constraints:\n"
        "1. Direct text grounding: Rely only on facts directly stated in the context.\n"
        "2. Zero speculation: If the provided context does not contain the answer, explicitly state: "
        "'I do not possess the verified context required to answer this inquiry.' Do not attempt to extrapolate.\n"
        "3. Clear formatting: Present code snippets or steps clearly when available.\n"
    )

    # 4. Formulate the User Prompt with the injected context (Augmentation)
    user_prompt = f"""
                    Context Documentation blocks:
                    =========================================
                    {context_str}
                    =========================================

                    User Question: {user_query}
                    
                    Answer:
                """
    
    # 5. Initialize the LLM Endpoint Connection
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI() if api_key else None

    print("\nOrchestrator: Step 2 - Compiling localized prompt context and sending to LLM...")

    if client:
        try:
            # Live production API call to a highly optimized model (gpt-4o-mini)
            # https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,  # Force zero randomness for maximum deterministic factual grounding
            )

            return response.choices[0].message.content.strip()
        
        except Exception as e:
            return f"LLM Orchestration Error: {e}"
    else:
        # Cost-free Mock Fallback for $0 development mode
        # Perfectly simulates a bounded response payload
        return (
            "SIMULATED RAG RESPONSE - $0 Dev Model\n"
            + ("-" * 50) + "\n"
            + f"Received Query: '{user_query}'\n"
            + f"Successfully verified and bound response logic against {len(retrieved_chunks)} database chunks.\n"
            + "System guardrails validated: Context successfully injected without exceeding limits."
        )

if __name__ == "__main__":
    # Test Question 1: Relevant to scikit-learn
    prompt_1 = input("Enter a scikit-learn related question to test the RAG system: ")
    ai_answer_1 = generate_rag_response(prompt_1)
    print(f"\nAI: {ai_answer_1}\n" + "="*60)

    # Test Question 2: Irrelevant (Should trigger our hallucination block!)
    prompt_2 = input("Enter a non-scikit-learn related question to test the hallucination guardrails: ")
    ai_answer_2 = generate_rag_response(prompt_2)
    print(f"\nAI: {ai_answer_2}\n")