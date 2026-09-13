"""Tests for it_ticket_agents.agents.mcp_bridge.

Uses a real MCP server (built in Phase 1), not mocked - the whole point
of this module is bridging our real server's tools, so faking the server
would test nothing meaningful. Real proof this works: the closure-bug
test specifically, which would silently pass with wrong data if the
tool-name binding in _make_tool_coroutine were broken.
"""

from pathlib import Path

from it_ticket_agents.agents.mcp_bridge import load_mcp_tools_as_langchain_tools
from it_ticket_agents.mcp_server.mock_state import MockStateStore, Ticket
from it_ticket_agents.mcp_server.server import build_server


def _seed_state(db_path: Path) -> None:
    store = MockStateStore(db_path)
    store.create_ticket(
        Ticket(
            id="T-1",
            title="VPN down",
            description="desc",
            status="open",
            priority="high",
            category="network",
            requester="jsmith",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    store.set_service_status("vpn-gateway", status="down")
    store.close()


async def test_loads_all_registered_tools(tmp_path: Path) -> None:
    _seed_state(tmp_path / "state.db")
    server = build_server(str(tmp_path / "state.db"))

    tools = await load_mcp_tools_as_langchain_tools(server)

    names = {t.name for t in tools}
    assert names == {
        "get_ticket",
        "list_open_tickets",
        "check_service_status",
        "restart_service",
        "check_account_status",
        "reset_password",
        "update_ticket_status",
    }


async def test_tool_descriptions_are_preserved(tmp_path: Path) -> None:
    _seed_state(tmp_path / "state.db")
    server = build_server(str(tmp_path / "state.db"))

    tools = await load_mcp_tools_as_langchain_tools(server)

    get_ticket_tool = next(t for t in tools if t.name == "get_ticket")
    assert "ticket" in get_ticket_tool.description.lower()


async def test_each_tool_calls_its_own_name_not_the_last_registered(tmp_path: Path) -> None:
    """The specific closure bug this module's factory function guards
    against: without correctly binding tool_name per tool, every
    generated LangChain tool would silently call whichever MCP tool was
    LAST in the registration loop, regardless of which one was actually
    invoked. This test calls two DIFFERENT tools and confirms each
    returns data belonging to its own tool, not the other's."""
    _seed_state(tmp_path / "state.db")
    server = build_server(str(tmp_path / "state.db"))
    tools = await load_mcp_tools_as_langchain_tools(server)

    get_ticket_tool = next(t for t in tools if t.name == "get_ticket")
    check_service_tool = next(t for t in tools if t.name == "check_service_status")

    ticket_result = await get_ticket_tool.ainvoke({"ticket_id": "T-1"})
    service_result = await check_service_tool.ainvoke({"service_name": "vpn-gateway"})

    assert "VPN down" in ticket_result  # ticket data, from get_ticket
    assert "vpn-gateway" in service_result  # service data, from check_service_status
    assert "vpn-gateway" not in ticket_result or "down" not in ticket_result.split("vpn-gateway")[0]


async def test_tool_call_actually_mutates_persisted_state(tmp_path: Path) -> None:
    """Confirms the bridge reaches real, persisted state - not just
    returning a canned response - by checking a mutation through a fresh
    store connection after the tool call."""
    db_path = tmp_path / "state.db"
    _seed_state(db_path)
    server = build_server(str(db_path))
    tools = await load_mcp_tools_as_langchain_tools(server)

    restart_tool = next(t for t in tools if t.name == "restart_service")
    await restart_tool.ainvoke({"service_name": "vpn-gateway"})

    verify_store = MockStateStore(db_path)
    status = verify_store.get_service_status("vpn-gateway")
    assert status is not None
    assert status.status == "running"


async def test_optional_argument_can_be_omitted(tmp_path: Path) -> None:
    """update_ticket_status has an optional resolution_notes parameter -
    confirms the dynamically-built args schema correctly marks it
    optional rather than requiring every field."""
    _seed_state(tmp_path / "state.db")
    server = build_server(str(tmp_path / "state.db"))
    tools = await load_mcp_tools_as_langchain_tools(server)

    update_tool = next(t for t in tools if t.name == "update_ticket_status")
    result = await update_tool.ainvoke({"ticket_id": "T-1", "status": "resolved"})

    assert "resolved" in result
