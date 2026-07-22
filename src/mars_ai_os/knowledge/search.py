"""Deterministic, citation-ready keyword search for ingested Mars documents."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256

from mars_ai_os.knowledge.ingestion import IngestedDocument
from mars_ai_os.knowledge.models import EvidenceLocator, SourceRecord

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*", re.ASCII)


@dataclass(frozen=True, slots=True)
class IndexedPassage:
    passage_id: str
    document_id: str
    source: SourceRecord
    text: str
    terms: tuple[str, ...]
    position: int
    page: int | None = None
    start_line: int | None = None
    end_line: int | None = None

    def evidence(self) -> EvidenceLocator:
        return EvidenceLocator(
            document_id=self.document_id,
            quote=self.text,
            page=self.page,
            start_line=self.start_line,
            end_line=self.end_line,
        )


@dataclass(frozen=True, slots=True)
class SearchResult:
    score: float
    passage: IndexedPassage
    matched_terms: tuple[str, ...]

    @property
    def evidence(self) -> EvidenceLocator:
        return self.passage.evidence()


class KnowledgeSearchIndex:
    """Small in-memory BM25 index with stable ranking and evidence locations."""

    def __init__(self, *, k1: float = 1.2, b: float = 0.75) -> None:
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("BM25 requires k1 > 0 and 0 <= b <= 1")
        self._k1 = k1
        self._b = b
        self._passages: dict[str, IndexedPassage] = {}

    @property
    def passage_count(self) -> int:
        return len(self._passages)

    def add(self, ingested: IngestedDocument) -> tuple[IndexedPassage, ...]:
        passages = _passages(ingested)
        for passage in passages:
            self._passages[passage.passage_id] = passage
        return passages

    def search(self, query: str, *, limit: int = 5) -> tuple[SearchResult, ...]:
        if limit < 1:
            raise ValueError("Search limit must be positive")
        query_terms = tuple(dict.fromkeys(tokenize(query)))
        if not query_terms or not self._passages:
            return ()

        passages = tuple(self._passages.values())
        average_length = sum(len(item.terms) for item in passages) / len(passages)
        frequencies = {term: sum(term in item.terms for item in passages) for term in query_terms}
        normalized_phrase = " ".join(query_terms)
        results: list[SearchResult] = []
        for passage in passages:
            counts = Counter(passage.terms)
            matched = tuple(term for term in query_terms if counts[term])
            if not matched:
                continue
            score = 0.0
            length_ratio = len(passage.terms) / average_length if average_length else 0.0
            for term in matched:
                document_frequency = frequencies[term]
                inverse_frequency = math.log(
                    1 + (len(passages) - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                frequency = counts[term]
                denominator = frequency + self._k1 * (1 - self._b + self._b * length_ratio)
                score += inverse_frequency * (frequency * (self._k1 + 1) / denominator)
            if len(query_terms) > 1 and normalized_phrase in " ".join(passage.terms):
                score += 0.25
            results.append(SearchResult(round(score, 8), passage, matched))

        results.sort(
            key=lambda item: (
                -item.score,
                item.passage.document_id,
                item.passage.position,
                item.passage.passage_id,
            )
        )
        return tuple(results[:limit])


def tokenize(value: str) -> tuple[str, ...]:
    return tuple(TOKEN_PATTERN.findall(value.casefold()))


def _passages(ingested: IngestedDocument) -> tuple[IndexedPassage, ...]:
    located: list[tuple[str, int | None, int | None, int | None]] = []
    if ingested.pages:
        for page_number, page in enumerate(ingested.pages, start=1):
            located.extend((text, page_number, None, None) for text, _, _ in _paragraphs(page))
    else:
        located.extend((text, None, start, end) for text, start, end in _paragraphs(ingested.text))

    output = []
    for position, (text, page, start_line, end_line) in enumerate(located):
        terms = tokenize(text)
        if not terms:
            continue
        identity = f"{ingested.document.document_id}:{position}:{text}".encode()
        output.append(
            IndexedPassage(
                passage_id=sha256(identity).hexdigest(),
                document_id=ingested.document.document_id,
                source=ingested.source,
                text=text,
                terms=terms,
                position=position,
                page=page,
                start_line=start_line,
                end_line=end_line,
            )
        )
    return tuple(output)


def _paragraphs(text: str) -> tuple[tuple[str, int, int], ...]:
    output: list[tuple[str, int, int]] = []
    current: list[str] = []
    start = 1
    lines = text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if line.strip():
            if not current:
                start = line_number
            current.append(line.strip())
        elif current:
            output.append((" ".join(current), start, line_number - 1))
            current = []
    if current:
        output.append((" ".join(current), start, len(lines)))
    return tuple(output)
