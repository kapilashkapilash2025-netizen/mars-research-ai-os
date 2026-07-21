"""Turns retrieved passages into a cited answer.

The default ``ExtractiveAnswerer`` never generates text beyond what was
retrieved — it can only quote and cite, so it cannot hallucinate. A
generative answerer (LLM-backed, e.g. via Ollama) is a strict upgrade
on top of the same retrieved passages and should implement the
``Answerer`` protocol; see docs/KNOWLEDGE_ENGINE.md for the intended
integration point and why it stays optional and clearly labeled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mars_ai_os.knowledge.models import Answer, RetrievedPassage


class Answerer(Protocol):
    """Contract for turning retrieved, cited passages into an answer."""

    def answer(self, question: str, passages: tuple[RetrievedPassage, ...]) -> Answer: ...


@dataclass(frozen=True, slots=True)
class ExtractiveAnswerer:
    """Zero-dependency, hallucination-free default: quotes cited passages."""

    max_passages: int = 3

    def __post_init__(self) -> None:
        if self.max_passages < 1:
            raise ValueError("max_passages must be at least 1")

    def answer(self, question: str, passages: tuple[RetrievedPassage, ...]) -> Answer:
        if not passages:
            raise ValueError(
                "No supporting passages were retrieved; refusing to answer without evidence"
            )

        used = passages[: self.max_passages]
        text = "\n\n".join(
            f"[{index + 1}] {passage.chunk.text.strip()}" for index, passage in enumerate(used)
        )
        citations = tuple(passage.citation for passage in used)
        confidence = used[0].score

        return Answer(question=question, text=text, citations=citations, confidence=confidence)
