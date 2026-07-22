from dataclasses import FrozenInstanceError

import pytest

from mars_ai_os.knowledge import DocumentRecord, EvidenceLocator, SourceKind, SourceRecord


def source() -> SourceRecord:
    return SourceRecord.create(
        uri="https://science.nasa.gov/mission/mars-2020-perseverance/",
        title="Mars 2020: Perseverance Rover",
        publisher="NASA Science",
        kind=SourceKind.WEB_PAGE,
        retrieved_at="2026-07-22T10:00:00+05:30",
        mission_ids=("mars-2020", "perseverance"),
    )


def document() -> DocumentRecord:
    payload = b"A deterministic test document."
    return DocumentRecord.create(
        source_id=source().source_id,
        content_sha256=DocumentRecord.hash_content(payload),
        media_type="text/plain",
        byte_length=len(payload),
        ingested_at="2026-07-22T10:05:00+05:30",
        extractor="plain-text",
        extractor_version="1",
    )


def test_source_identity_is_deterministic_and_serializable() -> None:
    first = source()
    second = source()

    assert first == second
    assert len(first.source_id) == 64
    assert first.to_dict()["kind"] == "web_page"
    with pytest.raises(FrozenInstanceError):
        first.title = "Changed"  # type: ignore[misc]


def test_source_rejects_untraceable_or_ambiguous_metadata() -> None:
    with pytest.raises(ValueError, match="absolute HTTP"):
        SourceRecord.create(
            uri="notes/local.txt",
            title="Notes",
            publisher="Unknown",
            kind=SourceKind.OTHER,
            retrieved_at="2026-07-22T10:00:00Z",
        )
    with pytest.raises(ValueError, match="timezone"):
        SourceRecord.create(
            uri="https://example.test/source",
            title="Source",
            publisher="Publisher",
            kind=SourceKind.REPORT,
            retrieved_at="2026-07-22T10:00:00",
        )


def test_document_binds_content_and_extraction_provenance() -> None:
    first = document()
    second = document()

    assert first == second
    assert len(first.document_id) == 64
    assert first.content_sha256 == DocumentRecord.hash_content(b"A deterministic test document.")
    assert first.document_id != DocumentRecord.create(
        source_id=first.source_id,
        content_sha256=first.content_sha256,
        media_type=first.media_type,
        byte_length=first.byte_length,
        ingested_at=first.ingested_at,
        extractor=first.extractor,
        extractor_version="2",
    ).document_id


def test_evidence_requires_a_precise_valid_location() -> None:
    evidence = EvidenceLocator(
        document_id=document().document_id,
        quote="deterministic test document",
        start_line=1,
        end_line=1,
    )
    assert evidence.to_dict()["start_line"] == 1

    with pytest.raises(ValueError, match="requires a page"):
        EvidenceLocator(document_id=document().document_id, quote="Unlocated")
    with pytest.raises(ValueError, match="line range"):
        EvidenceLocator(
            document_id=document().document_id,
            quote="Bad range",
            start_line=2,
            end_line=1,
        )
