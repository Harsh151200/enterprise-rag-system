from typing import List
from abc import ABC, abstractmethod
from core.config import settings

# =========================================================================
# INTERFACE DEFINITION (The Blueprint Contract)
# =========================================================================
class BaseEmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass

# =========================================================================
# UNIFIED BACKEND: CPU-OPTIMIZED LOCAL EXECUTION
# =========================================================================
class UnifiedEmbeddingProvider(BaseEmbeddingProvider):
    """
    Unified CPU-optimized embedding provider utilizing the open-source 
    1536-dimensional architecture for both local ETL and Cloud Run production.
    """
    def __init__(self):
        self.model_name = "Orange/orange-nomic-v1.5-1536"
        print(f"Initializing Unified Embedding Provider [{self.model_name}]...")
        
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "Missing core dependency. Please ensure sentence-transformers is installed."
            ) from e

        try:
            # Loads cleanly into RAM. Fast on CPUs for single-query retrieval.
            self.model = SentenceTransformer(self.model_name, trust_remote_code=True)
        except Exception as e:
            print(f"Critical failure initializing embedding engine: {e}")
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
# DEPENDENCY INJECTION & VALIDATION ENGINE
# =========================================================================
def get_embedding_provider() -> BaseEmbeddingProvider:
    provider = UnifiedEmbeddingProvider()

    print("Executing structural validation check on vector dimensions...")
    test_string = "Structural verification payload checkpoint."
    test_vector = provider.embed_text(test_string)
    actual_dim = len(test_vector)

    if actual_dim != settings.EMBEDDING_DIMENSION:
        raise ValueError(
            f"CRITICAL CONFIGURATION MISMATCH! Provider returned {actual_dim} dimensions, "
            f"but schema requires {settings.EMBEDDING_DIMENSION} dimensions."
        )
    
    print(f"Validation Guard Passed! Provider verified at clean {actual_dim} dimensions.")
    return provider

embedding_engine = get_embedding_provider()