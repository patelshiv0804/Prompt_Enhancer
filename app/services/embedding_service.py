from __future__ import annotations

import logging
from typing import List

from sentence_transformers import SentenceTransformer
from sentence_transformers.util import normalize_embeddings

from app.core import redis_client
from app.core.config import settings
from app.services.exceptions import EmbeddingGenerationError

logger = logging.getLogger("promptiq.embedding")


class EmbeddingService:
    _model: SentenceTransformer | None = None

    def __init__(self) -> None:
        self.model_name = settings.embedding_model_name

    @property
    def model(self) -> SentenceTransformer:
        # Cache the loaded model at the class level so every EmbeddingService
        # instance (created per-request in several call sites) shares one
        # in-memory model. This makes the startup warmup effective everywhere
        # and prevents repeated multi-second reloads.
        if EmbeddingService._model is None:
            logger.info("Loading embedding model: %s", self.model_name)
            try:
                EmbeddingService._model = SentenceTransformer(self.model_name)
            except Exception as exc:
                logger.exception("Failed to load embedding model %s", self.model_name)
                raise EmbeddingGenerationError("Failed to load embedding model.") from exc
        return EmbeddingService._model

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
        return self.generate([prompt])[0]

    async def generate_for_prompt_cached(self, prompt: str) -> List[float]:
        """Redis-cached variant of generate_for_prompt.

        The model is deterministic: identical text always produces the
        identical vector, so a cache hit is indistinguishable from a fresh
        computation — there is no staleness to reason about. On a miss, or when
        Redis is unavailable, this computes normally.

        Deliberately additive: the sync generate_for_prompt above is unchanged
        and still used by every caller that isn't on an async hot path.
        """
        if not prompt.strip():
            raise EmbeddingGenerationError("Prompt text must not be empty.")

        # The model name is part of the key: a different model yields vectors
        # of different meaning (and possibly different dimensions), which must
        # never be served from an entry written by the previous model.
        key = redis_client.make_key(
            redis_client.NS_EMBED,
            self.model_name.replace("/", "_"),
            redis_client.hash_text(prompt),
        )

        cached = await redis_client.get_json(key)
        if (
            isinstance(cached, list)
            and cached
            and all(isinstance(value, (int, float)) for value in cached)
        ):
            return cached

        embedding = self.generate_for_prompt(prompt)
        await redis_client.set_json(key, embedding, ttl=settings.redis_ttl_embedding)
        return embedding

    def normalize(self, embedding: List[float]) -> List[float]:
        normalized = normalize_embeddings([embedding])
        return normalized[0].tolist()
