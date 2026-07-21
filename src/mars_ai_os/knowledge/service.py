"""Kernel-registerable service exposing cited Mars knowledge search."""

from __future__ import annotations

from dataclasses import dataclass, field

from mars_ai_os.knowledge.answering import Answerer, ExtractiveAnswerer
from mars_ai_os.knowledge.embedding import Embedder, HashingEmbedder
from mars_ai_os.knowledge.ingestion import SourceConnector
from mars_ai_os.knowledge.models import Answer, RetrievedPassage
from mars_ai_os.knowledge.store import InMemoryVectorStore


@dataclass(slots=True)
class KnowledgeService:
    """Ingests configured sources and answers questions with citations.

    Implements the ``mars_ai_os.kernel.Service`` protocol so it can be
    registered directly with ``Kernel``, sharing the same lifecycle and
    health reporting as every other subsystem.
    """

    connectors: tuple[SourceConnector, ...] = ()
    embedder: Embedder = field(default_factory=HashingEmbedder)
    answerer: Answerer = field(default_factory=ExtractiveAnswerer)
    top_k: int = 3
    _store: InMemoryVectorStore = field(init=False)
    _document_count: int = field(default=0, init=False)
    _started: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._store = InMemoryVectorStore(embedder=self.embedder)

    @property
    def name(self) -> str:
        return "knowledge"

    def start(self) -> None:
        self._store.clear()
        self._document_count = 0
        for connector in self.connectors:
            for document in connector.fetch():
                self._store.add_document(document)
                self._document_count += 1
        self._started = True

    def stop(self) -> None:
        self._started = False

    def health(self) -> dict[str, object]:
        return {
            "healthy": self._started,
            "documents": self._document_count,
            "chunks": self._store.chunk_count,
        }

    def retrieve(self, question: str, *, top_k: int | None = None) -> tuple[RetrievedPassage, ...]:
        if not self._started:
            raise RuntimeError("KnowledgeService must be started before it can retrieve passages")
        if not question.strip():
            raise ValueError("question cannot be empty")

        return self._store.query(question, top_k=top_k or self.top_k)

    def ask(self, question: str, *, top_k: int | None = None) -> Answer:
        passages = self.retrieve(question, top_k=top_k)
        return self.answerer.answer(question, passages)
