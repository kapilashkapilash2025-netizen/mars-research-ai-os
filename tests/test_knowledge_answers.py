from __future__ import annotations

from dataclasses import replace

import pytest

from mars_ai_os.knowledge import (
    AnswerClaim,
    Citation,
    CitedAnswer,
    ClaimKind,
    DocumentRecord,
    IngestedDocument,
    KnowledgeAnswerService,
    KnowledgeSearchIndex,
    SourceKind,
    SourceRecord,
)


def index() -> KnowledgeSearchIndex:
    source = SourceRecord.create(
        uri="https://science.nasa.gov/mission/mars-2020-perseverance/",
        title="Mars 2020 Perseverance",
        publisher="NASA Science",
        kind=SourceKind.WEB_PAGE,
        retrieved_at="2026-07-22T10:00:00Z",
    )
    text = (
        "Perseverance landed in Jezero Crater on February 18, 2021.\n\n"
        "Jezero Crater hosted an ancient river delta."
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
    search = KnowledgeSearchIndex()
    search.add(IngestedDocument(source, document, text, ()))
    return search


def test_service_returns_numbered_citation_ready_evidence() -> None:
    answer = KnowledgeAnswerService(index()).answer("When did Perseverance land?", evidence_limit=1)

    assert answer.text.endswith("[1]")
    assert "February 18, 2021" in answer.text
    assert answer.claims[0].kind is ClaimKind.EVIDENCE
    assert answer.citations[0].source.publisher == "NASA Science"
    assert answer.citations[0].locator.start_line == 1


def test_no_match_is_honest_and_exposes_limitation() -> None:
    answer = KnowledgeAnswerService(index()).answer("photosynthesis chlorophyll")

    assert answer.claims == ()
    assert answer.citations == ()
    assert answer.text == "No supported answer was found in the indexed sources."
    assert answer.limitations == ("No indexed passage matched the query.",)


def test_claim_contract_separates_evidence_from_inference() -> None:
    with pytest.raises(ValueError, match="Evidence claims require"):
        AnswerClaim("Unsupported fact", ClaimKind.EVIDENCE, ())

    inference = AnswerClaim(
        "The delta may be a useful sampling target.",
        ClaimKind.INFERENCE,
        (),
    )
    answer = CitedAnswer("What follows?", (inference,), ())
    assert answer.text.startswith("Inference: ")


def test_answer_rejects_missing_or_disordered_citations() -> None:
    result = index().search("Jezero", limit=1)[0]
    citation = Citation(1, result.passage.source, result.evidence)
    claim = AnswerClaim("Supported", ClaimKind.EVIDENCE, (1,))

    with pytest.raises(ValueError, match="not present"):
        CitedAnswer("Question", (replace(claim, citation_numbers=(2,)),), (citation,))
    with pytest.raises(ValueError, match="sequential"):
        CitedAnswer(
            "Question", (replace(claim, citation_numbers=(2,)),), (replace(citation, number=2),)
        )


def test_service_supports_a_clean_custom_composer_interface() -> None:
    class RecordingComposer:
        def __init__(self) -> None:
            self.seen = ()

        def compose(self, query, results):  # type: ignore[no-untyped-def]
            self.seen = results
            return CitedAnswer(query, (), (), ("Test composer used.",))

    composer = RecordingComposer()
    answer = KnowledgeAnswerService(index(), composer).answer("Jezero", evidence_limit=1)

    assert len(composer.seen) == 1
    assert answer.limitations == ("Test composer used.",)
