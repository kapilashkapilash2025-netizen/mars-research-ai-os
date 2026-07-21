# Knowledge Engine (Phase 1)

Implements the roadmap's Phase 1 milestone: "Build a cited Mars
knowledge-search prototype." This is a retrieval-augmented system, not
a fine-tuned or from-scratch-trained model — see "Why RAG, not training
a model" below.

## Pipeline

```
SourceConnector.fetch() -> Document
        -> chunk_document()          (store.py)
        -> Embedder.embed()          (embedding.py)
        -> InMemoryVectorStore       (store.py)
        -> .query(question)          -> RetrievedPassage (scored, ranked)
        -> Answerer.answer()         -> Answer (text + citations)
```

Every `Answer` carries at least one `Citation` back to a specific
document and snippet — this is enforced in `Answer.__post_init__`, not
just a convention. There is no code path that produces an uncited
answer, matching the project charter's "evidence before confidence"
commitment.

## Extension points

Three protocols make each stage swappable without touching the others:

- **`SourceConnector`** (`ingestion.py`) — where documents come from.
  Ships with `LocalCorpusConnector` (reads `.md`/`.txt` from a
  directory) and `StaticDocumentConnector` (wraps an in-memory list, used
  by tests and the demo). Real Mars data sources — the NASA Planetary
  Data System, ADS/arXiv abstracts, mission ops feeds — should each be a
  new connector implementing `fetch() -> Iterable[Document]`. None of
  these are implemented yet; picking and vetting the actual public
  APIs/licensing terms is the next concrete step, per
  `docs/ROADMAP.md` Phase 1 ("Select public Mars datasets and APIs").
- **`Embedder`** (`embedding.py`) — how text becomes a vector. Ships
  with `HashingEmbedder`, a deterministic, dependency-free bag-of-words
  hash — reproducible, but lexical, not semantic. A trained embedding
  model plugged in behind the same protocol is a direct quality upgrade
  with no other code changes.
- **`Answerer`** (`answering.py`, `generative.py`) — how retrieved
  passages become an answer. `ExtractiveAnswerer` is the default: it
  only quotes retrieved text, so it cannot hallucinate. `OllamaAnswerer`
  is the opt-in generative path described below.

## Why RAG, not training a model

Training a foundation model from scratch on "advanced physics data" was
the original ask this design responds to. It is not the right next
step for this project, for reasons worth recording (per the charter's
"alternatives considered" requirement):

- **Cost**: pretraining a competent language model takes on the order
  of thousands of GPU-days and large curated corpora. This does not fit
  a single contributor's hardware.
- **It doesn't match the actual goal**: the goal is answers grounded in
  verifiable Mars/physics sources with citations. Retrieval already
  gives cited, up-to-date answers over curated sources — training does
  not add citations, it removes the direct link between an answer and
  its source.
- **It's the harder way to get a worse result** for this use case:
  RAG updates instantly when a new document is ingested; a trained
  model requires retraining.

A real fine-tuning step is a legitimate *later* option (e.g., adapting
a small local model's tone or domain vocabulary once a solid evaluation
set exists) — but it should sit on top of a working, cited retrieval
pipeline, not replace it.

## Generative answering (`OllamaAnswerer`)

`OllamaAnswerer` sends only the passages the retriever already ranked
as relevant to a locally-run Ollama server, instructs the model to
answer strictly from them, and still returns the retriever's own
citations — not model-invented ones. It is opt-in: nothing in this
module runs a model or opens a network connection unless a caller
explicitly builds and uses it, and it is not wired into
`KnowledgeService`'s default or into `knowledge-demo`.

```python
from mars_ai_os.knowledge import KnowledgeService, StaticDocumentConnector
from mars_ai_os.knowledge.generative import OllamaAnswerer

service = KnowledgeService(
    connectors=(StaticDocumentConnector(my_documents),),
    answerer=OllamaAnswerer(model="llama3.1"),  # requires `ollama pull llama3.1` locally
)
service.start()
answer = service.ask("What is the Martian atmosphere made of?")
```

If Ollama is not running or the model is not pulled, it raises
`OllamaUnavailableError` rather than falling back silently.

## Try it

```bash
mars-ai-os knowledge-demo --question "What is Mars atmosphere made of?"
```

Runs fully offline against a two-document bundled sample corpus (see
`knowledge/demo.py`) with the default `ExtractiveAnswerer` — no model,
no network call, deterministic output.

## Limitations and next fidelity step

- The bundled sample corpus is illustrative, not a real research
  corpus — no production `SourceConnector` for public Mars datasets
  exists yet.
- `HashingEmbedder` captures lexical overlap, not semantic meaning; it
  will miss paraphrases. It exists to keep the pipeline testable
  offline, not as the target retrieval quality.
- `ExtractiveAnswerer` produces quoted, not fluent, answers by design.
  Fluent generative answers are available via `OllamaAnswerer` once a
  local model is configured, at the cost of requiring that local
  service to be running.
- No evaluation set or retrieval-quality metrics exist yet (roadmap
  Phase 1: "Add evaluation questions and baseline quality metrics").
