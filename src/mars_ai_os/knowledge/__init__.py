"""Primary retrieval engine plus traceable provenance-record interfaces."""

from mars_ai_os.knowledge.answering import Answerer, ExtractiveAnswerer
from mars_ai_os.knowledge.answers import (
    AnswerClaim,
    CitedAnswer,
    ClaimKind,
    KnowledgeAnswerService,
)
from mars_ai_os.knowledge.answers import (
    Citation as NumberedCitation,
)
from mars_ai_os.knowledge.embedding import Embedder, HashingEmbedder
from mars_ai_os.knowledge.evaluation import (
    EvaluationCase,
    EvaluationOutcome,
    EvaluationReport,
    run_evaluation,
)
from mars_ai_os.knowledge.ingestion import (
    FetchedResource,
    IngestedDocument,
    LocalCorpusConnector,
    NasaDocumentIngestor,
    SourceConnector,
    StaticDocumentConnector,
)
from mars_ai_os.knowledge.models import (
    Answer,
    Chunk,
    Citation,
    Document,
    DocumentRecord,
    EvidenceLocator,
    RetrievedPassage,
    SourceKind,
    SourceRecord,
)
from mars_ai_os.knowledge.provenance_evaluation import (
    CaseEvaluation,
    KnowledgeEvaluator,
    ProvenanceEvaluationCase,
    ProvenanceEvaluationReport,
)
from mars_ai_os.knowledge.search import IndexedPassage, KnowledgeSearchIndex, SearchResult, tokenize
from mars_ai_os.knowledge.service import KnowledgeService
from mars_ai_os.knowledge.store import InMemoryVectorStore

__all__ = [
    "Answer",
    "AnswerClaim",
    "Answerer",
    "CaseEvaluation",
    "Chunk",
    "Citation",
    "CitedAnswer",
    "ClaimKind",
    "Document",
    "DocumentRecord",
    "Embedder",
    "EvaluationCase",
    "EvaluationOutcome",
    "EvaluationReport",
    "EvidenceLocator",
    "ExtractiveAnswerer",
    "FetchedResource",
    "HashingEmbedder",
    "InMemoryVectorStore",
    "IndexedPassage",
    "IngestedDocument",
    "KnowledgeAnswerService",
    "KnowledgeEvaluator",
    "KnowledgeSearchIndex",
    "KnowledgeService",
    "LocalCorpusConnector",
    "NasaDocumentIngestor",
    "NumberedCitation",
    "ProvenanceEvaluationCase",
    "ProvenanceEvaluationReport",
    "RetrievedPassage",
    "SearchResult",
    "SourceConnector",
    "SourceKind",
    "SourceRecord",
    "StaticDocumentConnector",
    "run_evaluation",
    "tokenize",
]
