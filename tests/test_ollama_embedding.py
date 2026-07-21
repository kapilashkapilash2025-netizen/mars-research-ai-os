from __future__ import annotations

import pytest

from mars_ai_os.knowledge.generative import OllamaUnavailableError
from mars_ai_os.knowledge.ollama_embedding import OllamaEmbedder, parse_embedding_response


class TestParseEmbeddingResponse:
    def test_parses_valid_response(self) -> None:
        body = b'{"embedding": [0.1, 0.2, 0.3]}'
        assert parse_embedding_response(body) == (0.1, 0.2, 0.3)

    def test_missing_embedding_key_raises(self) -> None:
        with pytest.raises(OllamaUnavailableError, match="empty or malformed"):
            parse_embedding_response(b'{"other": 1}')

    def test_empty_embedding_list_raises(self) -> None:
        with pytest.raises(OllamaUnavailableError, match="empty or malformed"):
            parse_embedding_response(b'{"embedding": []}')

    def test_non_list_embedding_raises(self) -> None:
        with pytest.raises(OllamaUnavailableError, match="empty or malformed"):
            parse_embedding_response(b'{"embedding": "not-a-list"}')

    def test_malformed_json_raises(self) -> None:
        with pytest.raises(OllamaUnavailableError, match="Could not parse"):
            parse_embedding_response(b"not json at all")

    def test_non_numeric_value_raises(self) -> None:
        with pytest.raises(OllamaUnavailableError, match="non-numeric"):
            parse_embedding_response(b'{"embedding": [0.1, "oops", 0.3]}')


class TestOllamaEmbedder:
    def test_unreachable_server_raises_clear_error(self) -> None:
        # Port 1 is reserved and refuses connections immediately, keeping
        # this test fast and fully offline.
        embedder = OllamaEmbedder(host="http://127.0.0.1:1", timeout_s=1.0)
        with pytest.raises(OllamaUnavailableError, match="Could not reach Ollama"):
            embedder.embed("Mars atmosphere")

    def test_defaults(self) -> None:
        embedder = OllamaEmbedder()
        assert embedder.model == "nomic-embed-text"
        assert embedder.host == "http://localhost:11434"
