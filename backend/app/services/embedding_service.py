"""
Embedding service using Sentence Transformers.
Provides local, fast semantic embeddings using all-MiniLM-L6-v2.
"""

from sentence_transformers import SentenceTransformer
from app.core.config import get_settings
from app.core.logging_config import get_logger
import time
from typing import List
import numpy as np


class EmbeddingService:
    """Manages embedding model loading and text encoding."""

    _instance = None
    _model = None

    def __new__(cls):
        """Singleton pattern to avoid loading the model multiple times."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None:
            self._load_model()

    def _load_model(self):
        """Load the sentence transformer model."""
        logger = get_logger()
        settings = get_settings()

        logger.info(f"Loading embedding model: {settings.embedding_model}")
        start = time.time()

        self._model = SentenceTransformer(settings.embedding_model)

        elapsed = time.time() - start
        logger.info(f"Embedding model loaded in {elapsed:.2f}s")

    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        Encode a list of texts into embedding vectors.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each is a list of floats).
        """
        logger = get_logger()

        if not texts:
            return []

        start = time.time()
        embeddings = self._model.encode(texts, show_progress_bar=False)
        elapsed = time.time() - start

        logger.info(f"Embedded {len(texts)} texts in {elapsed:.2f}s")

        # Convert numpy arrays to lists for ChromaDB compatibility
        if isinstance(embeddings, np.ndarray):
            return embeddings.tolist()
        return [e.tolist() if isinstance(e, np.ndarray) else e for e in embeddings]

    def encode_query(self, query: str) -> List[float]:
        """
        Encode a single query string into an embedding vector.

        Args:
            query: The query text to embed.

        Returns:
            Embedding vector as a list of floats.
        """
        result = self.encode([query])
        return result[0] if result else []

    @property
    def dimension(self) -> int:
        """Return the embedding dimension size."""
        return self._model.get_sentence_embedding_dimension()
