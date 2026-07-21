from __future__ import annotations

import json
from pathlib import Path

import pytest

from mars_ai_os.knowledge import (
    Answer,
    ExtractiveAnswerer,
    HashingEmbedder,
    InMemoryVectorStore,
    KnowledgeService,
    LocalCorpusConnector,
    StaticDocumentConnector,
)
from mars_ai_os.knowledge.demo import run_knowledge_demo
from mars_ai_os.knowledge.embedding import cosine_similarity
from mars_ai_os.knowledge.generative import OllamaAnswerer, OllamaUnavailableError
from mars_ai_os.knowledge.models import Chunk, Document, RetrievedPassage
from mars_ai_os.knowledge.store import chunk_document


def _document(
    document_id: str = "doc-1", text: str = "Mars has two moons, Phobos and Deimos."
) -> Document:
    return Document(
        document_id=document_id,
        title="Moons of Mars",
        source="test-fixture",
        url="https://example.invalid/moons",
        text=text,
    )


class TestModels:
    def test_document_rejects_blank_text(self) -> None:
        with pytest.raises(ValueError, match="text cannot be empty"):
            Document(document_id="d", title="t", source="s", url="u", text="   ")

    def test_answer_requires_at_least_one_citation(self) -> None:
        with pytest.raises(ValueError, match="at least one citation"):
            Answer(question="q", text="a", citations=(), confidence=0.5)

    def test_retrieved_passage_rejects_out_of_range_score(self) -> None:
        chunk = Chunk(chunk_id="c", document_id="d", title="t", source="s", url="u", text="x")
        with pytest.raises(ValueError, match="score must be within"):
            RetrievedPassage(chunk=chunk, score=1.5)

    def test_citation_snippet_is_truncated(self) -> None:
        chunk = Chunk(
            chunk_id="c", document_id="d", title="t", source="s", url="u", text="x" * 400
        )
        citation = RetrievedPassage(chunk=chunk, score=1.0).citation
        assert len(citation.snippet) <= 240
        assert citation.snippet.endswith("...")


class TestEmbedding:
    def test_embedding_is_deterministic(self) -> None:
        embedder = HashingEmbedder()
        assert embedder.embed("Mars atmosphere") == embedder.embed("Mars atmosphere")

    def test_similar_text_scores_higher_than_unrelated_text(self) -> None:
        embedder = HashingEmbedder()
        query = embedder.embed("Mars atmosphere carbon dioxide")
        related = embedder.embed("The Mars atmosphere is mostly carbon dioxide gas")
        unrelated = embedder.embed("Quarterly bakery sales report for downtown branch")
        assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)

    def test_rejects_tiny_dimensions(self) -> None:
        with pytest.raises(ValueError, match="dimensions"):
            HashingEmbedder(dimensions=2)

    def test_cosine_similarity_rejects_mismatched_dimensions(self) -> None:
        with pytest.raises(ValueError, match="dimensionality"):
            cosine_similarity((1.0, 0.0), (1.0, 0.0, 0.0))

    def test_cosine_similarity_normalizes_non_unit_vectors(self) -> None:
        assert cosine_similarity((2.0, 0.0), (10.0, 0.0)) == pytest.approx(1.0)
        assert cosine_similarity((3.0, 4.0), (30.0, 40.0)) == pytest.approx(1.0)

    def test_cosine_similarity_zero_vector_returns_zero(self) -> None:
        assert cosine_similarity((0.0, 0.0), (1.0, 1.0)) == 0.0


class TestChunking:
    def test_chunk_document_splits_on_sentence_boundaries(self) -> None:
        document = _document(
            text="Mars is the fourth planet. It is often called the Red Planet. "
            "Its thin atmosphere is mostly carbon dioxide."
        )
        chunks = chunk_document(document, max_chunk_chars=60)
        assert len(chunks) >= 2
        assert all(chunk.document_id == document.document_id for chunk in chunks)
        # Reassembled chunk text preserves every sentence, none dropped.
        reassembled = " ".join(chunk.text for chunk in chunks)
        assert "Red Planet" in reassembled
        assert "carbon dioxide" in reassembled

    def test_rejects_tiny_chunk_size(self) -> None:
        with pytest.raises(ValueError, match="max_chunk_chars"):
            chunk_document(_document(), max_chunk_chars=10)


class TestInMemoryVectorStore:
    def test_query_ranks_relevant_chunk_first(self) -> None:
        store = InMemoryVectorStore()
        store.add_document(_document("doc-moons", "Phobos and Deimos are the two moons of Mars."))
        store.add_document(_document("doc-weather", "Dust storms on Mars can last for weeks."))

        results = store.query("How many moons does Mars have?", top_k=2)

        assert results[0].chunk.document_id == "doc-moons"
        assert results[0].score >= results[1].score

    def test_query_on_empty_store_returns_nothing(self) -> None:
        assert InMemoryVectorStore().query("anything") == ()

    def test_query_rejects_non_positive_top_k(self) -> None:
        store = InMemoryVectorStore()
        store.add_document(_document())
        with pytest.raises(ValueError, match="top_k"):
            store.query("moons", top_k=0)

    def test_clear_removes_all_chunks(self) -> None:
        store = InMemoryVectorStore()
        store.add_document(_document())
        assert store.chunk_count > 0
        store.clear()
        assert store.chunk_count == 0


class TestLocalCorpusConnector:
    def test_fetch_reads_markdown_and_text_files(self, tmp_path: Path) -> None:
        (tmp_path / "note.md").write_text(
            "# Olympus Mons\nThe tallest volcano in the solar system."
        )
        (tmp_path / "note.txt").write_text("Valles Marineris is a vast canyon system.")
        (tmp_path / "ignore.json").write_text(json.dumps({"not": "ingested"}))

        documents = list(LocalCorpusConnector(directory=tmp_path).fetch())

        assert len(documents) == 2
        titles = {document.title for document in documents}
        assert "Olympus Mons" in titles

    def test_fetch_raises_for_missing_directory(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            list(LocalCorpusConnector(directory=tmp_path / "missing").fetch())


class TestExtractiveAnswerer:
    def test_answer_cites_top_passages(self) -> None:
        store = InMemoryVectorStore()
        store.add_document(_document())
        passages = store.query("moons of Mars")

        answer = ExtractiveAnswerer().answer("moons of Mars", passages)

        assert answer.citations
        assert "Phobos" in answer.text or "Deimos" in answer.text

    def test_answer_refuses_without_passages(self) -> None:
        with pytest.raises(ValueError, match="without evidence"):
            ExtractiveAnswerer().answer("anything", ())


class TestKnowledgeService:
    def test_ask_before_start_raises(self) -> None:
        service = KnowledgeService(connectors=(StaticDocumentConnector((_document(),)),))
        with pytest.raises(RuntimeError, match="must be started"):
            service.ask("moons of Mars")

    def test_start_ingests_all_connectors_and_reports_health(self) -> None:
        service = KnowledgeService(
            connectors=(
                StaticDocumentConnector((_document("doc-a"),)),
                StaticDocumentConnector((_document("doc-b", "Valles Marineris is a canyon."),)),
            )
        )
        service.start()

        health = service.health()
        assert health["healthy"] is True
        assert health["documents"] == 2
        assert health["chunks"] >= 2

        answer = service.ask("What are Mars's moons?")
        assert answer.citations

        service.stop()
        assert service.health()["healthy"] is False

    def test_ask_rejects_blank_question(self) -> None:
        service = KnowledgeService(connectors=(StaticDocumentConnector((_document(),)),))
        service.start()
        with pytest.raises(ValueError, match="question cannot be empty"):
            service.ask("   ")


class TestKnowledgeDemo:
    def test_run_knowledge_demo_returns_cited_answer(self) -> None:
        result = run_knowledge_demo()

        assert result["citations"]
        assert result["corpus"]["documents"] == 5
        assert 0.0 <= result["confidence"] <= 1.0


class TestOllamaAnswerer:
    def test_raises_without_passages(self) -> None:
        with pytest.raises(ValueError, match="without evidence"):
            OllamaAnswerer().answer("q", ())

    def test_unreachable_server_raises_clear_error(self) -> None:
        chunk = Chunk(chunk_id="c", document_id="d", title="t", source="s", url="u", text="x")
        passages = (RetrievedPassage(chunk=chunk, score=1.0),)
        # Port 1 is reserved and will refuse the connection immediately,
        # keeping this test fast and fully offline.
        answerer = OllamaAnswerer(host="http://127.0.0.1:1", timeout_s=1.0)
        with pytest.raises(OllamaUnavailableError, match="Could not reach Ollama"):
            answerer.answer("q", passages)
