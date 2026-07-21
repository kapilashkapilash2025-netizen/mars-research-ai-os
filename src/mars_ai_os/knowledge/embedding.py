"""Text embedding for semantic retrieval.

The default embedder is a deterministic, dependency-free hashing
vectorizer: same design philosophy as the classical QUBO/annealing
intelligence engine (docs/QUANTUM_INSPIRED_ENGINE.md) — a reproducible
classical baseline that requires no external service, GPU, or trained
weights, with a clear extension point for stronger backends later.

To upgrade retrieval quality, implement the ``Embedder`` protocol with
a real model. ``ollama_embedding.OllamaEmbedder`` does exactly this —
an Ollama-served embedding model such as ``nomic-embed-text`` — kept in
its own module since, unlike this one, it makes a real network call.
Pass any ``Embedder`` to ``InMemoryVectorStore`` or
``KnowledgeService(embedder=...)``; no other code needs to change.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_DEFAULT_DIMENSIONS = 256


class Embedder(Protocol):
    """Contract for turning text into a fixed-length vector."""

    def embed(self, text: str) -> tuple[float, ...]: ...


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


@dataclass(frozen=True, slots=True)
class HashingEmbedder:
    """Deterministic bag-of-words hashing vectorizer.

    Not a substitute for a trained embedding model — it captures lexical
    overlap, not semantics. It exists so the knowledge engine is fully
    testable and runnable offline before a real model is wired in.
    """

    dimensions: int = _DEFAULT_DIMENSIONS

    def __post_init__(self) -> None:
        if self.dimensions < 8:
            raise ValueError("dimensions must be at least 8")

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        tokens = _tokenize(text)
        for token in tokens:
            digest = sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0.0:
            return tuple(vector)
        return tuple(component / norm for component in vector)


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """True cosine similarity: dot product normalized by both vector norms.

    Does not assume its inputs are already unit-normalized. HashingEmbedder
    happens to return unit vectors (so this reduces to a plain dot product
    for it), but real model-backed embedders (e.g. OllamaEmbedder) are not
    guaranteed to — normalizing here, not in each Embedder, keeps ranking
    correct regardless of which embedder is configured.
    """

    if len(left) != len(right):
        raise ValueError("Vectors must share the same dimensionality")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(component * component for component in left))
    right_norm = math.sqrt(sum(component * component for component in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    similarity = dot / (left_norm * right_norm)
    # Clamp for float drift so callers always see a value within [-1, 1].
    return max(-1.0, min(1.0, similarity))
