"""Pluggable ingestion sources for the knowledge engine.

``SourceConnector`` is the extension point real data sources plug into.
This module ships one dependency-free connector (``LocalCorpusConnector``)
so the engine is fully runnable offline. Network-backed connectors for
public Mars data — the NASA Planetary Data System, ADS/arXiv abstracts,
PDS geosciences node, etc. — should live in their own modules and
implement the same protocol; none of the retrieval or answering code
needs to change when a new connector is added.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from mars_ai_os.knowledge.models import Document, DocumentRecord, SourceRecord

_SUPPORTED_SUFFIXES = (".txt", ".md")


class SourceConnector(Protocol):
    """Contract for anything that can supply documents to the knowledge engine."""

    def fetch(self) -> Iterable[Document]: ...


@dataclass(frozen=True, slots=True)
class LocalCorpusConnector:
    """Reads plain-text or markdown files from a local directory.

    Useful for bundled reference material, cached exports from an
    external API, or manually curated notes — anything already on disk.
    """

    directory: Path
    source_label: str = "local-corpus"

    def fetch(self) -> Iterable[Document]:
        if not self.directory.exists():
            raise FileNotFoundError(f"Corpus directory does not exist: {self.directory}")
        for path in sorted(self.directory.iterdir()):
            if path.suffix.lower() not in _SUPPORTED_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            title = text.splitlines()[0].lstrip("# ").strip() or path.stem
            yield Document(
                document_id=path.stem,
                title=title,
                source=self.source_label,
                url=str(path),
                text=text,
            )


@dataclass(frozen=True, slots=True)
class StaticDocumentConnector:
    """Wraps an already-built, in-memory sequence of documents.

    Handy for tests, demos, and for any future connector (arXiv, PDS,
    mission ops feeds) that fetches over the network in a separate
    step and hands off a finished document list here.
    """

    documents: tuple[Document, ...]

    def fetch(self) -> Iterable[Document]:
        return self.documents


EXTRACTOR_VERSION = "1"
NASA_HOST_SUFFIXES = ("nasa.gov",)
SUPPORTED_MEDIA_TYPES = frozenset(
    {"application/pdf", "text/html", "text/plain", "application/xhtml+xml"}
)


@dataclass(frozen=True, slots=True)
class FetchedResource:
    content: bytes
    media_type: str
    final_uri: str


@dataclass(frozen=True, slots=True)
class IngestedDocument:
    source: SourceRecord
    document: DocumentRecord
    text: str
    pages: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.document.source_id != self.source.source_id:
            raise ValueError("Document does not belong to the supplied source")
        if not self.text.strip():
            raise ValueError("Ingestion produced no searchable text")
        if "\x00" in self.text:
            raise ValueError("Extracted text contains null bytes")


Fetcher = Callable[[str], FetchedResource]


class NasaDocumentIngestor:
    """Fetch and normalize documents from explicitly trusted NASA hosts."""

    def __init__(
        self,
        *,
        fetcher: Fetcher | None = None,
        max_bytes: int = 25_000_000,
        trusted_host_suffixes: tuple[str, ...] = NASA_HOST_SUFFIXES,
    ) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        self._max_bytes = max_bytes
        self._trusted_hosts = tuple(host.lower().lstrip(".") for host in trusted_host_suffixes)
        self._fetcher = fetcher or self._fetch

    def ingest(self, source: SourceRecord, *, ingested_at: str) -> IngestedDocument:
        self._require_trusted_uri(source.uri)
        fetched = self._fetcher(source.uri)
        self._require_trusted_uri(fetched.final_uri)
        if len(fetched.content) > self._max_bytes:
            raise ValueError(f"Document exceeds the {self._max_bytes}-byte ingestion limit")

        media_type = fetched.media_type.partition(";")[0].strip().lower()
        if media_type not in SUPPORTED_MEDIA_TYPES:
            raise ValueError(f"Unsupported document media type: {media_type or 'missing'}")
        text, pages, extractor = _extract(fetched.content, media_type)
        document = DocumentRecord.create(
            source_id=source.source_id,
            content_sha256=DocumentRecord.hash_content(fetched.content),
            media_type=media_type,
            byte_length=len(fetched.content),
            ingested_at=ingested_at,
            extractor=extractor,
            extractor_version=EXTRACTOR_VERSION,
        )
        return IngestedDocument(source, document, text, pages)

    def _require_trusted_uri(self, uri: str) -> None:
        parsed = urlparse(uri)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not any(
            host == suffix or host.endswith(f".{suffix}") for suffix in self._trusted_hosts
        ):
            raise ValueError("NASA ingestion requires an HTTPS URL on a trusted NASA host")

    def _fetch(self, uri: str) -> FetchedResource:
        request = Request(uri, headers={"User-Agent": "mars-research-ai-os/0.1"})
        with urlopen(request, timeout=30) as response:  # noqa: S310 - host is allowlisted above
            content = response.read(self._max_bytes + 1)
            media_type = response.headers.get_content_type()
            final_uri = response.geturl()
        return FetchedResource(content, media_type, final_uri)


def _extract(content: bytes, media_type: str) -> tuple[str, tuple[str, ...], str]:
    if media_type in {"text/html", "application/xhtml+xml"}:
        parser = _VisibleTextParser()
        parser.feed(content.decode("utf-8-sig", errors="replace"))
        text = _normalize_text("\n".join(parser.parts))
        return text, (), "stdlib-html"
    if media_type == "text/plain":
        text = _normalize_text(content.decode("utf-8-sig", errors="replace"))
        return text, (), "utf8-text"

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    pages = tuple(_normalize_text(page.extract_text() or "") for page in reader.pages)
    return _normalize_text("\n\n".join(pages)), pages, "pypdf"


def _normalize_text(value: str) -> str:
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in value.replace("\r", "\n").split("\n"))
    output: list[str] = []
    for line in lines:
        if line:
            output.append(line)
        elif output and output[-1] != "":
            output.append("")
    return "\n".join(output).strip()


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._hidden_depth += 1
        elif tag in {"br", "p", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._hidden_depth:
            self._hidden_depth -= 1
        elif tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self.parts.append(data)
