import os
from openai import OpenAI
from core.config import settings
from storage.retriever import semantic_search

def generate_rag_response(user_query):
    """Generates a fully grounded RAG response with live citations via APIs."""
    print("Orchestrator Step 1: Fetching context matrix from scaled database core...")

    # 1. Retrieve the top matching records via our abstracted retriever
    retrieved_records = semantic_search(user_query, top_k=3)

    if not retrieved_records:
        print("Warning: No relevant documentation blocks retrieved from database.")
        context_str = "No verified documentation snippets available."
        citations = set()
    else:
        context_blocks = []
        citations = set()
        for record in retrieved_records:
            context_blocks.append(record["text"])
            if record["source"]:
                citations.add(record["source"])
                
        context_str = "\n\n--- DOCUMENTATION CHUNK ---\n".join(context_blocks)

    # 2. Formulate the strict grounding System Prompt
    system_prompt = (
        "You are an enterprise AI technical support engineer specialized in scikit-learn architecture.\n"
        "Your core directive is to answer the user's question using ONLY the provided documentation context blocks.\n"
        "Adhere to these strict operational constraints:\n"
        "1. Direct text grounding: Rely only on facts directly stated in the context.\n"
        "2. Zero speculation: If the provided context does not contain the answer, explicitly state: "
        "'I do not possess the verified context required to answer this inquiry.' Do not attempt to extrapolate or invent parameters.\n"
        "3. Clear formatting: Present code snippets or configurations cleanly when available.\n"
    )

    user_prompt = f"""
                    Context Documentation blocks:
                    =========================================
                    {context_str}
                    =========================================

                    User Question: {user_query}

                    Answer:
                    """
    
    # 3. Extract verified credentials from our central Pydantic Configuration Layer
    # Safely route to OpenAI API Key or fall back to the GitHub Models token structure
    api_key = settings.OPENAI_API_KEY or settings.GITHUB_TOKEN
    
    # Check if we are running in GitHub Models proxy mode or direct OpenAI mode
    base_url = "https://models.inference.ai.azure.com" if settings.GITHUB_TOKEN and not settings.OPENAI_API_KEY else None
    chat_model = "gpt-4o-mini" # Standard production baseline

    print(f"\nOrchestrator Step 2: Routing grounded payload matrix to cloud [Mode: {settings.APP_ENV}]...")

    if api_key:
        try:
            client = OpenAI(base_url=base_url, api_key=api_key)
            
            response = client.chat.completions.create(
                model=chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
            )

            llm_answer = response.choices[0].message.content.strip()
            
            if citations:
                formatted_citations = "\n".join([f"Source: {source}" for source in citations])
                return f"{llm_answer}\n\n---\n###  Sources Verified:\n{formatted_citations}"
            return llm_answer
        
        except Exception as e:
            return f"Live LLM Orchestration Error: {e}"
    else:
        return "Orchestrator Error: Secure API token authorization credentials missing."