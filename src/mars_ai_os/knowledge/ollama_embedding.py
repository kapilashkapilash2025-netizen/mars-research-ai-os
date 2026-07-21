"""Real semantic embedding backend via a locally-run Ollama model.

Fills the extension point ``embedding.py`` documents: swap
``HashingEmbedder`` (lexical, dependency-free) for ``OllamaEmbedder``
(semantic, requires a local Ollama server) without touching ingestion,
chunking, storage, or answering code — every consumer only depends on
the ``Embedder`` protocol.

This is the concrete fix for the retrieval gap the evaluation harness
measured and documented in docs/KNOWLEDGE_ENGINE.md: ``HashingEmbedder``
scored `hit_rate_at_1 ~0.71` on the bundled labeled questions because
lexical hashing can be pulled toward a longer, topically broad
document. A real embedding model should score higher on the same
``run_knowledge_evaluation()`` check — that is the number to compare
against once this is verified.

Same separation pattern as ``generative.py`` and ``arxiv_connector.py``:
this makes a real network call, so it stays out of the dependency-free
core. Nothing here opens a connection at import time — only ``embed()``
does.

Not runnable in the environment this was authored in (no local Ollama
server there). Verify on a machine with Ollama installed and the model
pulled:

    ollama pull nomic-embed-text
    python -c "
    from mars_ai_os.knowledge import KnowledgeService
    from mars_ai_os.knowledge.demo import _SAMPLE_DOCUMENTS, _SAMPLE_EVALUATION_CASES
    from mars_ai_os.knowledge.evaluation import run_evaluation
    from mars_ai_os.knowledge.ingestion import StaticDocumentConnector
    from mars_ai_os.knowledge.ollama_embedding import OllamaEmbedder

    service = KnowledgeService(
        connectors=(StaticDocumentConnector(_SAMPLE_DOCUMENTS),),
        embedder=OllamaEmbedder(),
    )
    service.start()
    report = run_evaluation(service, _SAMPLE_EVALUATION_CASES)
    print(report.to_dict())
    "
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from mars_ai_os.knowledge.generative import OllamaUnavailableError

_DEFAULT_HOST = "http://localhost:11434"
_DEFAULT_MODEL = "nomic-embed-text"
_DEFAULT_TIMEOUT_S = 30.0


@dataclass(frozen=True, slots=True)
class OllamaEmbedder:
    """Embeds text using a locally-run Ollama embedding model.

    Implements the same ``Embedder`` protocol as ``HashingEmbedder``:
    pass an instance to ``KnowledgeService(embedder=...)`` or
    ``InMemoryVectorStore(embedder=...)`` and nothing else changes.

    Requires the model to already be pulled locally, e.g.
    ``ollama pull nomic-embed-text``. Reuses ``OllamaUnavailableError``
    from ``generative.py`` — both raise the same error type when the
    local Ollama server can't be reached, so callers only need to
    handle one exception regardless of which Ollama integration point
    is in use.
    """

    model: str = _DEFAULT_MODEL
    host: str = _DEFAULT_HOST
    timeout_s: float = _DEFAULT_TIMEOUT_S

    def embed(self, text: str) -> tuple[float, ...]:
        payload = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host.rstrip('/')}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            raise OllamaUnavailableError(
                f"Could not reach Ollama at {self.host} with model {self.model!r}: {error}"
            ) from error

        return parse_embedding_response(body)


def parse_embedding_response(body: bytes) -> tuple[float, ...]:
    """Parse an Ollama ``/api/embeddings`` response body into a vector.

    Separated from ``embed`` so it is unit-testable against a fixed
    sample response, with no network access required.
    """

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise OllamaUnavailableError(
            f"Could not parse Ollama embedding response: {error}"
        ) from error

    embedding = payload.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise OllamaUnavailableError("Ollama returned an empty or malformed embedding")

    try:
        return tuple(float(value) for value in embedding)
    except (TypeError, ValueError) as error:
        raise OllamaUnavailableError(
            f"Ollama embedding contained a non-numeric value: {error}"
        ) from error
