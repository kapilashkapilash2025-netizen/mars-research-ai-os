"""Verified end-to-end demonstration used by the public CLI.

Uses a tiny, hand-written sample corpus (not a live network fetch) so
the demo is fast, deterministic, and runnable offline in CI. Swap
``StaticDocumentConnector`` for ``LocalCorpusConnector`` or a future
network connector to run against real data.
"""

from __future__ import annotations

from mars_ai_os.knowledge.evaluation import EvaluationCase, EvaluationReport, run_evaluation
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
    Document(
        document_id="sample-moons",
        title="Moons of Mars (sample reference note)",
        source="bundled-sample",
        url="docs/KNOWLEDGE_ENGINE.md#sample-corpus",
        text=(
            "Mars has two small moons, Phobos and Deimos, both irregularly "
            "shaped and likely captured asteroids. Phobos orbits so close to "
            "Mars that it completes an orbit in under eight hours, faster "
            "than Mars itself rotates, and is slowly spiraling inward. Deimos "
            "is smaller and orbits farther out with a much slower orbit."
        ),
    ),
    Document(
        document_id="sample-geology",
        title="Olympus Mons and Martian Geology (sample reference note)",
        source="bundled-sample",
        url="docs/KNOWLEDGE_ENGINE.md#sample-corpus",
        text=(
            "Olympus Mons is a shield volcano on Mars and the tallest known "
            "volcano in the solar system, standing about 22 kilometers high, "
            "roughly two and a half times the height of Mount Everest above "
            "sea level. Nearby, Valles Marineris is a canyon system "
            "stretching thousands of kilometers, far longer than Earth's "
            "Grand Canyon."
        ),
    ),
    Document(
        document_id="sample-rovers",
        title="Mars Surface Rovers (sample reference note)",
        source="bundled-sample",
        url="docs/KNOWLEDGE_ENGINE.md#sample-corpus",
        text=(
            "Several robotic rovers have explored the Martian surface, "
            "including Sojourner, Spirit, Opportunity, Curiosity, and "
            "Perseverance. Curiosity landed in Gale Crater in 2012 to study "
            "past habitability. Perseverance landed in Jezero Crater in 2021 "
            "and carries instruments to collect samples for potential future "
            "return to Earth."
        ),
    ),
)

_SAMPLE_EVALUATION_CASES = (
    EvaluationCase(
        question="What is Mars atmosphere made of?",
        expected_document_ids=("sample-atmosphere",),
    ),
    EvaluationCase(
        question="How strong is gravity on the surface of Mars?",
        expected_document_ids=("sample-gravity",),
    ),
    EvaluationCase(
        question="How many moons does Mars have?",
        expected_document_ids=("sample-moons",),
    ),
    EvaluationCase(
        question="What is the tallest volcano in the solar system?",
        expected_document_ids=("sample-geology",),
    ),
    EvaluationCase(
        question="Which rover landed in Jezero Crater?",
        expected_document_ids=("sample-rovers",),
    ),
    EvaluationCase(
        question="What is the atmospheric pressure at the Martian surface?",
        expected_document_ids=("sample-atmosphere",),
    ),
    EvaluationCase(
        question="Name the two moons of Mars.",
        expected_document_ids=("sample-moons",),
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


def run_knowledge_evaluation() -> EvaluationReport:
    """Score retrieval quality against the bundled labeled sample questions.

    Baseline for roadmap Phase 1's "evaluation questions and baseline
    quality metrics" milestone. Only covers the bundled sample corpus —
    see docs/KNOWLEDGE_ENGINE.md limitations for what this does not
    prove about real-world retrieval quality.
    """

    service = KnowledgeService(connectors=(StaticDocumentConnector(_SAMPLE_DOCUMENTS),))
    service.start()
    report = run_evaluation(service, _SAMPLE_EVALUATION_CASES)
    service.stop()
    return report
