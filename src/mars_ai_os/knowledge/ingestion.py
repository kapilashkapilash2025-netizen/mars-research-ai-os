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

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from mars_ai_os.knowledge.models import Document

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
