from __future__ import annotations

import pytest

from mars_ai_os.knowledge.arxiv_connector import (
    ArxivConnector,
    ArxivUnavailableError,
    parse_arxiv_feed,
)

_SAMPLE_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2101.00001v1</id>
    <title>
      A Study of Martian Atmospheric Dust Dynamics
    </title>
    <summary>
      We present  a model of dust
      lofting in the thin Martian atmosphere.
    </summary>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2102.00002v2</id>
    <title>Seasonal CO2 Ice Cap Variation on Mars</title>
    <summary>Observations of the polar ice caps over three Mars years.</summary>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2103.00003v1</id>
    <title>Malformed Entry Missing Summary</title>
  </entry>
</feed>
"""

_EMPTY_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>
"""


class TestArxivConnectorConfig:
    def test_rejects_blank_query(self) -> None:
        with pytest.raises(ValueError, match="query cannot be empty"):
            ArxivConnector(query="   ")

    def test_rejects_non_positive_max_results(self) -> None:
        with pytest.raises(ValueError, match="max_results"):
            ArxivConnector(query="abs:Mars", max_results=0)

    def test_unreachable_host_raises_clear_error(self) -> None:
        # Port 1 is reserved and refuses connections immediately, keeping
        # this test fast and fully offline.
        connector = ArxivConnector(
            query="abs:Mars", base_url="http://127.0.0.1:1/api/query", timeout_s=1.0
        )
        with pytest.raises(ArxivUnavailableError, match="Could not reach arXiv"):
            connector.fetch()


class TestParseArxivFeed:
    def test_parses_entries_into_documents(self) -> None:
        documents = parse_arxiv_feed(_SAMPLE_FEED)

        # The third entry has no <summary> and must be skipped, not crash.
        assert len(documents) == 2

        first = documents[0]
        assert first.document_id == "arxiv-2101.00001v1"
        assert first.title == "A Study of Martian Atmospheric Dust Dynamics"
        assert first.source == "arxiv"
        assert first.url == "http://arxiv.org/abs/2101.00001v1"
        assert "dust" in first.text.lower()
        # Whitespace from the indented XML must be collapsed.
        assert "  " not in first.title
        assert "  " not in first.text

    def test_second_entry_parsed_correctly(self) -> None:
        documents = parse_arxiv_feed(_SAMPLE_FEED)
        second = documents[1]
        assert second.document_id == "arxiv-2102.00002v2"
        assert second.title == "Seasonal CO2 Ice Cap Variation on Mars"

    def test_custom_source_label_is_applied(self) -> None:
        documents = parse_arxiv_feed(_SAMPLE_FEED, source_label="arxiv-mars-search")
        assert all(document.source == "arxiv-mars-search" for document in documents)

    def test_empty_feed_returns_no_documents(self) -> None:
        assert parse_arxiv_feed(_EMPTY_FEED) == ()

    def test_malformed_xml_raises_clear_error(self) -> None:
        with pytest.raises(ArxivUnavailableError, match="Could not parse arXiv response"):
            parse_arxiv_feed(b"not xml at all <<<")


class TestArxivConnectorIntegrationWithKnowledgeService:
    """Confirms ArxivConnector satisfies the SourceConnector protocol end-to-end
    using a parsed sample feed fed through StaticDocumentConnector — no network.
    """

    def test_parsed_documents_are_ingestible_and_citable(self) -> None:
        from mars_ai_os.knowledge.ingestion import StaticDocumentConnector
        from mars_ai_os.knowledge.service import KnowledgeService

        documents = parse_arxiv_feed(_SAMPLE_FEED)
        service = KnowledgeService(connectors=(StaticDocumentConnector(documents),))
        service.start()

        answer = service.ask("What did the study find about Martian dust?")

        assert answer.citations
        assert answer.citations[0].source == "arxiv"
        service.stop()
