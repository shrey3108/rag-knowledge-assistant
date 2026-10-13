import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Manages text embedding generation using Sentence-Transformers with lazy loading."""

    _instance: Optional["EmbeddingService"] = None

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self._model = None

    @classmethod
    def get_instance(cls, model_name: str = "BAAI/bge-small-en-v1.5") -> "EmbeddingService":
        if cls._instance is None or cls._instance.model_name != model_name:
            cls._instance = cls(model_name=model_name)
        return cls._instance

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}...")
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Successfully loaded embedding model: {self.model_name}")
            except Exception as e:
                logger.warning(
                    f"Could not load SentenceTransformer '{self.model_name}': {e}. "
                    "Falling back to deterministic pseudo-embedding for testing/bootstrap."
                )
                self._model = "MOCK"
        return self._model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate normalized embedding vectors for a list of text strings."""
        if not texts:
            return []

        if self.model == "MOCK":
            return [self._pseudo_embedding(t) for t in texts]

        embeddings = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Generate normalized embedding vector for a single query."""
        if self.model == "MOCK":
            return self._pseudo_embedding(query)

        # For BGE models, query instruction can improve retrieval, but standard encode works well
        embedding = self.model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
        return embedding.tolist()

    def _pseudo_embedding(self, text: str, dim: int = 384) -> List[float]:
        """Deterministic pseudo-random embedding generator for offline testing."""
        seed = abs(hash(text)) % (2**32)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dim)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
