import os
from openai import OpenAI
from dotenv import load_dotenv
from storage.retriever import semantic_search

# Check an environmental flag set by your terminal (defaulting to local development)
app_env = os.getenv("APP_ENV", "development")

# Dynamically route the runtime configurations file path
if app_env == "production":
    load_dotenv(".env.production")
    print("[CONFIG]: System successfully bound to PRODUCTION environment.")
else:
    load_dotenv(".env")
    print("[CONFIG]: System successfully bound to LOCAL DEVELOPMENT environment.")

def generate_rag_response(user_query):
    """Generates a fully grounded RAG response with live citations via APIs."""
    print("Orchestrator Step 1: Fetching context matrix from scaled database core...")

    # 1. Retrieve the top matching records (now containing text and metadata dicts)
    retrieved_records = semantic_search(user_query, top_k=3)

    if not retrieved_records:
        print("Warning: No relevant documentation blocks retrieved from database.")
        context_str = "No verified documentation snippets available."
        citations = set()
    else:
        # 2. Extract texts and isolate file citations
        context_blocks = []
        citations = set()
        
        for record in retrieved_records:
            context_blocks.append(record["text"])
            if record["source"]:
                citations.add(record["source"])
                
        # Flatten the list of text chunks into a single clean string block
        context_str = "\n\n--- DOCUMENTATION CHUNK ---\n".join(context_blocks)

    # 3. Formulate the strict grounding System Prompt
    system_prompt = (
        "You are an enterprise AI technical support engineer specialized in scikit-learn architecture.\n"
        "Your core directive is to answer the user's question using ONLY the provided documentation context blocks.\n"
        "Adhere to these strict operational constraints:\n"
        "1. Direct text grounding: Rely only on facts directly stated in the context.\n"
        "2. Zero speculation: If the provided context does not contain the answer, explicitly state: "
        "'I do not possess the verified context required to answer this inquiry.' Do not attempt to extrapolate or invent parameters.\n"
        "3. Clear formatting: Present code snippets or configurations cleanly when available.\n"
    )

    # 4. Formulate the User Prompt with the injected context
    user_prompt = f"""
                    Context Documentation blocks:
                    =========================================
                    {context_str}
                    =========================================

                    User Question: {user_query}

                    Answer:
                    """
    
    # 5. Initialize the Live GitHub Models LLM Client
    github_token = os.getenv("GITHUB_TOKEN")
    base_url = os.getenv("LLM_BASE_URL", "https://models.inference.ai.azure.com")
    chat_model = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")

    print("\nOrchestrator Step 2: Routing grounded payload matrix to live model cloud...")

    if github_token and not github_token.startswith("ghp_YOUR_"):
        try:
            client = OpenAI(base_url=base_url, api_key=github_token)
            
            response = client.chat.completions.create(
                model=chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,  # Strict mathematical framing adherence
            )

            llm_answer = response.choices[0].message.content.strip()
            
            # 6. Append production-grade verifiable citations to the output response
            if citations:
                formatted_citations = "\n".join([f"Source: {source}" for source in citations])
                return f"{llm_answer}\n\n---\n###  Sources Verified:\n{formatted_citations}"
            return llm_answer
        
        except Exception as e:
            return f"Live LLM Orchestration Error: {e}"
    else:
        return "Orchestrator Error: GITHUB_TOKEN configuration failure."

if __name__ == "__main__":
    # Test Question 1: Relevant to scikit-learn (Should return direct answer + active source files)
    prompt_1 = input("Enter a scikit-learn related question to test the live RAG system: ")
    ai_answer_1 = generate_rag_response(prompt_1)
    print(f"\nAI RESPONSE:\n" + "="*60 + f"\n{ai_answer_1}\n" + "="*60 + "\n")

    # Test Question 2: Irrelevant (Should trigger our hallucination block!)
    prompt_2 = input("Enter a non-scikit-learn question to test hallucination guardrails: ")
    ai_answer_2 = generate_rag_response(prompt_2)
    print(f"\nAI RESPONSE:\n" + "="*60 + f"\n{ai_answer_2}\n" + "="*60)