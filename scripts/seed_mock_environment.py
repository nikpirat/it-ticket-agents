"""Seed the mock IT environment with realistic sample data for manual
testing and demos in later phases.

Run once: uv run python scripts/seed_mock_environment.py
"""

from it_ticket_agents.config.settings import settings
from it_ticket_agents.mcp_server.mock_state import MockStateStore, Ticket

TICKETS = [
    Ticket(
        id="T-1001",
        title="Cannot connect to corporate VPN",
        description=(
            "User jsmith reports the VPN client fails to connect since this "
            "morning, error 'gateway unreachable'."
        ),
        status="open",
        priority="high",
        category="network",
        requester="jsmith",
        created_at="2026-01-15T09:12:00+00:00",
    ),
    Ticket(
        id="T-1002",
        title="Locked out of email account",
        description="User mgarcia is locked out after too many failed login attempts.",
        status="open",
        priority="medium",
        category="account",
        requester="mgarcia",
        created_at="2026-01-15T10:03:00+00:00",
    ),
    Ticket(
        id="T-1003",
        title="Internal wiki unreachable",
        description="Multiple users report the internal wiki (confluence-internal) is down.",
        status="open",
        priority="critical",
        category="service",
        requester="rkumar",
        created_at="2026-01-15T11:47:00+00:00",
    ),
    Ticket(
        id="T-1004",
        title="Slow file share access",
        description="File share access has been intermittently slow for the past two days.",
        status="in_progress",
        priority="low",
        category="network",
        requester="tlee",
        created_at="2026-01-14T14:20:00+00:00",
        resolution_notes="Investigating with network team; no root cause yet.",
    ),
]

SERVICES = [
    ("vpn-gateway", "down"),
    ("confluence-internal", "down"),
    ("file-share-01", "degraded"),
    ("email-server", "running"),
]

ACCOUNTS = [
    ("jsmith", False),
    ("mgarcia", True),
    ("rkumar", False),
    ("tlee", False),
]


def main() -> None:
    store = MockStateStore(settings.mock_db_path)

    for ticket in TICKETS:
        store.create_ticket(ticket)

    for name, status in SERVICES:
        store.set_service_status(name, status=status)

    for username, locked in ACCOUNTS:
        store.set_account_locked(username, locked=locked)

    store.close()
    print(
        f"Seeded {len(TICKETS)} tickets, {len(SERVICES)} services, "
        f"{len(ACCOUNTS)} accounts into {settings.mock_db_path}"
    )


if __name__ == "__main__":
    main()
