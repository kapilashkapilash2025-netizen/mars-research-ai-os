"""Reproducible evaluation for the provenance-record search interface."""

from __future__ import annotations

from dataclasses import dataclass

from mars_ai_os.knowledge.answers import KnowledgeAnswerService
from mars_ai_os.knowledge.search import KnowledgeSearchIndex, tokenize


@dataclass(frozen=True, slots=True)
class ProvenanceEvaluationCase:
    case_id: str
    question: str
    relevant_source_uris: tuple[str, ...]
    expected_answer_terms: tuple[str, ...] = ()
    expect_answer: bool = True

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.question.strip():
            raise ValueError("Evaluation case ID and question cannot be empty")
        if tuple(sorted(set(self.relevant_source_uris))) != self.relevant_source_uris:
            raise ValueError("Relevant source URIs must be unique and sorted")
        normalized_terms = tuple(term.casefold() for term in self.expected_answer_terms)
        if tuple(sorted(set(normalized_terms))) != normalized_terms:
            raise ValueError("Expected answer terms must be lowercase, unique, and sorted")
        if self.expect_answer and not self.relevant_source_uris:
            raise ValueError("Answerable cases require at least one relevant source")


@dataclass(frozen=True, slots=True)
class CaseEvaluation:
    case_id: str
    retrieved_source_uris: tuple[str, ...]
    relevant_retrieved: int
    reciprocal_rank: float
    answer_returned: bool
    answer_term_coverage: float
    citations_valid: bool


@dataclass(frozen=True, slots=True)
class ProvenanceEvaluationReport:
    case_count: int
    retrieval_precision_at_k: float
    retrieval_recall_at_k: float
    retrieval_hit_rate_at_k: float
    mean_reciprocal_rank: float
    answer_term_coverage: float
    answerability_accuracy: float
    citation_validity_rate: float
    cases: tuple[CaseEvaluation, ...]


class KnowledgeEvaluator:
    def __init__(self, index: KnowledgeSearchIndex) -> None:
        self._index = index
        self._answers = KnowledgeAnswerService(index)

    def evaluate(
        self, cases: tuple[ProvenanceEvaluationCase, ...], *, k: int = 3
    ) -> ProvenanceEvaluationReport:
        if not cases:
            raise ValueError("Evaluation requires at least one case")
        if k < 1:
            raise ValueError("Evaluation k must be positive")
        ids = tuple(case.case_id for case in cases)
        if len(set(ids)) != len(ids):
            raise ValueError("Evaluation case IDs must be unique")
        results = tuple(self._evaluate_case(case, k) for case in cases)
        answerable = tuple(
            (case, result)
            for case, result in zip(cases, results, strict=True)
            if case.expect_answer
        )
        precision = sum(result.relevant_retrieved / k for result in results) / len(results)
        recall = sum(
            result.relevant_retrieved / len(case.relevant_source_uris)
            if case.relevant_source_uris
            else float(not result.retrieved_source_uris)
            for case, result in zip(cases, results, strict=True)
        ) / len(results)
        return ProvenanceEvaluationReport(
            len(cases),
            _rounded(precision),
            _rounded(recall),
            _rounded(sum(item.relevant_retrieved > 0 for item in results) / len(results)),
            _rounded(sum(item.reciprocal_rank for item in results) / len(results)),
            _rounded(
                sum(item.answer_term_coverage for _, item in answerable) / len(answerable)
                if answerable
                else 1.0
            ),
            _rounded(
                sum(
                    result.answer_returned == case.expect_answer
                    for case, result in zip(cases, results, strict=True)
                )
                / len(results)
            ),
            _rounded(sum(item.citations_valid for item in results) / len(results)),
            results,
        )

    def _evaluate_case(self, case: ProvenanceEvaluationCase, k: int) -> CaseEvaluation:
        search_results = self._index.search(case.question, limit=k)
        retrieved = tuple(result.passage.source.uri for result in search_results)
        positions = tuple(
            index
            for index, uri in enumerate(retrieved, start=1)
            if uri in case.relevant_source_uris
        )
        answer = self._answers.answer(case.question, evidence_limit=k)
        expected_tokens = {token for term in case.expected_answer_terms for token in tokenize(term)}
        answer_tokens = set(tokenize(answer.text))
        citations = {citation.number for citation in answer.citations}
        return CaseEvaluation(
            case.case_id,
            retrieved,
            sum(uri in case.relevant_source_uris for uri in retrieved),
            _rounded(1 / positions[0] if positions else 0.0),
            bool(answer.claims),
            _rounded(
                len(expected_tokens & answer_tokens) / len(expected_tokens)
                if expected_tokens
                else 1.0
            ),
            all(
                bool(claim.citation_numbers) and set(claim.citation_numbers) <= citations
                for claim in answer.claims
            ),
        )


def _rounded(value: float) -> float:
    return round(value, 6)
