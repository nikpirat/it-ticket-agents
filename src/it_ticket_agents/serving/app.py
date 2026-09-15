"""FastAPI serving application for the IT ticket triage/remediation agents.

Wires together the MCP server, LangChain tool bridge, SQLite-backed
checkpointer (durable human-in-the-loop pauses across requests/
restarts), and the compiled agent graph.

Uses the same dependency-injection pattern as this roadmap's prior RAG
project's serving layer: a `graph_builder` callable (defaulting to the
real MCP+checkpointer-backed construction) so tests can inject a fully
fake graph and skip real API keys, a live checkpointer, and MCP server
startup entirely.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel

from it_ticket_agents.agents.graph import build_graph
from it_ticket_agents.agents.mcp_bridge import load_mcp_tools_as_langchain_tools
from it_ticket_agents.agents.state import TicketState
from it_ticket_agents.config.settings import settings
from it_ticket_agents.mcp_server.mock_state import MockStateStore
from it_ticket_agents.mcp_server.server import build_server

logger = logging.getLogger(__name__)

CHECKPOINT_DB_PATH = "checkpoints.db"


class ProposedActionResponse(BaseModel):
    action_type: str
    target: str
    reasoning: str


class ProcessTicketResponse(BaseModel):
    ticket_id: str
    status: str
    resolution_notes: str
    pending_approval: bool
    proposed_action: ProposedActionResponse | None = None


class ApprovalRequest(BaseModel):
    approved: bool


def _config_for(ticket_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": ticket_id}}


def _response_from_result(ticket_id: str, result: dict[str, Any]) -> ProcessTicketResponse:
    if "__interrupt__" in result:
        interrupt_payload = result["__interrupt__"][0].value
        return ProcessTicketResponse(
            ticket_id=ticket_id,
            status="pending_approval",
            resolution_notes="Awaiting human approval.",
            pending_approval=True,
            proposed_action=ProposedActionResponse(**interrupt_payload["proposed_action"]),
        )
    return ProcessTicketResponse(
        ticket_id=ticket_id,
        status=result["status"],
        resolution_notes=result["resolution_notes"],
        pending_approval=False,
    )


def create_app(
    graph_builder: Callable[[], Awaitable[CompiledStateGraph[TicketState]]] | None = None,
    ticket_store_builder: Callable[[], MockStateStore] = (
        lambda: MockStateStore(settings.mock_db_path)
    ),
) -> FastAPI:
    """Build the FastAPI app.

    Args:
        graph_builder: async producer of the compiled graph, built once
            at startup. None (the default) uses the real MCP +
            checkpointer-backed construction, correctly scoped via a
            real `async with` block for the app's full lifetime.

            Real bug found via live testing (not a preemptive guess): an
            earlier version called
            `AsyncSqliteSaver.from_conn_string(...).__aenter__()`
            manually instead of using `async with`. That looked like
            only a resource-cleanup nicety ("__aexit__ never runs on
            shutdown") but was load-bearing — langgraph-checkpoint-
            sqlite's connection-started check uses `thread.is_alive()`,
            which is also False once aiosqlite's background thread
            finishes its work and exits, not just before it starts.
            With the manual __aenter__, a later request could see
            `is_alive() == False` and try to `.start()` the same
            already-used thread object again, which Python explicitly
            forbids: "threads can only be started once". Holding a real
            `async with` open around `yield` keeps this thread's
            lifecycle correctly scoped to the app's actual runtime.

            Tests pass a plain async callable returning a fake graph (or
            a real one with fake node functions, as in test_graph.py)
            instead — no context-manager scoping needed there, since
            fake graphs don't hold a real aiosqlite connection.
        ticket_store_builder: producer of the MockStateStore used to
            fetch ticket details. Defaults to Settings; tests pass a
            builder pointed at a temp database.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("Building agent graph...")
        app.state.ticket_store = ticket_store_builder()

        if graph_builder is not None:
            app.state.graph = await graph_builder()
            yield
        else:
            mcp_server = build_server()
            tools = await load_mcp_tools_as_langchain_tools(mcp_server)
            async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as checkpointer:
                app.state.graph = build_graph(tools=tools, checkpointer=checkpointer)
                yield

    app = FastAPI(title="IT Ticket Triage Agents", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/tickets/{ticket_id}/process", response_model=ProcessTicketResponse)
    async def process_ticket(ticket_id: str) -> ProcessTicketResponse:
        ticket = app.state.ticket_store.get_ticket(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found")

        initial_state = TicketState(
            ticket_id=ticket_id,
            ticket={
                "title": ticket.title,
                "description": ticket.description,
                "priority": ticket.priority,
            },
            category="",
            escalate_immediately=False,
            supervisor_reasoning="",
            diagnosis="",
            kb_context=[],
            proposed_action=None,
            requires_human_approval=False,
            status="",
            resolution_notes="",
        )

        result = await app.state.graph.ainvoke(initial_state, config=_config_for(ticket_id))
        return _response_from_result(ticket_id, result)

    @app.post("/tickets/{ticket_id}/approval", response_model=ProcessTicketResponse)
    async def approve_or_reject(ticket_id: str, request: ApprovalRequest) -> ProcessTicketResponse:
        result = await app.state.graph.ainvoke(
            Command(resume=request.approved), config=_config_for(ticket_id)
        )
        return _response_from_result(ticket_id, result)

    return app


app = create_app()
