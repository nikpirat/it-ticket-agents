"""Smoke tests for it_ticket_agents.mcp_server.server.

These go through the real MCPServer.call_tool/list_tools machinery (not
mocked) - the goal is confirming our tool registration actually works
against the real SDK, since that's exactly the kind of wiring mistake
that's easy to get subtly wrong (wrong decorator usage, wrong return
type) and that unit tests of tools.py alone wouldn't catch.
"""

from pathlib import Path

from it_ticket_agents.mcp_server.mock_state import MockStateStore, Ticket
from it_ticket_agents.mcp_server.server import build_server


async def test_all_expected_tools_are_registered(tmp_path: Path) -> None:
    server = build_server(str(tmp_path / "state.db"))

    registered = {tool.name for tool in await server.list_tools()}

    assert registered == {
        "get_ticket",
        "list_open_tickets",
        "check_service_status",
        "restart_service",
        "check_account_status",
        "reset_password",
        "update_ticket_status",
    }


async def test_call_tool_get_ticket_end_to_end(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    seed_store = MockStateStore(db_path)
    seed_store.create_ticket(
        Ticket(
            id="T-1",
            title="VPN not connecting",
            description="User cannot connect to the corporate VPN.",
            status="open",
            priority="high",
            category="network",
            requester="jsmith",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    seed_store.close()

    server = build_server(str(db_path))
    result = await server.call_tool("get_ticket", {"ticket_id": "T-1"})

    assert result.is_error is not True


async def test_call_tool_restart_service_end_to_end(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    seed_store = MockStateStore(db_path)
    seed_store.set_service_status("vpn-gateway", status="down")
    seed_store.close()

    server = build_server(str(db_path))
    await server.call_tool("restart_service", {"service_name": "vpn-gateway"})

    verify_store = MockStateStore(db_path)
    status = verify_store.get_service_status("vpn-gateway")
    assert status is not None
    assert status.status == "running"