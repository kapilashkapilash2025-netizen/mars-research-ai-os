"""In-memory vector store for retrieval-augmented knowledge search."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from mars_ai_os.knowledge.embedding import Embedder, HashingEmbedder, cosine_similarity
from mars_ai_os.knowledge.models import Chunk, Document, RetrievedPassage

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_DEFAULT_MAX_CHUNK_CHARS = 480


def chunk_document(
    document: Document, *, max_chunk_chars: int = _DEFAULT_MAX_CHUNK_CHARS
) -> tuple[Chunk, ...]:
    """Split a document into citation-sized chunks on sentence boundaries."""

    if max_chunk_chars < 40:
        raise ValueError("max_chunk_chars must be at least 40")

    sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(document.text.strip()) if s.strip()]
    if not sentences:
        sentences = [document.text.strip()]

    chunks: list[Chunk] = []
    buffer: list[str] = []
    buffer_len = 0
    index = 0

    def flush() -> None:
        nonlocal buffer, buffer_len, index
        if not buffer:
            return
        chunks.append(
            Chunk(
                chunk_id=f"{document.document_id}::{index}",
                document_id=document.document_id,
                title=document.title,
                source=document.source,
                url=document.url,
                text=" ".join(buffer),
            )
        )
        index += 1
        buffer = []
        buffer_len = 0

    for sentence in sentences:
        if buffer and buffer_len + len(sentence) + 1 > max_chunk_chars:
            flush()
        buffer.append(sentence)
        buffer_len += len(sentence) + 1
    flush()

    return tuple(chunks)


@dataclass(slots=True)
class InMemoryVectorStore:
    """Deterministic, dependency-free vector store.

    Swap ``embedder`` for a real model-backed ``Embedder`` to improve
    retrieval quality without touching ingestion or querying code.
    """

    embedder: Embedder = field(default_factory=HashingEmbedder)
    _chunks: list[Chunk] = field(default_factory=list, init=False)
    _vectors: list[tuple[float, ...]] = field(default_factory=list, init=False)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def add_document(self, document: Document) -> tuple[Chunk, ...]:
        chunks = chunk_document(document)
        for chunk in chunks:
            self._chunks.append(chunk)
            self._vectors.append(self.embedder.embed(chunk.text))
        return chunks

    def clear(self) -> None:
        self._chunks.clear()
        self._vectors.clear()

    def query(self, text: str, *, top_k: int = 3) -> tuple[RetrievedPassage, ...]:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        if not self._chunks:
            return ()

        query_vector = self.embedder.embed(text)
        scored = [
            RetrievedPassage(chunk=chunk, score=max(0.0, cosine_similarity(query_vector, vector)))
            for chunk, vector in zip(self._chunks, self._vectors, strict=True)
        ]
        scored.sort(key=lambda passage: passage.score, reverse=True)
        return tuple(scored[:top_k])
