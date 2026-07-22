# Knowledge provenance model

Mars research knowledge is represented by three immutable records:

- `SourceRecord` identifies the external publisher, URL, source type, retrieval time and mission tags.
- `DocumentRecord` binds fetched bytes to their source and records the extractor used to process them.
- `EvidenceLocator` points to a page, section or line range and retains the supporting quotation.

Source and document identifiers are deterministic SHA-256 hashes of canonical JSON. Timestamps require an
explicit timezone, mission tags are unique and sorted, and ingested content has its own SHA-256 digest.
Together these constraints allow later indexing and answer-generation layers to show where evidence came
from and detect changes in either the published content or extraction process.

This model stores provenance only. Fetching, document extraction, trust policy and answer generation are
separate layers and must not silently weaken these validation rules.

## NASA document ingestion

`NasaDocumentIngestor` accepts HTTPS sources on NASA-owned hosts, applies a configurable byte limit, and
checks the final URL after redirects. HTML, UTF-8 text, and PDF documents are normalized into searchable
text. PDF page boundaries are retained for later citations. Fetching is injectable so test and archival
workflows can ingest fixed bytes without making a live network request.

## Deterministic keyword search

`KnowledgeSearchIndex` splits normalized documents into paragraphs and ranks them with a deterministic
BM25 calculation. Results are ordered by score and stable content identity. Each result carries its source
metadata plus an `EvidenceLocator`: PDF passages retain their page number, while HTML and text passages
retain normalized line ranges. Search is local and dependency-free; it does not generate or infer claims.

## Citation-enforced answers

`KnowledgeAnswerService` retrieves evidence before invoking an `AnswerComposer`. The default extractive
composer returns relevant source passages with sequential citations and performs no unsupported synthesis.
Every evidence claim must reference an included citation. Model-backed composers can be added behind the
same interface, but inferred claims must use the explicit `inference` kind and render with an `Inference:`
label. Empty searches return a limitation instead of fabricating an answer.

## Baseline evaluation

`KnowledgeEvaluator` runs fixed questions through retrieval and answer composition. It reports precision
and recall at K, hit rate, mean reciprocal rank, expected-term coverage, answerability accuracy, and
citation validity. Metrics are rounded deterministically and include per-case results. The initial question
set is stored in `docs/knowledge_evaluation_questions.json`; it contains answerable NASA questions and an
unsupported-claim control that should remain unanswered.
