"""Citation-enforced answer composition over deterministic knowledge search."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from mars_ai_os.knowledge.models import EvidenceLocator, SourceRecord
from mars_ai_os.knowledge.search import KnowledgeSearchIndex, SearchResult


class ClaimKind(StrEnum):
    EVIDENCE = "evidence"
    INFERENCE = "inference"


@dataclass(frozen=True, slots=True)
class Citation:
    number: int
    source: SourceRecord
    locator: EvidenceLocator

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError("Citation number must be positive")


@dataclass(frozen=True, slots=True)
class AnswerClaim:
    text: str
    kind: ClaimKind
    citation_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Answer claim cannot be empty")
        if tuple(sorted(set(self.citation_numbers))) != self.citation_numbers:
            raise ValueError("Claim citations must be unique and sorted")
        if self.kind is ClaimKind.EVIDENCE and not self.citation_numbers:
            raise ValueError("Evidence claims require at least one citation")


@dataclass(frozen=True, slots=True)
class CitedAnswer:
    query: str
    claims: tuple[AnswerClaim, ...]
    citations: tuple[Citation, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("Answer query cannot be empty")
        expected = tuple(range(1, len(self.citations) + 1))
        actual = tuple(citation.number for citation in self.citations)
        if actual != expected:
            raise ValueError("Citations must be sequential and ordered")
        available = set(actual)
        if any(not set(claim.citation_numbers) <= available for claim in self.claims):
            raise ValueError("Claim refers to a citation that is not present")
        if tuple(sorted(set(self.limitations))) != self.limitations:
            raise ValueError("Limitations must be unique and sorted")

    @property
    def text(self) -> str:
        if not self.claims:
            return "No supported answer was found in the indexed sources."
        lines = []
        for claim in self.claims:
            marker = "Inference: " if claim.kind is ClaimKind.INFERENCE else ""
            references = "".join(f"[{number}]" for number in claim.citation_numbers)
            suffix = f" {references}" if references else ""
            lines.append(f"{marker}{claim.text}{suffix}")
        return "\n".join(lines)


class AnswerComposer(Protocol):
    """Interface for grounded deterministic or model-backed composers."""

    def compose(self, query: str, results: tuple[SearchResult, ...]) -> CitedAnswer: ...


class ExtractiveAnswerComposer:
    """Safe baseline that quotes relevant passages without inventing synthesis."""

    def compose(self, query: str, results: tuple[SearchResult, ...]) -> CitedAnswer:
        citations = tuple(
            Citation(number, result.passage.source, result.evidence)
            for number, result in enumerate(results, start=1)
        )
        claims = tuple(
            AnswerClaim(
                text=result.passage.text,
                kind=ClaimKind.EVIDENCE,
                citation_numbers=(number,),
            )
            for number, result in enumerate(results, start=1)
        )
        limitations = ()
        if not results:
            limitations = ("No indexed passage matched the query.",)
        return CitedAnswer(query, claims, citations, limitations)


class KnowledgeAnswerService:
    """Search first, then delegate only the retrieved evidence to a composer."""

    def __init__(
        self,
        index: KnowledgeSearchIndex,
        composer: AnswerComposer | None = None,
    ) -> None:
        self._index = index
        self._composer = composer or ExtractiveAnswerComposer()

    def answer(self, query: str, *, evidence_limit: int = 3) -> CitedAnswer:
        if not query.strip():
            raise ValueError("Answer query cannot be empty")
        results = self._index.search(query, limit=evidence_limit)
        return self._composer.compose(query, results)
