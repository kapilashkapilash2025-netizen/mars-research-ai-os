from __future__ import annotations

import pytest

from mars_ai_os.knowledge import (
    DocumentRecord,
    IngestedDocument,
    KnowledgeEvaluator,
    KnowledgeSearchIndex,
    SourceKind,
    SourceRecord,
)
from mars_ai_os.knowledge.provenance_evaluation import ProvenanceEvaluationCase

PERSEVERANCE_URI = "https://science.nasa.gov/mission/mars-2020-perseverance/"
ATMOSPHERE_URI = "https://science.nasa.gov/mars/facts/"


def add(index: KnowledgeSearchIndex, uri: str, title: str, text: str) -> None:
    source = SourceRecord.create(
        uri=uri,
        title=title,
        publisher="NASA Science",
        kind=SourceKind.WEB_PAGE,
        retrieved_at="2026-07-22T10:00:00Z",
    )
    content = text.encode()
    document = DocumentRecord.create(
        source_id=source.source_id,
        content_sha256=DocumentRecord.hash_content(content),
        media_type="text/plain",
        byte_length=len(content),
        ingested_at="2026-07-22T10:01:00Z",
        extractor="test",
        extractor_version="1",
    )
    index.add(IngestedDocument(source, document, text, ()))


def test_evaluation_computes_repeatable_baseline_metrics() -> None:
    index = KnowledgeSearchIndex()
    add(
        index,
        PERSEVERANCE_URI,
        "Perseverance",
        "Perseverance landed in Jezero Crater on February 18 2021.",
    )
    add(
        index,
        ATMOSPHERE_URI,
        "Mars facts",
        "The atmosphere of Mars consists mostly of carbon dioxide.",
    )
    cases = (
        ProvenanceEvaluationCase(
            "landing-date",
            "When did Perseverance land in Jezero?",
            (PERSEVERANCE_URI,),
            ("2021", "february"),
        ),
        ProvenanceEvaluationCase(
            "atmosphere",
            "What is the Mars atmosphere mostly made of?",
            (ATMOSPHERE_URI,),
            ("carbon", "dioxide"),
        ),
        ProvenanceEvaluationCase(
            "unsupported",
            "What color are Martian penguins?",
            (),
            expect_answer=False,
        ),
    )

    first = KnowledgeEvaluator(index).evaluate(cases, k=1)
    second = KnowledgeEvaluator(index).evaluate(cases, k=1)

    assert first == second
    assert first.case_count == 3
    assert first.retrieval_precision_at_k == pytest.approx(2 / 3, abs=1e-6)
    assert first.retrieval_recall_at_k == 1.0
    assert first.retrieval_hit_rate_at_k == pytest.approx(2 / 3, abs=1e-6)
    assert first.mean_reciprocal_rank == pytest.approx(2 / 3, abs=1e-6)
    assert first.answer_term_coverage == 1.0
    assert first.answerability_accuracy == 1.0
    assert first.citation_validity_rate == 1.0


def test_evaluation_validates_dataset_and_parameters() -> None:
    evaluator = KnowledgeEvaluator(KnowledgeSearchIndex())
    case = ProvenanceEvaluationCase("unknown", "Unknown question", (), expect_answer=False)

    with pytest.raises(ValueError, match="at least one case"):
        evaluator.evaluate(())
    with pytest.raises(ValueError, match="positive"):
        evaluator.evaluate((case,), k=0)
    with pytest.raises(ValueError, match="unique"):
        evaluator.evaluate((case, case))
    with pytest.raises(ValueError, match="require at least one"):
        ProvenanceEvaluationCase("invalid", "Question", ())
