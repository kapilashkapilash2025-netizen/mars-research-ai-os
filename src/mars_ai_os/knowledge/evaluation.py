"""Baseline retrieval-quality evaluation for the primary knowledge engine."""

from __future__ import annotations

from dataclasses import dataclass

from mars_ai_os.knowledge.service import KnowledgeService


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    question: str
    expected_document_ids: tuple[str, ...]
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("question cannot be empty")
        if not self.expected_document_ids:
            raise ValueError("expected_document_ids cannot be empty")


@dataclass(frozen=True, slots=True)
class EvaluationOutcome:
    case: EvaluationCase
    retrieved_document_ids: tuple[str, ...]
    top_score: float

    @property
    def hit_at_1(self) -> bool:
        return bool(self.retrieved_document_ids) and (
            self.retrieved_document_ids[0] in self.case.expected_document_ids
        )

    @property
    def hit_at_3(self) -> bool:
        return any(
            document_id in self.case.expected_document_ids
            for document_id in self.retrieved_document_ids[:3]
        )

    @property
    def reciprocal_rank(self) -> float:
        for rank, document_id in enumerate(self.retrieved_document_ids, start=1):
            if document_id in self.case.expected_document_ids:
                return 1.0 / rank
        return 0.0


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    outcomes: tuple[EvaluationOutcome, ...]

    def __post_init__(self) -> None:
        if not self.outcomes:
            raise ValueError("outcomes cannot be empty")

    @property
    def case_count(self) -> int:
        return len(self.outcomes)

    @property
    def hit_rate_at_1(self) -> float:
        return sum(1 for outcome in self.outcomes if outcome.hit_at_1) / self.case_count

    @property
    def hit_rate_at_3(self) -> float:
        return sum(1 for outcome in self.outcomes if outcome.hit_at_3) / self.case_count

    @property
    def mean_reciprocal_rank(self) -> float:
        return sum(outcome.reciprocal_rank for outcome in self.outcomes) / self.case_count

    def failing_cases(self) -> tuple[EvaluationOutcome, ...]:
        return tuple(outcome for outcome in self.outcomes if not outcome.hit_at_1)

    def to_dict(self) -> dict[str, object]:
        return {
            "case_count": self.case_count,
            "hit_rate_at_1": self.hit_rate_at_1,
            "hit_rate_at_3": self.hit_rate_at_3,
            "mean_reciprocal_rank": self.mean_reciprocal_rank,
            "failing_questions": [outcome.case.question for outcome in self.failing_cases()],
        }


def run_evaluation(
    service: KnowledgeService, cases: tuple[EvaluationCase, ...], *, top_k: int = 3
) -> EvaluationReport:
    if not cases:
        raise ValueError("cases cannot be empty")
    outcomes = []
    for case in cases:
        passages = service.retrieve(case.question, top_k=top_k)
        outcomes.append(
            EvaluationOutcome(
                case=case,
                retrieved_document_ids=tuple(item.chunk.document_id for item in passages),
                top_score=passages[0].score if passages else 0.0,
            )
        )
    return EvaluationReport(outcomes=tuple(outcomes))
