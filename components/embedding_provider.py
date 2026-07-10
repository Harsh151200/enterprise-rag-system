from abc import ABC, abstractmethod
import os
from typing import List
from core.config import settings

# =========================================================================
# INTERFACE DEFINITION (The Blueprint Contract)
# =========================================================================
class BaseEmbeddingProvider(ABC):
    """
    Abstract Base Class acting as the mandatory structural contract for 
    all vector generation engines in the Enterprise RAG Platform.
    """
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Calculates vector coordinates for a single string fragment."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Calculates vector coordinates for an array of strings efficiently."""
        pass

# =========================================================================
# CONCRETE BACKEND 1: LOCAL HUGGING FACE EXECUTION
# =========================================================================
class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """
    Local CPU-optimized embedding provider utilizing an open-source 
    1536-dimensional architecture for local development testing.
    """
    def __init__(self):
        print("Initializing Local Embedding Provider [nomic-embed-text-v1.5]...")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "Missing core dependency for LOCAL embedding mode. Please run: pip install sentence-transformers"
            ) from e

        try:
            # Nomic-embed-text-v1.5 natively supports adjustable dimensions and defaults to 1536
            self.model = SentenceTransformer("Orange/orange-nomic-v1.5-1536", trust_remote_code=True)
        except Exception as e:
            # This will now print out the exact missing sub-dependency or network error
            print(f"Critical failure initializing Nomic embedding engine: {e}")
            raise e

    def embed_text(self, text: str) -> List[float]:
        # Prefix required by Nomic model tuning specifications for search tasks
        prefix_text = f"search_document: {text}"
        vector = self.model.encode(prefix_text, convert_to_tensor=False)
        return vector.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        prefixed_texts = [f"search_document: {t}" for t in texts]
        vectors = self.model.encode(prefixed_texts, batch_size=32, convert_to_tensor=False)
        return vectors.tolist()

# =========================================================================
# CONCRETE BACKEND 2: CLOUD MANAGED API ROUTING
# =========================================================================
class CloudEmbeddingProvider(BaseEmbeddingProvider):
    """
    Cloud-optimized provider routing embedding requests via secure external 
    SDK channels, keeping the production runtime container lightweight.
    """
    def __init__(self):
        print("Initializing Cloud Managed API Embedding Provider...")
        # Check for OpenAI first, fallback to GitHub Models configuration if set
        self.api_key = settings.OPENAI_API_KEY or settings.GITHUB_TOKEN
        if not self.api_key:
            raise ValueError("Cloud Embedding Mode requires an active OPENAI_API_KEY or GITHUB_TOKEN.")
        
        try:
            from openai import OpenAI
            # Dynamically handle base URL routing based on which credential token is available
            base_url = "https://models.inference.ai.azure.com" if settings.GITHUB_TOKEN and not settings.OPENAI_API_KEY else None
            self.client = OpenAI(api_key=self.api_key, base_url=base_url)
            self.model_name = "text-embedding-3-large" # Native 1536-dimension cloud engine
        except ImportError:
            raise ImportError("Missing dependencies for CLOUD embedding mode. Please run: pip install openai")

    def embed_text(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            input=[text],
            model=self.model_name,
            dimensions=settings.EMBEDDING_DIMENSION # Enforces strict 1536 compliance
        )
        return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(
            input=texts,
            model=self.model_name,
            dimensions=settings.EMBEDDING_DIMENSION
        )
        return [record.embedding for record in response.data]

# =========================================================================
# DEPENDENCY INJECTION FACTORY & VALIDATION ENGINE
# =========================================================================
def get_embedding_provider() -> BaseEmbeddingProvider:
    """
    Factory selector that reads system settings to inject the correct 
    backend provider and runs a validation check on vector outputs.
    """
    # 1. Resolve Provider Variant via Active Configuration Profile
    if settings.EMBEDDING_MODE == "CLOUD":
        provider = CloudEmbeddingProvider()
    else:
        provider = LocalEmbeddingProvider()

    # 2. Boot-Time Structural Validation Guard
    print("Executing structural validation check on vector dimensions...")
    test_string = "Structural verification payload checkpoint."
    test_vector = provider.embed_text(test_string)
    actual_dim = len(test_vector)

    if actual_dim != settings.EMBEDDING_DIMENSION:
        raise ValueError(
            f"CRITICAL CONFIGURATION MISMATCH! The active embedding backend returned a vector "
            f"dimension size of {actual_dim}, but the system database schema requires exactly "
            f"{settings.EMBEDDING_DIMENSION} dimensions. System boot halted to protect data integrity."
        )
    
    print(f"Validation Guard Passed! Provider verified at clean {actual_dim} dimensions.")
    return provider

# Global instance initialization for plug-and-play imports across the platform
embedding_engine = get_embedding_provider()