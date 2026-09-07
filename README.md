# IT Ticket Triage & Remediation Agents

A multi-agent system that triages incoming IT support tickets, investigates
via a knowledge base, and (with human-in-the-loop approval) executes
remediation actions — built with LangGraph, a custom MCP server for tool
integration, and hosted LLM/embedding APIs.

## Tech stack

| Concern | Choice |
|---|---|
| Generation | Anthropic API — Sonnet (reasoning agents), Haiku (routing/classification) |
| Orchestration | LangGraph |
| Tool integration | Custom MCP server |
| Embeddings | Voyage AI |
| Vector store | Qdrant (self-hosted) |
| Tracing | OpenTelemetry |
| LLM observability | Langfuse (self-hosted) |
| Evaluation | Hand-rolled agent-level eval |

## Local setup

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone <your-repo-url>
cd it-ticket-agents
make install
uv run pre-commit install
```

## Common commands

```bash
make check       # everything CI runs
make lint
make format
make typecheck
make test
```