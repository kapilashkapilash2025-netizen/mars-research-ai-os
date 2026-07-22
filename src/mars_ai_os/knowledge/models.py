"""Evidence-first data records for the knowledge-search subsystem.

Every answer the knowledge engine produces must trace back to a
``Citation``. This mirrors the project's "evidence before confidence"
commitment (see docs/PROJECT_CHARTER.md).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from urllib.parse import urlparse

from mars_ai_os.digital_twin.provenance import canonical_json, canonicalize


@dataclass(frozen=True, slots=True)
class Document:
    """A single ingested source document."""

    document_id: str
    title: str
    source: str
    url: str
    text: str

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("document_id cannot be empty")
        if not self.text.strip():
            raise ValueError("Document text cannot be empty")
        if not self.source.strip():
            raise ValueError("Document source cannot be empty")


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable slice of a document, small enough to cite precisely."""

    chunk_id: str
    document_id: str
    title: str
    source: str
    url: str
    text: str

    def __post_init__(self) -> None:
        if not self.chunk_id.strip():
            raise ValueError("chunk_id cannot be empty")
        if not self.text.strip():
            raise ValueError("Chunk text cannot be empty")


@dataclass(frozen=True, slots=True)
class Citation:
    """A traceable reference to the exact passage backing a claim."""

    document_id: str
    title: str
    source: str
    url: str
    snippet: str


@dataclass(frozen=True, slots=True)
class RetrievedPassage:
    """A scored retrieval result, ready to be cited or shown to a reviewer."""

    chunk: Chunk
    score: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0 + 1e-9):
            raise ValueError("score must be within [0, 1]")

    @property
    def citation(self) -> Citation:
        snippet = self.chunk.text.strip()
        if len(snippet) > 240:
            snippet = snippet[:237].rstrip() + "..."
        return Citation(
            document_id=self.chunk.document_id,
            title=self.chunk.title,
            source=self.chunk.source,
            url=self.chunk.url,
            snippet=snippet,
        )


@dataclass(frozen=True, slots=True)
class Answer:
    """A cited answer. No answer may exist without at least one citation."""

    question: str
    text: str
    citations: tuple[Citation, ...]
    confidence: float

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(
                "Answer must retain at least one citation (evidence before confidence)"
            )
        if not (0.0 <= self.confidence <= 1.0 + 1e-9):
            raise ValueError("confidence must be within [0, 1]")


class SourceKind(StrEnum):
    WEB_PAGE = "web_page"
    PAPER = "paper"
    DATASET = "dataset"
    REPORT = "report"
    IMAGE = "image"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """Identity and provenance for one externally published source."""

    uri: str
    title: str
    publisher: str
    kind: SourceKind
    retrieved_at: str
    published_at: str | None = None
    license: str | None = None
    mission_ids: tuple[str, ...] = ()
    source_id: str = ""

    def __post_init__(self) -> None:
        parsed = urlparse(self.uri)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Source URI must be an absolute HTTP(S) URL")
        if not self.title.strip() or not self.publisher.strip():
            raise ValueError("Source title and publisher cannot be empty")
        _require_iso8601(self.retrieved_at, "retrieved_at")
        if self.published_at is not None:
            _require_iso8601(self.published_at, "published_at")
        if tuple(sorted(set(self.mission_ids))) != self.mission_ids:
            raise ValueError("mission_ids must be unique and sorted")
        _require_optional_digest(self.source_id, "source_id")

    @classmethod
    def create(cls, **values: object) -> SourceRecord:
        record = cls(**values)  # type: ignore[arg-type]
        return replace(record, source_id=_identity_digest(record, "source_id"))

    def to_dict(self) -> dict[str, object]:
        return canonicalize(self)


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    """An immutable representation of content fetched from a source."""

    source_id: str
    content_sha256: str
    media_type: str
    byte_length: int
    ingested_at: str
    extractor: str
    extractor_version: str
    document_id: str = ""

    def __post_init__(self) -> None:
        _require_digest(self.source_id, "source_id")
        _require_digest(self.content_sha256, "content_sha256")
        _require_optional_digest(self.document_id, "document_id")
        if not self.media_type.strip() or "/" not in self.media_type:
            raise ValueError("media_type must be a valid MIME type")
        if self.byte_length < 0:
            raise ValueError("byte_length cannot be negative")
        _require_iso8601(self.ingested_at, "ingested_at")
        if not self.extractor.strip() or not self.extractor_version.strip():
            raise ValueError("Extractor name and version cannot be empty")

    @classmethod
    def create(cls, **values: object) -> DocumentRecord:
        record = cls(**values)  # type: ignore[arg-type]
        return replace(record, document_id=_identity_digest(record, "document_id"))

    @staticmethod
    def hash_content(content: bytes) -> str:
        return sha256(content).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return canonicalize(self)


@dataclass(frozen=True, slots=True)
class EvidenceLocator:
    """A reproducible location inside an ingested document."""

    document_id: str
    quote: str
    page: int | None = None
    section: str | None = None
    start_line: int | None = None
    end_line: int | None = None

    def __post_init__(self) -> None:
        _require_digest(self.document_id, "document_id")
        if not self.quote.strip():
            raise ValueError("Evidence quote cannot be empty")
        if self.page is not None and self.page < 1:
            raise ValueError("Evidence page must be positive")
        if (self.start_line is None) != (self.end_line is None):
            raise ValueError("Evidence line range requires both start_line and end_line")
        if self.start_line is not None and (
            self.start_line < 1 or self.end_line is None or self.end_line < self.start_line
        ):
            raise ValueError("Evidence line range is invalid")
        if self.page is None and self.section is None and self.start_line is None:
            raise ValueError("Evidence requires a page, section, or line range")

    def to_dict(self) -> dict[str, object]:
        return canonicalize(self)


def _identity_digest(record: object, identity_field: str) -> str:
    payload = canonicalize(record)
    payload[identity_field] = ""
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _require_iso8601(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")


def _require_digest(value: str, field: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")


def _require_optional_digest(value: str, field: str) -> None:
    if value:
        _require_digest(value, field)
