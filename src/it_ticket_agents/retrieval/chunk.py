"""Markdown-based chunking for runbook documents.

Simpler than PDF chunking (a prior project's font-size heuristic) since
markdown headers are explicit structural markup - no need to infer
section boundaries from visual formatting.
"""

import re
from pathlib import Path

from it_ticket_agents.retrieval.store import RunbookChunk


def chunk_markdown_file(path: Path) -> list[RunbookChunk]:
    """Split a markdown file into chunks at ## (level-2) headings.

    The level-1 (#) heading is the document title, not a chunk boundary
    on its own — chunks are built from level-2 sections, which is where
    this project's runbooks organize distinct, individually-relevant
    topics (e.g. "## Standard resolution", "## When to escalate").
    """
    text = path.read_text(encoding="utf-8")
    source_document = path.name

    sections = re.split(r"^## (.+)$", text, flags=re.MULTILINE)

    chunks = []
    chunk_index = 0

    pre_content = sections[0].strip()
    if pre_content:
        lines = pre_content.split("\n", 1)
        overview_text = lines[1].strip() if len(lines) > 1 else ""
        if overview_text:
            chunks.append(
                RunbookChunk(
                    text=overview_text,
                    section_heading="Overview",
                    source_document=source_document,
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

    for i in range(1, len(sections), 2):
        heading = sections[i].strip()
        content = sections[i + 1].strip() if i + 1 < len(sections) else ""
        if not content:
            continue
        chunks.append(
            RunbookChunk(
                text=content,
                section_heading=heading,
                source_document=source_document,
                chunk_index=chunk_index,
            )
        )
        chunk_index += 1

    return chunks


def chunk_all_runbooks(directory: Path) -> list[RunbookChunk]:
    """Chunk every markdown file in a directory, in sorted filename order
    for deterministic, reproducible output."""
    all_chunks = []
    for path in sorted(directory.glob("*.md")):
        all_chunks.extend(chunk_markdown_file(path))
    return all_chunks