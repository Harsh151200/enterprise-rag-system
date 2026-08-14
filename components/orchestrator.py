import os
from typing import Dict, Any
from openai import OpenAI
from core.config import settings
from storage.retriever import hybrid_search

def generate_rag_response(user_query: str) -> Dict[str, Any]:
    """
    Generates a fully grounded RAG response with structured live citations,
    utilizing blended keyword and dense vector hybrid search strategies.
    
    Returns:
        Dict[str, Any]: A dictionary containing 'answer' (str) and 'citations' (list).
    """
    print("Orchestrator Step 1: Fetching context matrix from scaled hybrid database core...")

    # 1. Retrieve the top matching records via our abstracted hybrid retriever (top_k=4)
    retrieved_records = hybrid_search(user_query, top_k=4)

    citations = set()
    if not retrieved_records:
        print("Warning: No relevant documentation blocks retrieved from database.")
        context_str = "No verified documentation snippets available."
    else:
        context_blocks = []
        for idx, record in enumerate(retrieved_records, 1):
            # Format raw strings with explicit lineage metadata headers to maximize attention anchoring
            formatted_chunk = (
                f"[DOCUMENT NODE #{idx}] (Format: {record['format']} | RRF Score: {record['rrf_score']:.5f})\n"
                f"Source Location: {record['source']} | Chunk Offset: {record['chunk_index']}\n"
                f"{'-' * 60}\n"
                f"{record['text']}"
            )
            context_blocks.append(formatted_chunk)
            
            if record.get("source"):
                citations.add(record["source"])
                
        context_str = "\n\n--- DOCUMENTATION CHUNK ---\n".join(context_blocks)

        # print("\n[DEBUG] --- EXACT CONTEXT SENT TO LLM ---")
        # print(context_str)
        # print("[DEBUG] -----------------------------------\n")

    # 2. Formulate the strict grounding System Prompt
    system_prompt = (
        "You are an enterprise AI technical support engineer specialized in scikit-learn architecture.\n"
        "Your core directive is to answer the user's question using ONLY the provided documentation context blocks.\n"
        "Adhere to these strict operational constraints:\n"
        "1. Rely on the provided context to anchor your answer, but you may synthesize broad machine learning definitions if the context mentions the specific algorithmic implementations.\n"
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
    api_key = settings.OPENAI_API_KEY or settings.GITHUB_TOKEN
    
    # Check if we are running in GitHub Models proxy mode or direct OpenAI mode
    base_url = "https://models.github.ai/inference" if settings.GITHUB_TOKEN and not settings.OPENAI_API_KEY else None
    chat_model = "gpt-4o-mini"

    print(f"\nOrchestrator Step 2: Routing grounded payload matrix to cloud [Mode: {settings.APP_ENV}]...")
    print(base_url)
    print(api_key)

    if not api_key:
        return {
            "answer": "Orchestrator Error: Secure API token authorization credentials missing.",
            "citations": []
        }

    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        
        response = client.chat.completions.create(
            model=chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0, # Kept at absolute 0 for predictable testing runs
        )

        llm_answer = response.choices[0].message.content.strip()
        
        # FIXED: Returns clean, structured dictionary data to allow custom frontend visual parsing
        return {
            "answer": llm_answer,
            "citations": sorted(list(citations))
        }
    
    except Exception as e:
        return {
            "answer": f"Live LLM Orchestration Error: {e}",
            "citations": []
        }