"""Optional LLM-backed answering, grounded in retrieved citations.

This is the integration point for "add a real LLM on top of the
retrieval layer" — the direction discussed for this project. It is kept
separate from the zero-dependency default (``ExtractiveAnswerer``) and
is opt-in only:

- No import in this module runs a model or opens a connection at import
  time. Nothing here executes unless a caller explicitly constructs and
  uses ``OllamaAnswerer``.
- It talks to a locally-run Ollama server (default
  ``http://localhost:11434``) — no data leaves the machine.
- The prompt only ever contains the passages returned by the vector
  store for *this* question, and instructs the model to answer strictly
  from them. It still returns an ``Answer`` with the same citations the
  retriever produced, so downstream code and the "evidence before
  confidence" guarantee do not change based on which ``Answerer`` is
  configured.

This does not train or fine-tune a model. It calls whatever model is
already pulled in Ollama (e.g. ``ollama pull llama3.1``). Fine-tuning on
curated physics/Mars literature is a legitimate later step, but it is a
separate, much heavier effort (data curation, evaluation, GPU time) from
wiring a generation step onto retrieval — see docs/KNOWLEDGE_ENGINE.md.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from mars_ai_os.knowledge.models import Answer, RetrievedPassage

_DEFAULT_HOST = "http://localhost:11434"
_DEFAULT_MODEL = "llama3.1"
_DEFAULT_TIMEOUT_S = 30.0


class OllamaUnavailableError(RuntimeError):
    """Raised when the local Ollama server cannot be reached or errors out."""


def _build_prompt(question: str, passages: tuple[RetrievedPassage, ...]) -> str:
    sources = "\n\n".join(
        f"Source [{index + 1}] ({passage.chunk.title}): {passage.chunk.text.strip()}"
        for index, passage in enumerate(passages)
    )
    return (
        "You are a Mars research assistant. Answer the question using ONLY the "
        "numbered sources below. Cite sources inline as [1], [2], etc. "
        "If the sources do not contain the answer, say so explicitly instead "
        "of guessing.\n\n"
        f"{sources}\n\nQuestion: {question}\nAnswer:"
    )


@dataclass(frozen=True, slots=True)
class OllamaAnswerer:
    """Generates prose over retrieved passages using a local Ollama model."""

    model: str = _DEFAULT_MODEL
    host: str = _DEFAULT_HOST
    timeout_s: float = _DEFAULT_TIMEOUT_S

    def answer(self, question: str, passages: tuple[RetrievedPassage, ...]) -> Answer:
        if not passages:
            raise ValueError(
                "No supporting passages were retrieved; refusing to answer without evidence"
            )

        prompt = _build_prompt(question, passages)
        payload = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode(
            "utf-8"
        )
        request = urllib.request.Request(
            f"{self.host.rstrip('/')}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise OllamaUnavailableError(
                f"Could not reach Ollama at {self.host} with model {self.model!r}: {error}"
            ) from error

        generated_text = str(body.get("response", "")).strip()
        if not generated_text:
            raise OllamaUnavailableError("Ollama returned an empty response")

        citations = tuple(passage.citation for passage in passages)
        return Answer(
            question=question,
            text=generated_text,
            citations=citations,
            confidence=passages[0].score,
        )
