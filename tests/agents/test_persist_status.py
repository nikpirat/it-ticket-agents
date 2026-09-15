"""Tests for it_ticket_agents.agents.persist_status.

Uses a real MCP server and MockStateStore (not mocked) — the whole point
of this node is writing to real persisted state, so faking the tool
would test nothing meaningful. This is the fix for a real gap found via
live end-to-end testing: a "resolved" API response never actually
updated the ticket's own status column in the database.
"""

from pathlib import Path

from it_ticket_agents.agents.mcp_bridge import load_mcp_tools_as_langchain_tools
from it_ticket_agents.agents.persist_status import persist_status_node
from it_ticket_agents.agents.state import TicketState
from it_ticket_agents.mcp_server.mock_state import MockStateStore, Ticket
from it_ticket_agents.mcp_server.server import build_server


def _seed_ticket(db_path: Path) -> None:
    store = MockStateStore(db_path)
    store.create_ticket(
        Ticket(
            id="T-1",
            title="VPN down",
            description="Cannot connect",
            status="open",
            priority="high",
            category="network",
            requester="jsmith",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    store.close()


def _make_state(status: str, resolution_notes: str) -> TicketState:
    return TicketState(
        ticket_id="T-1",
        ticket={"title": "VPN down", "description": "Cannot connect"},
        category="network",
        escalate_immediately=False,
        supervisor_reasoning="",
        diagnosis="vpn-gateway is down.",
        kb_context=[],
        proposed_action=None,
        requires_human_approval=False,
        status=status,
        resolution_notes=resolution_notes,
    )


async def test_writes_resolved_status_back_to_the_ticket_record(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    _seed_ticket(db_path)
    server = build_server(str(db_path))
    tools = await load_mcp_tools_as_langchain_tools(server)

    await persist_status_node(
        _make_state("resolved", "Executed restart_service on vpn-gateway."), tools=tools
    )

    verify_store = MockStateStore(db_path)
    ticket = verify_store.get_ticket("T-1")
    assert ticket is not None
    assert ticket.status == "resolved"
    assert ticket.resolution_notes == "Executed restart_service on vpn-gateway."


async def test_writes_escalated_status_back_to_the_ticket_record(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    _seed_ticket(db_path)
    server = build_server(str(db_path))
    tools = await load_mcp_tools_as_langchain_tools(server)

    await persist_status_node(
        _make_state("escalated", "Escalated: no safe automated action identified."),
        tools=tools,
    )

    verify_store = MockStateStore(db_path)
    ticket = verify_store.get_ticket("T-1")
    assert ticket is not None
    assert ticket.status == "escalated"


async def test_missing_tool_fails_gracefully_without_raising() -> None:
    """Shouldn't happen given our own MCP server always registers this
    tool, but confirms a missing tool doesn't crash an otherwise-
    successful ticket resolution."""
    result = await persist_status_node(_make_state("resolved", "notes"), tools=[])

    assert result == {}
