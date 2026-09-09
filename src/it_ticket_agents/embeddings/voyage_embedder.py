"""Embedding generation via the Voyage AI API.

Voyage uses asymmetric embedding via the `input_type` parameter: queries
are embedded with input_type="query", documents/passages with
input_type="document" - confirmed against Voyage's own current API
reference, not assumed. Asymmetric-embedding pattern (via Voyage's first-class API parameter).
Getting this backwards doesn't error, it silently produces measurably worse retrieval
- same lesson, different mechanism.

Requires the VOYAGE_API_KEY environment variable (picked up automatically
by voyageai.Client() - confirmed directly against the installed SDK's
source, not assumed).
"""

import logging
from typing import cast

from voyageai.client import Client

from it_ticket_agents.config.settings import settings

logger = logging.getLogger(__name__)


def embed_documents(texts: list[str], model: str = settings.voyage_model) -> list[list[float]]:
    """Embed document/passage text with input_type='document'. No
    instruction/role framing needed on the document side - Voyage's
    asymmetric design only requires the distinction on the query side.
    """
    if not texts:
        return []
    client = Client()
    result = client.embed(texts, model=model, input_type="document")
    return cast(list[list[float]], result.embeddings)


def embed_query(text: str, model: str = settings.voyage_model) -> list[float]:
    """Embed a single search query with input_type='query'."""
    client = Client()
    result = client.embed([text], model=model, input_type="query")
    return cast(list[float], result.embeddings[0])
