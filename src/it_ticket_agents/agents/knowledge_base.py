"""Knowledge-base agent node: retrieves relevant runbook context.

No LLM call needed here - the ticket's own title and description (plus
the diagnosis agent's findings, once available) provide enough
natural-language material to search against directly, avoiding an
unnecessary LLM call just to reformulate a search query.
"""

from collections.abc import Callable

from qdrant_client import QdrantClient

from it_ticket_agents.agents.state import TicketState
from it_ticket_agents.config.settings import settings
from it_ticket_agents.embeddings.voyage_embedder import embed_query
from it_ticket_agents.retrieval.store import SearchResult, search


def _default_qdrant_client_builder() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def _build_search_query(state: TicketState) -> str:
    """Combine ticket details and (if available) the diagnosis agent's
    findings into one search query - a diagnosis that's already
    identified a specific symptom narrows retrieval meaningfully compared
    to the ticket's raw description alone.
    """
    ticket = state["ticket"]
    diagnosis = state.get("diagnosis", "")
    parts = [str(ticket.get("title", "")), str(ticket.get("description", ""))]
    if diagnosis:
        parts.append(diagnosis)
    return " ".join(p for p in parts if p)


def knowledge_base_node(
    state: TicketState,
    qdrant_client_builder: Callable[[], QdrantClient] = _default_qdrant_client_builder,
    embed_query_fn: Callable[[str], list[float]] = embed_query,
    search_fn: Callable[..., list[SearchResult]] = search,
) -> dict[str, object]:
    """LangGraph node: retrieve relevant runbook chunks for this ticket.

    Injectable dependencies default to the real Qdrant/Voyage-backed
    implementations; tests pass fakes so no live Qdrant server or Voyage
    API key is needed.
    """
    query_text = _build_search_query(state)
    query_vector = embed_query_fn(query_text)

    client = qdrant_client_builder()
    results = search_fn(client, query_vector)

    kb_context = [
        {
            "text": r.text,
            "section_heading": r.section_heading,
            "source_document": r.source_document,
            "score": r.score,
        }
        for r in results
    ]

    return {"kb_context": kb_context}