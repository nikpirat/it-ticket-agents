"""Centralized, type-validated application settings.

Every model name, version, and configuration constant lives here — not
scattered as hardcoded values across individual modules. A single source
of truth means changing a model or a path is a one-line edit here, not a
grep-and-replace across the codebase, and avoids the exact class of bug
where two places disagree about the same value (e.g. a hardcoded
embedding dimension drifting out of sync with the model actually
producing it).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ITA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Embeddings (Voyage AI)
    voyage_model: str = "voyage-4-lite"
    voyage_embedding_dim: int = 1024

    # Mock IT environment / MCP server
    mock_db_path: str = "mock_it_state.db"

    # Vector store (Qdrant)
    qdrant_url: str = "http://localhost:6333"
    kb_collection_name: str = "it_runbooks"
    retrieval_top_k: int = 5


settings = Settings()
