"""Tests for it_ticket_agents.retrieval.chunk."""

from pathlib import Path

from it_ticket_agents.retrieval.chunk import chunk_all_runbooks, chunk_markdown_file


def _write_markdown(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class TestChunkMarkdownFile:
    def test_splits_at_level_2_headings(self, tmp_path: Path) -> None:
        path = _write_markdown(
            tmp_path / "doc.md",
            "# Title\n\nOverview text here.\n\n## Section One\n\nContent one.\n\n"
            "## Section Two\n\nContent two.\n",
        )

        chunks = chunk_markdown_file(path)

        headings = [c.section_heading for c in chunks]
        assert headings == ["Overview", "Section One", "Section Two"]
        assert chunks[1].text == "Content one."
        assert chunks[2].text == "Content two."

    def test_chunk_index_increments_in_order(self, tmp_path: Path) -> None:
        path = _write_markdown(
            tmp_path / "doc.md",
            "# Title\n\nIntro.\n\n## A\n\nContent A.\n\n## B\n\nContent B.\n",
        )

        chunks = chunk_markdown_file(path)

        assert [c.chunk_index for c in chunks] == [0, 1, 2]

    def test_source_document_is_filename(self, tmp_path: Path) -> None:
        path = _write_markdown(tmp_path / "vpn-troubleshooting.md", "# T\n\n## A\n\nContent.\n")

        chunks = chunk_markdown_file(path)

        assert all(c.source_document == "vpn-troubleshooting.md" for c in chunks)

    def test_title_only_with_no_overview_text_produces_no_overview_chunk(
        self, tmp_path: Path
    ) -> None:
        """A doc with just a title and no overview paragraph before the
        first ## heading shouldn't produce an empty 'Overview' chunk."""
        path = _write_markdown(tmp_path / "doc.md", "# Title\n\n## Section\n\nContent.\n")

        chunks = chunk_markdown_file(path)

        assert [c.section_heading for c in chunks] == ["Section"]

    def test_empty_section_content_is_skipped(self, tmp_path: Path) -> None:
        path = _write_markdown(
            tmp_path / "doc.md",
            "# Title\n\nIntro.\n\n## Empty Section\n\n## Real Section\n\nReal content.\n",
        )

        chunks = chunk_markdown_file(path)

        headings = [c.section_heading for c in chunks]
        assert "Empty Section" not in headings
        assert "Real Section" in headings


class TestChunkAllRunbooks:
    def test_chunks_every_markdown_file_in_directory(self, tmp_path: Path) -> None:
        _write_markdown(tmp_path / "a.md", "# A\n\n## Section\n\nContent A.\n")
        _write_markdown(tmp_path / "b.md", "# B\n\n## Section\n\nContent B.\n")
        _write_markdown(tmp_path / "not-markdown.txt", "should be ignored")

        chunks = chunk_all_runbooks(tmp_path)

        sources = {c.source_document for c in chunks}
        assert sources == {"a.md", "b.md"}

    def test_empty_directory_returns_no_chunks(self, tmp_path: Path) -> None:
        assert chunk_all_runbooks(tmp_path) == []
