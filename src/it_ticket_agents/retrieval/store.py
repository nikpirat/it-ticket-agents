"""Qdrant vector store for the IT runbook knowledge base.

Server mode from the start (not local/embedded mode) - this project's
agents run as a served system, not a one-off script, so there's a single
source of truth for the index from day one rather than a local-mode
convenience that later needs a migration (a real lesson from a prior
project: two disconnected vector stores - one embedded, one served -
silently drift apart).
"""

import logging
import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from it_ticket_agents.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunbookChunk:
    """A chunk of a runbook document, ready to embed and index."""

    text: str
    section_heading: str
    source_document: str
    chunk_index: int


@dataclass(frozen=True)
class SearchResult:
    """A retrieved runbook chunk with its similarity score, decoupled
    from Qdrant's own point/payload types so callers don't depend on the
    vector store's internal representation.
    """

    text: str
    section_heading: str
    source_document: str
    score: float


def create_collection(
    client: QdrantClient, collection_name: str = settings.kb_collection_name
) -> None:
    """Create the collection if it doesn't already exist. Idempotent."""
    if client.collection_exists(collection_name):
        logger.info("Collection '%s' already exists, skipping creation", collection_name)
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=settings.voyage_embedding_dim, distance=Distance.COSINE),
    )
    logger.info(
        "Created collection '%s' (dim=%d, cosine distance)",
        collection_name,
        settings.voyage_embedding_dim,
    )


def _chunk_point_id(chunk: RunbookChunk) -> str:
    """Deterministic point ID derived from the chunk's source and index —
    re-indexing the same chunk produces the same ID, making indexing
    idempotent (re-running ingestion updates existing points instead of
    duplicating them).
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk.source_document}:{chunk.chunk_index}"))


def index_chunks(
    client: QdrantClient,
    chunks: list[RunbookChunk],
    embeddings: list[list[float]],
    collection_name: str = settings.kb_collection_name,
) -> int:
    """Upsert chunks and their embeddings into the collection. Returns the
    number of points written.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) must be the same length"
        )
    if not chunks:
        return 0

    points = [
        PointStruct(
            id=_chunk_point_id(chunk),
            vector=embedding,
            payload={
                "text": chunk.text,
                "section_heading": chunk.section_heading,
                "source_document": chunk.source_document,
            },
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]

    client.upsert(collection_name=collection_name, points=points)
    logger.info("Indexed %d chunks into '%s'", len(points), collection_name)
    return len(points)


def search(
    client: QdrantClient,
    query_vector: list[float],
    collection_name: str = settings.kb_collection_name,
    limit: int = settings.retrieval_top_k,
) -> list[SearchResult]:
    """Retrieve the top-k most similar runbook chunks to the query vector."""
    results = client.query_points(
        collection_name=collection_name, query=query_vector, limit=limit
    )

    search_results = []
    for point in results.points:
        if point.payload is None:
            logger.warning("Point %s has no payload, skipping", point.id)
            continue
        search_results.append(
            SearchResult(
                text=point.payload["text"],
                section_heading=point.payload["section_heading"],
                source_document=point.payload["source_document"],
                score=point.score,
            )
        )
    return search_results