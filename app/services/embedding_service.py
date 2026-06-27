from __future__ import annotations

import logging
from typing import List

from sentence_transformers import SentenceTransformer
from sentence_transformers.util import normalize_embeddings

from app.core.config import settings
from app.services.exceptions import EmbeddingGenerationError

logger = logging.getLogger("promptiq.embedding")


class EmbeddingService:
    _model: SentenceTransformer | None = None

    def __init__(self) -> None:
        self.model_name = settings.embedding_model_name

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading embedding model: %s", self.model_name)
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:
                logger.exception("Failed to load embedding model %s", self.model_name)
                raise EmbeddingGenerationError("Failed to load embedding model.") from exc
        return self._model

    def generate(self, texts: List[str]) -> List[float]:
        try:
            embedding = self.model.encode(texts, normalize_embeddings=True)
            if isinstance(embedding, list):
                return embedding
            return embedding.tolist()
        except Exception as exc:
            logger.exception("Embedding generation failed for texts: %s", texts)
            raise EmbeddingGenerationError("Embedding generation failed.") from exc

    def generate_for_prompt(self, prompt: str) -> List[float]:
        if not prompt.strip():
            raise EmbeddingGenerationError("Prompt text must not be empty.")
        return self.generate([prompt])

    def normalize(self, embedding: List[float]) -> List[float]:
        normalized = normalize_embeddings([embedding])
        return normalized[0].tolist()
