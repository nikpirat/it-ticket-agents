"""Tests for it_ticket_agents.mcp_server.tools.

Uses a real temp-file MockStateStore, same rationale as test_mock_state.py.
"""

from pathlib import Path

from it_ticket_agents.mcp_server import tools
from it_ticket_agents.mcp_server.mock_state import MockStateStore, Ticket


def _make_ticket(ticket_id: str = "T-1", status: str = "open") -> Ticket:
    return Ticket(
        id=ticket_id,
        title="VPN not connecting",
        description="User cannot connect to the corporate VPN.",
        status=status,
        priority="high",
        category="network",
        requester="jsmith",
        created_at="2026-01-01T00:00:00+00:00",
    )


class TestGetTicket:
    def test_returns_ticket_details(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")
        store.create_ticket(_make_ticket())

        result = tools.get_ticket(store, "T-1")

        assert result["id"] == "T-1"
        assert result["title"] == "VPN not connecting"
        assert "error" not in result

    def test_returns_error_for_unknown_ticket(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")

        result = tools.get_ticket(store, "does-not-exist")

        assert "error" in result


class TestListOpenTickets:
    def test_lists_only_open_and_in_progress(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")
        store.create_ticket(_make_ticket("T-1", status="open"))
        store.create_ticket(_make_ticket("T-2", status="resolved"))

        results = tools.list_open_tickets(store)

        assert len(results) == 1
        assert results[0]["id"] == "T-1"


class TestServiceTools:
    def test_check_status_of_unknown_service_returns_error(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")

        result = tools.check_service_status(store, "unknown-service")

        assert "error" in result

    def test_restart_service_brings_it_to_running(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")
        store.set_service_status("vpn-gateway", status="down")

        result = tools.restart_service(store, "vpn-gateway")

        assert result["status"] == "running"
        assert result["action"] == "restarted"
        status = store.get_service_status("vpn-gateway")
        assert status is not None
        assert status.status == "running"

    def test_restart_unknown_service_returns_error_without_creating_it(
        self, tmp_path: Path
    ) -> None:
        store = MockStateStore(tmp_path / "state.db")

        result = tools.restart_service(store, "phantom-service")

        assert "error" in result
        assert store.get_service_status("phantom-service") is None


class TestAccountTools:
    def test_reset_password_for_unknown_account_returns_error(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")

        result = tools.reset_password(store, "does-not-exist")

        assert "error" in result

    def test_reset_password_unlocks_known_account(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")
        store.set_account_locked("jsmith", locked=True)

        result = tools.reset_password(store, "jsmith")

        assert result["locked"] is False
        assert result["action"] == "password_reset"


class TestUpdateTicketStatus:
    def test_rejects_invalid_status(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")
        store.create_ticket(_make_ticket())

        result = tools.update_ticket_status(store, "T-1", "not_a_real_status")

        assert "error" in result
        ticket = store.get_ticket("T-1")
        assert ticket is not None
        assert ticket.status == "open"

    def test_accepts_valid_status_with_notes(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")
        store.create_ticket(_make_ticket())

        result = tools.update_ticket_status(store, "T-1", "resolved", "Fixed via restart.")

        assert result["status"] == "resolved"
        ticket = store.get_ticket("T-1")
        assert ticket is not None
        assert ticket.resolution_notes == "Fixed via restart."

    def test_unknown_ticket_returns_error(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")

        result = tools.update_ticket_status(store, "does-not-exist", "resolved")

        assert "error" in result