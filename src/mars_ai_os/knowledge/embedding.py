"""Text embedding for semantic retrieval.

The default embedder is a deterministic, dependency-free hashing
vectorizer: same design philosophy as the classical QUBO/annealing
intelligence engine (docs/QUANTUM_INSPIRED_ENGINE.md) — a reproducible
classical baseline that requires no external service, GPU, or trained
weights, with a clear extension point for stronger backends later.

To upgrade retrieval quality, implement the ``Embedder`` protocol with
a real model (for example, an Ollama-served embedding model such as
``nomic-embed-text``) and pass it to ``InMemoryVectorStore``. No other
code needs to change.
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
    if len(left) != len(right):
        raise ValueError("Vectors must share the same dimensionality")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    # Vectors from HashingEmbedder.embed are already unit-normalized;
    # clamp for float drift so callers always see a value within [-1, 1].
    return max(-1.0, min(1.0, dot))
