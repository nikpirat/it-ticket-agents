"""Tests for it_ticket_agents.retrieval.index_kb.

Fakes embed_documents (the one piece requiring a real Voyage API key) -
everything else (chunking real files, real local-mode Qdrant indexing)
runs for real.
"""

from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from it_ticket_agents.retrieval import index_kb


def _write_runbook(path: Path, sections: int) -> None:
    content = "# Test Runbook\n\nIntro text.\n\n"
    for i in range(sections):
        content += f"## Section {i}\n\nContent for section {i}.\n\n"
    path.write_text(content, encoding="utf-8")


class TestRunIndexing:
    def test_chunks_embeds_and_indexes_real_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runbooks_dir = tmp_path / "runbooks"
        runbooks_dir.mkdir()
        _write_runbook(runbooks_dir / "a.md", sections=3)
        _write_runbook(runbooks_dir / "b.md", sections=2)
        # Total chunks: (1 overview + 3 sections) + (1 overview + 2 sections) = 7

        call_count = 0

        def fake_embed_documents(texts: list[str]) -> list[list[float]]:
            nonlocal call_count
            call_count += 1
            return [[float(i)] + [0.0] * 1023 for i in range(len(texts))]

        monkeypatch.setattr(index_kb, "embed_documents", fake_embed_documents)

        total = index_kb.run_indexing(
            runbooks_dir=runbooks_dir,
            qdrant_client_builder=lambda: QdrantClient(path=str(tmp_path / "qdrant")),
            collection_name="test_collection",
            batch_size=4,
        )

        assert total == 7
        # 7 chunks at batch_size=4 -> batches of 4, 3 -> 2 calls
        assert call_count == 2

    def test_raises_when_no_runbooks_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with pytest.raises(ValueError, match="No runbook chunks found"):
            index_kb.run_indexing(
                runbooks_dir=empty_dir,
                qdrant_client_builder=lambda: QdrantClient(path=str(tmp_path / "qdrant")),
            )