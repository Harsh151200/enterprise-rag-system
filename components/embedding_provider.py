import os
import random
from abc import ABC, abstractmethod
from typing import List

from openai import OpenAI


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate a vector embedding for text."""


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.client = OpenAI()

    def embed_text(self, text: str) -> List[float]:
        response = self.client.embeddings.create(input=text, model=self.model)
        return response.data[0].embedding


class MockEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    def embed_text(self, text: str) -> List[float]:
        random.seed(int(abs(hash(text)) % 1e7))
        return [random.uniform(-1, 1) for _ in range(self.dimensions)]


def create_embedding_provider(
    model: str = "text-embedding-3-small", dimensions: int = 1536
) -> EmbeddingProvider:
    return (
        OpenAIEmbeddingProvider(model=model)
        if os.getenv("OPENAI_API_KEY")
        else MockEmbeddingProvider(dimensions=dimensions)
    )
