"""Cited Mars knowledge search — Phase 1 of the roadmap.

Retrieval-augmented, not fine-tuned: a deterministic, dependency-free
retriever and extractive answerer by default, with a clearly separated,
opt-in ``OllamaAnswerer`` for generative answers once a local model is
available. See docs/KNOWLEDGE_ENGINE.md for the design rationale.
"""

from mars_ai_os.knowledge.answering import Answerer, ExtractiveAnswerer
from mars_ai_os.knowledge.embedding import Embedder, HashingEmbedder
from mars_ai_os.knowledge.ingestion import (
    LocalCorpusConnector,
    SourceConnector,
    StaticDocumentConnector,
)
from mars_ai_os.knowledge.models import Answer, Chunk, Citation, Document, RetrievedPassage
from mars_ai_os.knowledge.service import KnowledgeService
from mars_ai_os.knowledge.store import InMemoryVectorStore

__all__ = [
    "Answer",
    "Answerer",
    "Chunk",
    "Citation",
    "Document",
    "Embedder",
    "ExtractiveAnswerer",
    "HashingEmbedder",
    "InMemoryVectorStore",
    "KnowledgeService",
    "LocalCorpusConnector",
    "RetrievedPassage",
    "SourceConnector",
    "StaticDocumentConnector",
]
