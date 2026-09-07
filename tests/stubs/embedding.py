"""
StubEmbeddingService — a deterministic, dependency-free vector encoder.

WHY NOT THE REAL MODEL
----------------------
``EmbeddingService`` loads ``sentence-transformers/all-MiniLM-L6-v2``: seconds of
cold start, ~90 MB of RAM, and a hard dependency on the Hugging Face cache being
present. Paying that in every unit and integration test is not worth it, so this
stub produces 384-dimensional vectors by *feature hashing* instead.

WHAT THE VECTORS ARE GOOD FOR
-----------------------------
Signed hashing of word tokens into 384 buckets, then L2 normalisation. Because
identical tokens always land in the same bucket with the same sign, cosine
similarity between two stub vectors is a real (if crude) measure of lexical
overlap: identical text scores 1.0, text sharing half its words scores around
0.5, unrelated text scores near 0. That is enough to exercise every code path
that ranks, thresholds or deduplicates by similarity.

WHAT THEY ARE NOT GOOD FOR
--------------------------
The cloned ``templates`` rows carry vectors produced by the *real* MiniLM model.
A stub query vector has no meaningful relationship to those, so similarity
against stored template embeddings is effectively noise. Two consequences:

* Enhancement/retrieval tests must pass a ``role`` and ``mode`` that exactly
  match rows in the database. ``TemplateRetrievalService`` skips its similarity
  threshold when both were explicit, so selection stays deterministic.
* Any test making a claim about *semantic* quality must use the
  ``real_embedding_service`` fixture and carry the ``slow`` marker.

The vectors are still 384-dimensional and unit-length, so they are valid input
for the ``Vector(384)`` columns and for pgvector's cosine operator.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import List

from app.core.config import settings
from app.services.exceptions import EmbeddingGenerationError

EMBEDDING_DIM = 384

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def hashed_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """Signed feature hash of ``text`` into a unit-length ``dim``-vector."""
    vector = [0.0] * dim
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        # Text with no alphanumeric tokens (e.g. "!!!"). Return a fixed unit
        # vector rather than zeros: pgvector's cosine distance is undefined for
        # the zero vector and would surface as a confusing database error.
        vector[0] = 1.0
        return vector
    return [value / norm for value in vector]


class StubEmbeddingService:
    """Drop-in replacement for ``app.services.embedding_service.EmbeddingService``.

    Mirrors the full public surface, including the sync variants the app does not
    currently call, so a new call site can't silently fall through to the real
    model.
    """

    def __init__(self) -> None:
        # Reported by call sites that key caches on the model identity. Marked as
        # a stub so a cache entry written under test can never be mistaken for
        # one written by the real model.
        self.model_name = f"stub/{settings.embedding_model_name}"
        self.calls: list[str] = []
        # Stands in for the Redis cache: process-local, so nothing leaks between
        # tests through a shared Redis instance.
        self._cache: dict[str, List[float]] = {}

    @property
    def model(self):  # pragma: no cover - guard, not behaviour
        raise AssertionError(
            "StubEmbeddingService.model was accessed — something is trying to "
            "load the real sentence-transformers model. Use the "
            "real_embedding_service fixture (marked slow) if that is intended."
        )

    # ── Sync API ──────────────────────────────────────────────────────────

    def generate(self, texts: List[str]) -> List[List[float]]:
        self.calls.extend(texts)
        return [hashed_embedding(text) for text in texts]

    def generate_for_prompt(self, prompt: str) -> List[float]:
        if not prompt.strip():
            raise EmbeddingGenerationError("Prompt text must not be empty.")
        return self.generate([prompt])[0]

    # ── Async API (what the application actually calls) ────────────────────
    # No thread offload: hashing 384 buckets is microseconds, and staying on the
    # loop keeps test failures readable.

    async def generate_async(self, texts: List[str]) -> List[List[float]]:
        return self.generate(texts)

    async def generate_for_prompt_async(self, prompt: str) -> List[float]:
        if not prompt.strip():
            raise EmbeddingGenerationError("Prompt text must not be empty.")
        return self.generate_for_prompt(prompt)

    async def generate_for_prompt_cached(self, prompt: str) -> List[float]:
        if not prompt.strip():
            raise EmbeddingGenerationError("Prompt text must not be empty.")
        cached = self._cache.get(prompt)
        if cached is not None:
            return list(cached)
        embedding = self.generate_for_prompt(prompt)
        self._cache[prompt] = embedding
        return list(embedding)

    def normalize(self, embedding: List[float]) -> List[float]:
        norm = math.sqrt(sum(value * value for value in embedding))
        if norm == 0.0:
            return list(embedding)
        return [value / norm for value in embedding]

    # ── Test helpers ──────────────────────────────────────────────────────

    def reset(self) -> None:
        self.calls.clear()
        self._cache.clear()
