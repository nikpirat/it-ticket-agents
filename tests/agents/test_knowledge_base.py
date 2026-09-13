"""Tests for it_ticket_agents.agents.knowledge_base.

Uses real local-mode Qdrant (like Phase 2's retrieval tests) - only
embed_query is faked, since that's the one piece requiring a real Voyage
API key.
"""

from pathlib import Path

from qdrant_client import QdrantClient

from it_ticket_agents.agents.knowledge_base import _build_search_query, knowledge_base_node
from it_ticket_agents.agents.state import TicketState
from it_ticket_agents.retrieval.store import RunbookChunk, create_collection, index_chunks


def _make_state(
    title: str = "VPN down", description: str = "Cannot connect", diagnosis: str = ""
) -> TicketState:
    return TicketState(
        ticket_id="T-1",
        ticket={"title": title, "description": description, "priority": "high"},
        category="network",
        escalate_immediately=False,
        supervisor_reasoning="",
        diagnosis=diagnosis,
        kb_context=[],
        proposed_action=None,
        requires_human_approval=False,
        status="",
        resolution_notes="",
    )


class TestBuildSearchQuery:
    def test_combines_title_and_description(self) -> None:
        state = _make_state(title="VPN down", description="Cannot connect")

        query = _build_search_query(state)

        assert "VPN down" in query
        assert "Cannot connect" in query

    def test_includes_diagnosis_when_present(self) -> None:
        state = _make_state(diagnosis="Service vpn-gateway is down.")

        query = _build_search_query(state)

        assert "Service vpn-gateway is down." in query

    def test_omits_empty_diagnosis(self) -> None:
        state = _make_state(diagnosis="")

        query = _build_search_query(state)

        assert query.count("  ") == 0  # no double-space artifact from an empty part


class TestKnowledgeBaseNode:
    def test_retrieves_and_formats_relevant_chunks(self, tmp_path: Path) -> None:
        client = QdrantClient(path=str(tmp_path / "qdrant"))
        create_collection(client, "test_kb")
        chunks = [
            RunbookChunk(
                text="Restart vpn-gateway to resolve gateway unreachable errors.",
                section_heading="VPN fix",
                source_document="vpn.md",
                chunk_index=0,
            ),
        ]
        vector = [1.0] + [0.0] * 1023
        index_chunks(client, chunks, [vector], collection_name="test_kb")

        def fake_embed_query(text: str) -> list[float]:
            return vector

        def fake_search(client: QdrantClient, query_vector: list[float]) -> list:  # type: ignore[type-arg]
            from it_ticket_agents.retrieval.store import search

            return search(client, query_vector, collection_name="test_kb")

        result = knowledge_base_node(
            _make_state(),
            qdrant_client_builder=lambda: client,
            embed_query_fn=fake_embed_query,
            search_fn=fake_search,
        )

        assert len(result["kb_context"]) == 1
        chunk = result["kb_context"][0]
        assert chunk["section_heading"] == "VPN fix"
        assert chunk["source_document"] == "vpn.md"
        assert "score" in chunk

    def test_no_matches_returns_empty_context(self, tmp_path: Path) -> None:
        client = QdrantClient(path=str(tmp_path / "qdrant"))
        create_collection(client, "test_kb")

        def fake_embed_query(text: str) -> list[float]:
            return [1.0] + [0.0] * 1023

        def fake_search(client: QdrantClient, query_vector: list[float]) -> list:  # type: ignore[type-arg]
            from it_ticket_agents.retrieval.store import search

            return search(client, query_vector, collection_name="test_kb")

        result = knowledge_base_node(
            _make_state(),
            qdrant_client_builder=lambda: client,
            embed_query_fn=fake_embed_query,
            search_fn=fake_search,
        )

        assert result["kb_context"] == []