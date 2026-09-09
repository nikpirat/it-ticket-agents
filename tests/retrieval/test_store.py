"""Tests for it_ticket_agents.retrieval.store.

Uses real Qdrant local/embedded instances (temp on-disk paths), not
mocks - Qdrant's local mode is fully in-process, so there's no reason to
fake what we can actually run. Server-mode connection (settings.qdrant_url)
is what the real application uses; local mode here is purely a testing
convenience that doesn't require Docker.
"""

from pathlib import Path

from qdrant_client import QdrantClient

from it_ticket_agents.retrieval.store import RunbookChunk, create_collection, index_chunks, search


def _make_chunk(text: str, heading: str, source: str, index: int) -> RunbookChunk:
    return RunbookChunk(
        text=text, section_heading=heading, source_document=source, chunk_index=index
    )


class TestCreateCollection:
    def test_creates_collection(self, tmp_path: Path) -> None:
        client = QdrantClient(path=str(tmp_path / "qdrant"))
        create_collection(client, "test_collection")

        assert client.collection_exists("test_collection")

    def test_is_idempotent(self, tmp_path: Path) -> None:
        client = QdrantClient(path=str(tmp_path / "qdrant"))
        create_collection(client, "test_collection")
        create_collection(client, "test_collection")  # should not raise

        assert client.collection_exists("test_collection")


class TestIndexAndSearch:
    def test_indexes_and_retrieves_by_similarity(self, tmp_path: Path) -> None:
        client = QdrantClient(path=str(tmp_path / "qdrant"))
        create_collection(client, "test_collection")

        chunks = [
            _make_chunk("VPN troubleshooting steps.", "VPN-01", "vpn.md", 0),
            _make_chunk("Account lockout resolution.", "ACCT-01", "accounts.md", 0),
        ]
        # 1024-dim vectors matching settings.voyage_embedding_dim
        embeddings = [
            [1.0] + [0.0] * 1023,
            [0.0, 1.0] + [0.0] * 1022,
        ]

        written = index_chunks(client, chunks, embeddings, collection_name="test_collection")
        assert written == 2

        query_vector = [0.9, 0.1] + [0.0] * 1022
        results = search(client, query_vector, collection_name="test_collection", limit=2)

        assert len(results) == 2
        assert results[0].text == "VPN troubleshooting steps."
        assert results[0].section_heading == "VPN-01"
        assert results[0].score > results[1].score

    def test_raises_on_length_mismatch(self, tmp_path: Path) -> None:
        client = QdrantClient(path=str(tmp_path / "qdrant"))
        create_collection(client, "test_collection")

        chunks = [_make_chunk("text", "heading", "doc.md", 0)]
        embeddings: list[list[float]] = []

        try:
            index_chunks(client, chunks, embeddings, collection_name="test_collection")
            raise AssertionError("Expected ValueError for mismatched lengths")
        except ValueError as e:
            assert "must be the same length" in str(e)

    def test_empty_chunks_returns_zero(self, tmp_path: Path) -> None:
        client = QdrantClient(path=str(tmp_path / "qdrant"))
        create_collection(client, "test_collection")

        assert index_chunks(client, [], [], collection_name="test_collection") == 0

    def test_reindexing_same_chunk_is_idempotent(self, tmp_path: Path) -> None:
        client = QdrantClient(path=str(tmp_path / "qdrant"))
        create_collection(client, "test_collection")

        chunk = _make_chunk("Original text.", "Heading", "doc.md", 0)
        vector = [1.0] + [0.0] * 1023
        index_chunks(client, [chunk], [vector], collection_name="test_collection")

        updated_chunk = _make_chunk("Updated text.", "Heading", "doc.md", 0)
        index_chunks(client, [updated_chunk], [vector], collection_name="test_collection")

        results = search(client, vector, collection_name="test_collection", limit=10)

        assert len(results) == 1  # updated, not duplicated
        assert results[0].text == "Updated text."