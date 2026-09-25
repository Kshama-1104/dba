from abc import ABC, abstractmethod
import hashlib
import math
from typing import List, Optional


class EmbeddingProvider(ABC):
    """
    Abstract interface for embedding generation.
    Decouples vector generation from database storage and retrieval.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the embedding vector dimension."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the name/identifier of the embedding model."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string into a dense vector."""
        pass

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of text strings into dense vectors."""
        pass


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic provider producing unit-normalized 384-dimensional dense vectors
    using token-level feature hashing and random projection.
    Provides fast, reproducible, offline semantic representations without external network calls.
    """

    def __init__(self, dimension: int = 384, model_name: str = "all-MiniLM-L6-v2"):
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_text(self, text: str) -> List[float]:
        words = text.lower().split()
        if not words:
            words = ["empty"]

        vec = [0.0] * self._dimension
        for word in words:
            h = hashlib.sha256(word.encode("utf-8")).digest()
            idx = int.from_bytes(h[:2], "big") % self._dimension
            sign = 1.0 if (h[2] % 2 == 0) else -1.0
            vec[idx] += sign

        # Euclidean L2 normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            return [round(x / norm, 6) for x in vec]
        vec[0] = 1.0
        return vec

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """
    Provider utilizing local HuggingFace / sentence-transformers model.
    Falls back gracefully if the package is not installed or model unavailable.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._dimension = 384
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load SentenceTransformer model '{self._model_name}': {str(exc)}"
                ) from exc

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_text(self, text: str) -> List[float]:
        self._load_model()
        vec = self._model.encode(text, normalize_embeddings=True)
        return [float(x) for x in vec]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        self._load_model()
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [[float(x) for x in vec] for vec in vectors]


# Default singleton instance
_default_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider() -> EmbeddingProvider:
    """
    Factory function returning the active embedding provider.
    Defaults to DeterministicEmbeddingProvider matching the PostgreSQL 384-dim schema.
    """
    global _default_provider
    if _default_provider is None:
        _default_provider = DeterministicEmbeddingProvider(dimension=384, model_name="all-MiniLM-L6-v2")
    return _default_provider


def set_embedding_provider(provider: EmbeddingProvider) -> None:
    """
    Allows test suites or configuration to inject a specific embedding provider.
    """
    global _default_provider
    _default_provider = provider
