from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from mars_ai_os.knowledge import (
    FetchedResource,
    NasaDocumentIngestor,
    SourceKind,
    SourceRecord,
)


def source(uri: str = "https://science.nasa.gov/mars/") -> SourceRecord:
    return SourceRecord.create(
        uri=uri,
        title="Mars exploration",
        publisher="NASA Science",
        kind=SourceKind.WEB_PAGE,
        retrieved_at="2026-07-22T10:00:00Z",
    )


def ingestor(content: bytes, media_type: str, final_uri: str | None = None) -> NasaDocumentIngestor:
    return NasaDocumentIngestor(
        fetcher=lambda uri: FetchedResource(content, media_type, final_uri or uri)
    )


def test_ingests_html_as_normalized_visible_text() -> None:
    html = b"<html><style>hidden</style><h1>Mars</h1><p>Perseverance &amp; Ingenuity</p></html>"
    result = ingestor(html, "text/html; charset=utf-8").ingest(
        source(), ingested_at="2026-07-22T10:01:00Z"
    )

    assert result.text == "Mars\n\nPerseverance & Ingenuity"
    assert "hidden" not in result.text
    assert result.document.content_sha256 == result.document.hash_content(html)
    assert result.document.extractor == "stdlib-html"


def test_ingests_plain_text_and_rejects_unsupported_content() -> None:
    result = ingestor(b"Mars   rocks\r\n\r\nMission data", "text/plain").ingest(
        source(), ingested_at="2026-07-22T10:01:00+00:00"
    )
    assert result.text == "Mars rocks\n\nMission data"

    with pytest.raises(ValueError, match="Unsupported"):
        ingestor(b"{}", "application/json").ingest(
            source(), ingested_at="2026-07-22T10:01:00Z"
        )


def test_ingests_pdf_with_page_boundaries() -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 250 Td (Jezero crater evidence) Tj ET")
    page[NameObject("/Contents")] = stream
    buffer = BytesIO()
    writer.write(buffer)

    result = ingestor(buffer.getvalue(), "application/pdf").ingest(
        source(), ingested_at="2026-07-22T10:01:00Z"
    )
    assert result.pages == ("Jezero crater evidence",)
    assert result.text == "Jezero crater evidence"
    assert result.document.extractor == "pypdf"


def test_rejects_untrusted_redirects_and_oversized_documents() -> None:
    with pytest.raises(ValueError, match="trusted NASA host"):
        ingestor(b"data", "text/plain", "https://example.com/copy").ingest(
            source(), ingested_at="2026-07-22T10:01:00Z"
        )

    limited = NasaDocumentIngestor(
        fetcher=lambda uri: FetchedResource(b"12345", "text/plain", uri), max_bytes=4
    )
    with pytest.raises(ValueError, match="exceeds"):
        limited.ingest(source(), ingested_at="2026-07-22T10:01:00Z")
