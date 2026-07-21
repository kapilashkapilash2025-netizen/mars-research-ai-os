"""Evidence-first data records for the knowledge-search subsystem.

Every answer the knowledge engine produces must trace back to a
``Citation``. This mirrors the project's "evidence before confidence"
commitment (see docs/PROJECT_CHARTER.md).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Document:
    """A single ingested source document."""

    document_id: str
    title: str
    source: str
    url: str
    text: str

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("document_id cannot be empty")
        if not self.text.strip():
            raise ValueError("Document text cannot be empty")
        if not self.source.strip():
            raise ValueError("Document source cannot be empty")


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable slice of a document, small enough to cite precisely."""

    chunk_id: str
    document_id: str
    title: str
    source: str
    url: str
    text: str

    def __post_init__(self) -> None:
        if not self.chunk_id.strip():
            raise ValueError("chunk_id cannot be empty")
        if not self.text.strip():
            raise ValueError("Chunk text cannot be empty")


@dataclass(frozen=True, slots=True)
class Citation:
    """A traceable reference to the exact passage backing a claim."""

    document_id: str
    title: str
    source: str
    url: str
    snippet: str


@dataclass(frozen=True, slots=True)
class RetrievedPassage:
    """A scored retrieval result, ready to be cited or shown to a reviewer."""

    chunk: Chunk
    score: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0 + 1e-9):
            raise ValueError("score must be within [0, 1]")

    @property
    def citation(self) -> Citation:
        snippet = self.chunk.text.strip()
        if len(snippet) > 240:
            snippet = snippet[:237].rstrip() + "..."
        return Citation(
            document_id=self.chunk.document_id,
            title=self.chunk.title,
            source=self.chunk.source,
            url=self.chunk.url,
            snippet=snippet,
        )


@dataclass(frozen=True, slots=True)
class Answer:
    """A cited answer. No answer may exist without at least one citation."""

    question: str
    text: str
    citations: tuple[Citation, ...]
    confidence: float

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                "Answer must retain at least one citation (evidence before confidence)"
            )
        if not (0.0 <= self.confidence <= 1.0 + 1e-9):
            raise ValueError("confidence must be within [0, 1]")
