from typing import List
from abc import ABC, abstractmethod
from core.config import settings

class BaseEmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]: pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]: pass

class UnifiedEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self):
        self.model_name = "Orange/orange-nomic-v1.5-1536"
        self._model = None # Model starts empty to allow instant server boot
        print(f"Embedding Provider registered [{self.model_name}]. (Model will lazy-load on first request)")

    @property
    def model(self):
        """Lazy-loads the PyTorch model on the first request."""
        if self._model is None:
            print(f"Lazy loading Embedding Model [{self.model_name}] into memory...")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, trust_remote_code=True)
            self._verify_dimensions()
        return self._model

    def _verify_dimensions(self):
        print("Executing structural validation check on vector dimensions...")
        test_string = "Structural verification payload checkpoint."
        prefix_text = f"search_document: {test_string}"
        
        # Bypass self.model here to avoid infinite recursion
        test_vector = self._model.encode(prefix_text, convert_to_tensor=False)
        actual_dim = len(test_vector)

        if actual_dim != settings.EMBEDDING_DIMENSION:
            raise ValueError(
                f"CRITICAL MISMATCH! Provider returned {actual_dim} dimensions, "
                f"schema requires {settings.EMBEDDING_DIMENSION} dimensions."
            )
        print(f"Validation Guard Passed! Verified at clean {actual_dim} dimensions.")

    def embed_text(self, text: str) -> List[float]:
        prefix_text = f"search_document: {text}"
        # Accessing self.model triggers the lazy load if not already loaded
        vector = self.model.encode(prefix_text, convert_to_tensor=False)
        return vector.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        prefixed_texts = [f"search_document: {t}" for t in texts]
        vectors = self.model.encode(prefixed_texts, batch_size=32, convert_to_tensor=False)
        return vectors.tolist()

def get_embedding_provider() -> BaseEmbeddingProvider:
    # Removed global test execution. Just return the un-initialized provider.
    return UnifiedEmbeddingProvider()

embedding_engine = get_embedding_provider()