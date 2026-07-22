from __future__ import annotations

import pytest

from mars_ai_os.knowledge import (
    DocumentRecord,
    IngestedDocument,
    KnowledgeSearchIndex,
    SourceKind,
    SourceRecord,
    tokenize,
)


def ingested(title: str, text: str, *, pages: tuple[str, ...] = ()) -> IngestedDocument:
    source = SourceRecord.create(
        uri=f"https://science.nasa.gov/{title.lower().replace(' ', '-')}/",
        title=title,
        publisher="NASA Science",
        kind=SourceKind.REPORT,
        retrieved_at="2026-07-22T10:00:00Z",
    )
    content = text.encode()
    document = DocumentRecord.create(
        source_id=source.source_id,
        content_sha256=DocumentRecord.hash_content(content),
        media_type="application/pdf" if pages else "text/plain",
        byte_length=len(content),
        ingested_at="2026-07-22T10:01:00Z",
        extractor="test",
        extractor_version="1",
    )
    return IngestedDocument(source, document, text, pages)


def test_tokenization_is_case_insensitive_and_deterministic() -> None:
    assert tokenize("Mars' Rocks -- JEZERO-CRATER!") == ("mars", "rocks", "jezero-crater")


def test_search_ranks_passages_and_returns_line_evidence() -> None:
    index = KnowledgeSearchIndex()
    index.add(
        ingested(
            "Rover report",
            "Perseverance collected a sample in Jezero crater.\n\n"
            "The rover stores sealed sample tubes for future recovery.",
        )
    )
    index.add(ingested("Atmosphere report", "Mars has a thin carbon dioxide atmosphere."))

    results = index.search("Jezero sample", limit=2)

    assert len(results) == 2
    assert results[0].passage.text.startswith("Perseverance collected")
    assert results[0].matched_terms == ("jezero", "sample")
    assert results[0].evidence.start_line == 1
    assert results[0].evidence.end_line == 1
    assert results[0].passage.source.publisher == "NASA Science"


def test_pdf_search_preserves_page_number() -> None:
    pages = ("Landing information.", "Jezero crater contains an ancient river delta.")
    index = KnowledgeSearchIndex()
    index.add(ingested("Jezero geology", "\n\n".join(pages), pages=pages))

    result = index.search("ancient river delta")[0]

    assert result.evidence.page == 2
    assert result.evidence.start_line is None


def test_search_order_and_scores_are_repeatable() -> None:
    index = KnowledgeSearchIndex()
    index.add(ingested("Beta", "Mars ice evidence."))
    index.add(ingested("Alpha", "Mars ice evidence."))

    first = index.search("Mars ice")
    second = index.search("Mars ice")

    assert first == second
    assert tuple(item.score for item in first) == tuple(item.score for item in second)
    assert tuple(item.passage.document_id for item in first) == tuple(
        sorted(item.passage.document_id for item in first)
    )


def test_empty_queries_limits_and_duplicate_adds_are_safe() -> None:
    document = ingested("Mission", "Mars rover mission")
    index = KnowledgeSearchIndex()
    first = index.add(document)
    second = index.add(document)

    assert first == second
    assert index.passage_count == 1
    assert index.search("---") == ()
    with pytest.raises(ValueError, match="limit"):
        index.search("Mars", limit=0)
