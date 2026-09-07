"""Tests for it_ticket_agents.mcp_server.mock_state.

Uses real, temporary SQLite databases - not mocked - since SQLite is
fast and file-based, there's no reason to fake what we can actually run.
"""

from pathlib import Path

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


class TestTickets:
    def test_create_and_get_ticket(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")
        store.create_ticket(_make_ticket())

        ticket = store.get_ticket("T-1")

        assert ticket is not None
        assert ticket.title == "VPN not connecting"
        assert ticket.status == "open"

    def test_get_nonexistent_ticket_returns_none(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")

        assert store.get_ticket("does-not-exist") is None

    def test_list_open_tickets_excludes_resolved(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")
        store.create_ticket(_make_ticket("T-1", status="open"))
        store.create_ticket(_make_ticket("T-2", status="resolved"))
        store.create_ticket(_make_ticket("T-3", status="in_progress"))

        open_tickets = store.list_open_tickets()

        assert {t.id for t in open_tickets} == {"T-1", "T-3"}

    def test_update_ticket_status_returns_true_when_found(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")
        store.create_ticket(_make_ticket())

        updated = store.update_ticket_status("T-1", "resolved", "Restarted VPN service.")

        assert updated is True
        ticket = store.get_ticket("T-1")
        assert ticket is not None
        assert ticket.status == "resolved"
        assert ticket.resolution_notes == "Restarted VPN service."

    def test_update_ticket_status_returns_false_when_not_found(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")

        assert store.update_ticket_status("does-not-exist", "resolved") is False

    def test_update_status_without_notes_preserves_existing_notes(self, tmp_path: Path) -> None:
        """COALESCE behavior: updating status alone shouldn't wipe out
        resolution_notes set by an earlier update."""
        store = MockStateStore(tmp_path / "state.db")
        store.create_ticket(_make_ticket())
        store.update_ticket_status("T-1", "in_progress", "Investigating VPN logs.")

        store.update_ticket_status("T-1", "resolved")

        ticket = store.get_ticket("T-1")
        assert ticket is not None
        assert ticket.resolution_notes == "Investigating VPN logs."

    def test_state_persists_across_store_instances(self, tmp_path: Path) -> None:
        """Real persistence check — a ticket created via one connection
        must be visible via a fresh connection to the same file, proving
        this genuinely persists to disk rather than only living in memory."""
        db_path = tmp_path / "state.db"
        store_1 = MockStateStore(db_path)
        store_1.create_ticket(_make_ticket())
        store_1.close()

        store_2 = MockStateStore(db_path)
        ticket = store_2.get_ticket("T-1")

        assert ticket is not None
        assert ticket.title == "VPN not connecting"


class TestServices:
    def test_unknown_service_returns_none(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")

        assert store.get_service_status("vpn-gateway") is None

    def test_set_and_get_service_status(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")

        store.set_service_status("vpn-gateway", status="down")

        status = store.get_service_status("vpn-gateway")
        assert status is not None
        assert status.status == "down"
        assert status.last_restarted is None

    def test_restart_sets_status_running_and_records_timestamp(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")
        store.set_service_status("vpn-gateway", status="down")

        store.set_service_status("vpn-gateway", status="running", restarted=True)

        status = store.get_service_status("vpn-gateway")
        assert status is not None
        assert status.status == "running"
        assert status.last_restarted is not None


class TestAccounts:
    def test_unknown_account_returns_none(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")

        assert store.get_account_status("jsmith") is None

    def test_lock_and_check_account(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")

        store.set_account_locked("jsmith", locked=True)

        status = store.get_account_status("jsmith")
        assert status is not None
        assert status.locked is True

    def test_reset_password_unlocks_account(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")
        store.set_account_locked("jsmith", locked=True)

        reset = store.reset_account_password("jsmith")

        assert reset is True
        status = store.get_account_status("jsmith")
        assert status is not None
        assert status.locked is False
        assert status.last_password_reset is not None

    def test_reset_password_for_unknown_account_returns_false(self, tmp_path: Path) -> None:
        store = MockStateStore(tmp_path / "state.db")

        assert store.reset_account_password("does-not-exist") is False
