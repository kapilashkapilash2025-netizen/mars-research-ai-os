"""arXiv abstract connector — a real ``SourceConnector`` for Mars research.

Fetches paper titles and abstracts from the public arXiv API
(https://arxiv.org/help/api) and turns each result into a ``Document``
the ingestion pipeline can chunk, embed, and cite exactly like any
other source. No API key is required.

Kept separate from ``ingestion.py`` (which only holds dependency-free,
offline connectors) because this one makes a real network call, the
same separation ``generative.py`` uses for the optional Ollama
answerer. Nothing in this module opens a connection at import time —
only ``fetch()`` does.

arXiv's API is free but asks callers to keep request rates reasonable
(no more than one call every three seconds); this connector makes
exactly one request per ``fetch()`` call and leaves rate-limiting
between repeated ``fetch()`` calls to the caller.

Not runnable in the environment these responses were authored in
(no arxiv.org network access there) — ``parse_arxiv_feed`` is unit
tested directly against a fixed sample response, and the network path
should be verified on a machine with normal internet access:

    python -c "
    from mars_ai_os.knowledge.arxiv_connector import ArxivConnector
    docs = ArxivConnector(query='abs:Mars AND abs:atmosphere', max_results=5).fetch()
    for d in docs: print(d.title)
    "
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from mars_ai_os.knowledge.models import Document

_DEFAULT_BASE_URL = "http://export.arxiv.org/api/query"
_DEFAULT_TIMEOUT_S = 15.0
_ATOM_NS = "{http://www.w3.org/2005/Atom}"


class ArxivUnavailableError(RuntimeError):
    """Raised when the arXiv API cannot be reached or returns malformed data."""


@dataclass(frozen=True, slots=True)
class ArxivConnector:
    """Fetches paper abstracts from arXiv matching a search query.

    Example::

        ArxivConnector(query="abs:Mars AND abs:atmosphere", max_results=20)

    See https://arxiv.org/help/api/user-manual for query syntax
    (``ti:``, ``abs:``, ``cat:`` prefixes; boolean ``AND``/``OR``/``ANDNOT``).
    """

    query: str
    max_results: int = 20
    base_url: str = _DEFAULT_BASE_URL
    timeout_s: float = _DEFAULT_TIMEOUT_S
    source_label: str = "arxiv"

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query cannot be empty")
        if self.max_results < 1:
            raise ValueError("max_results must be at least 1")

    def fetch(self) -> tuple[Document, ...]:
        params = urllib.parse.urlencode(
            {
                "search_query": self.query,
                "start": 0,
                "max_results": self.max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
        )
        url = f"{self.base_url}?{params}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_s) as response:
                body = response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            raise ArxivUnavailableError(
                f"Could not reach arXiv at {self.base_url}: {error}"
            ) from error

        return parse_arxiv_feed(body, source_label=self.source_label)


def parse_arxiv_feed(feed_bytes: bytes, *, source_label: str = "arxiv") -> tuple[Document, ...]:
    """Parse an arXiv Atom feed response into ``Document`` records.

    Separated from ``fetch`` so it is unit-testable against a fixed
    sample response, with no network access required.
    """

    try:
        root = ET.fromstring(feed_bytes)
    except ET.ParseError as error:
        raise ArxivUnavailableError(f"Could not parse arXiv response as XML: {error}") from error

    documents: list[Document] = []
    for entry in root.findall(f"{_ATOM_NS}entry"):
        arxiv_id = _child_text(entry, "id")
        title = _child_text(entry, "title")
        summary = _child_text(entry, "summary")
        if not arxiv_id or not title or not summary:
            continue  # skip malformed entries rather than failing the whole batch

        document_id = arxiv_id.rsplit("/", 1)[-1]
        documents.append(
            Document(
                document_id=f"arxiv-{document_id}",
                title=" ".join(title.split()),
                source=source_label,
                url=arxiv_id,
                text=" ".join(summary.split()),
            )
        )

    return tuple(documents)


def _child_text(entry: ET.Element, tag: str) -> str:
    element = entry.find(f"{_ATOM_NS}{tag}")
    return (element.text or "").strip() if element is not None else ""
