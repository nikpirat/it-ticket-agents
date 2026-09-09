"""Chunk every runbook in data/runbooks, embed them via Voyage AI, and
index them into Qdrant.

Batches embedding calls (rather than one request per chunk) to reduce
API round-trip overhead.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from qdrant_client import QdrantClient

from it_ticket_agents.config.settings import settings
from it_ticket_agents.embeddings.voyage_embedder import embed_documents
from it_ticket_agents.retrieval.chunk import chunk_all_runbooks
from it_ticket_agents.retrieval.store import create_collection, index_chunks

logger = logging.getLogger(__name__)

BATCH_SIZE = 32
DEFAULT_RUNBOOKS_DIR = Path("data/runbooks")


def _default_qdrant_client_builder() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def run_indexing(
    runbooks_dir: Path = DEFAULT_RUNBOOKS_DIR,
    qdrant_client_builder: Callable[[], QdrantClient] = _default_qdrant_client_builder,
    collection_name: str = settings.kb_collection_name,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Chunk, embed, and index every runbook. Returns the total number of
    points written.

    Args:
        qdrant_client_builder: producer of the Qdrant client. Defaults to
            a real server connection via Settings; tests pass a builder
            pointed at a temp local-mode client instead.
            :param batch_size:
            :param collection_name:
            :param qdrant_client_builder:
            :param runbooks_dir:
    """
    chunks = chunk_all_runbooks(runbooks_dir)
    if not chunks:
        raise ValueError(f"No runbook chunks found in {runbooks_dir}")

    client = qdrant_client_builder()
    create_collection(client, collection_name)

    total_indexed = 0
    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start : batch_start + batch_size]
        texts = [chunk.text for chunk in batch]

        logger.info(
            "Embedding batch %d-%d of %d", batch_start, batch_start + len(batch), len(chunks)
        )
        embeddings = embed_documents(texts)

        total_indexed += index_chunks(client, batch, embeddings, collection_name)

    logger.info("Indexed %d total chunks into '%s'", total_indexed, collection_name)
    return total_indexed


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    total = run_indexing()
    print(f"Total chunks indexed: {total}")


if __name__ == "__main__":
    main()
