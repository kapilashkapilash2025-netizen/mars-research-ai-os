"""Verified end-to-end demonstration used by the public CLI.

Uses a tiny, hand-written sample corpus (not a live network fetch) so
the demo is fast, deterministic, and runnable offline in CI. Swap
``StaticDocumentConnector`` for ``LocalCorpusConnector`` or a future
network connector to run against real data.
"""

from __future__ import annotations

from mars_ai_os.knowledge.ingestion import StaticDocumentConnector
from mars_ai_os.knowledge.models import Document
from mars_ai_os.knowledge.service import KnowledgeService

_SAMPLE_DOCUMENTS = (
    Document(
        document_id="sample-atmosphere",
        title="Mars Atmospheric Composition (sample reference note)",
        source="bundled-sample",
        url="docs/KNOWLEDGE_ENGINE.md#sample-corpus",
        text=(
            "The Martian atmosphere is composed primarily of carbon dioxide, "
            "at roughly 95 percent by volume. Nitrogen makes up about 2.6 "
            "percent and argon about 1.9 percent, with only trace amounts of "
            "oxygen and water vapor. Surface atmospheric pressure averages "
            "around 600 pascals, less than one percent of sea-level pressure "
            "on Earth. This thin atmosphere provides little protection from "
            "radiation and contributes to large daily temperature swings."
        ),
    ),
    Document(
        document_id="sample-gravity",
        title="Mars Surface Gravity (sample reference note)",
        source="bundled-sample",
        url="docs/KNOWLEDGE_ENGINE.md#sample-corpus",
        text=(
            "Surface gravity on Mars is approximately 3.72 meters per second "
            "squared, about 38 percent of Earth's surface gravity. This lower "
            "gravity affects rover mobility design, dust behavior, and long "
            "term human physiology planning for future crewed missions."
        ),
    ),
)


def run_knowledge_demo(question: str = "What is Mars atmosphere made of?") -> dict[str, object]:
    service = KnowledgeService(connectors=(StaticDocumentConnector(_SAMPLE_DOCUMENTS),))
    service.start()
    answer = service.ask(question)
    health = service.health()
    service.stop()

    return {
        "question": answer.question,
        "answer": answer.text,
        "confidence": answer.confidence,
        "citations": [
            {
                "title": citation.title,
                "source": citation.source,
                "url": citation.url,
                "snippet": citation.snippet,
            }
            for citation in answer.citations
        ],
        "corpus": {"documents": health["documents"], "chunks": health["chunks"]},
        "safety": "extractive by default; no generation beyond bundled sample sources",
    }
