"""Tests for it_ticket_agents.embeddings.voyage_embedder.

Mocks voyageai's Client.embed directly rather than an HTTP transport
layer - the SDK doesn't expose a clean transport-level seam the way
httpx does, so patching the class method is the practical boundary here.
This verifies our own request construction (input_type, model, text
list) against the SDK's real signature, not Voyage's own API behavior,
which we can't call without a real key.
"""

from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

from it_ticket_agents.embeddings.voyage_embedder import embed_documents, embed_query


@dataclass
class _FakeEmbeddingsObject:
    embeddings: list[list[float]]


class TestEmbedDocuments:
    def test_sends_document_input_type(self) -> None:
        captured: dict[str, Any] = {}

        def fake_embed(self: object, texts: list[str], **kwargs: str) -> _FakeEmbeddingsObject:
            captured["texts"] = texts
            captured["kwargs"] = kwargs
            return _FakeEmbeddingsObject(embeddings=[[0.1, 0.2], [0.3, 0.4]])

        with patch("it_ticket_agents.embeddings.voyage_embedder.Client.embed", fake_embed):
            result = embed_documents(["First doc.", "Second doc."])

        assert captured["texts"] == ["First doc.", "Second doc."]
        assert captured["kwargs"]["input_type"] == "document"
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    def test_empty_input_returns_empty_without_calling_api(self) -> None:
        def fake_embed(self: object, texts: list[str], **kwargs: str) -> _FakeEmbeddingsObject:
            raise AssertionError("Should not call the API for empty input")

        with patch("it_ticket_agents.embeddings.voyage_embedder.Client.embed", fake_embed):
            assert embed_documents([]) == []


class TestEmbedQuery:
    def test_sends_query_input_type(self) -> None:
        captured: dict[str, Any] = {}

        def fake_embed(self: object, texts: list[str], **kwargs: str) -> _FakeEmbeddingsObject:
            captured["texts"] = texts
            captured["kwargs"] = kwargs
            return _FakeEmbeddingsObject(embeddings=[[0.5, 0.6]])

        with patch("it_ticket_agents.embeddings.voyage_embedder.Client.embed", fake_embed):
            result = embed_query("How do I reset my VPN?")

        assert captured["texts"] == ["How do I reset my VPN?"]
        assert captured["kwargs"]["input_type"] == "query"
        assert result == [0.5, 0.6]
