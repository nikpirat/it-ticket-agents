"""Mock IT environment: SQLite-backed state for tickets, services, and
accounts, giving the agent tools something real (if simulated) to read
and mutate - not just hardcoded fixtures that never change.

SQLite (not pure in-memory dicts) so the environment's state persists
across process restarts during development/demos - a ticket you
"resolved" in one run should stay resolved when you run the agents again.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Ticket:
    id: str
    title: str
    description: str
    status: str  # "open", "in_progress", "resolved", "escalated"
    priority: str  # "low", "medium", "high", "critical"
    category: str  # e.g. "account", "service", "network"
    requester: str
    created_at: str
    resolution_notes: str | None = None


@dataclass(frozen=True)
class ServiceStatus:
    name: str
    status: str  # "running", "degraded", "down"
    last_restarted: str | None


@dataclass(frozen=True)
class AccountStatus:
    username: str
    locked: bool
    last_password_reset: str | None


SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    priority TEXT NOT NULL,
    category TEXT NOT NULL,
    requester TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolution_notes TEXT
);

CREATE TABLE IF NOT EXISTS services (
    name TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_restarted TEXT
);

CREATE TABLE IF NOT EXISTS accounts (
    username TEXT PRIMARY KEY,
    locked INTEGER NOT NULL,
    last_password_reset TEXT
);
"""


class MockStateStore:
    """Wraps a SQLite connection representing the mock IT environment's
    current state."""

    def __init__(self, db_path: str | Path) -> None:
        # check_same_thread=False: real bug found via testing against the
        # actual MCP SDK, not a preemptive guess — MCP dispatches
        # synchronous tool functions (like ours) to a worker thread pool,
        # the same pattern FastAPI uses for sync route handlers. Without
        # this, the connection (created in the main thread when
        # build_server() runs) can't be touched from the thread pool
        # worker that actually executes the tool call. Safe for this
        # store's needs — SQLite has its own internal write-serialization
        # locking — but worth knowing this is a simplification appropriate
        # for a mock/demo store's modest concurrency, not a
        # high-concurrency production pattern.
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- Tickets ---

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        row = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return _row_to_ticket(row) if row else None

    def list_open_tickets(self) -> list[Ticket]:
        rows = self._conn.execute(
            "SELECT * FROM tickets WHERE status IN ('open', 'in_progress') ORDER BY created_at"
        ).fetchall()
        return [_row_to_ticket(row) for row in rows]

    def create_ticket(self, ticket: Ticket) -> None:
        self._conn.execute(
            "INSERT INTO tickets (id, title, description, status, priority, category, "
            "requester, created_at, resolution_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ticket.id,
                ticket.title,
                ticket.description,
                ticket.status,
                ticket.priority,
                ticket.category,
                ticket.requester,
                ticket.created_at,
                ticket.resolution_notes,
            ),
        )
        self._conn.commit()

    def update_ticket_status(
        self, ticket_id: str, status: str, resolution_notes: str | None = None
    ) -> bool:
        """Returns True if a ticket was actually updated, False if no
        ticket with that id exists — callers need to distinguish
        "updated" from "silently did nothing"."""
        cursor = self._conn.execute(
            "UPDATE tickets SET status = ?, resolution_notes = COALESCE(?, resolution_notes) "
            "WHERE id = ?",
            (status, resolution_notes, ticket_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # --- Services ---

    def get_service_status(self, name: str) -> ServiceStatus | None:
        row = self._conn.execute("SELECT * FROM services WHERE name = ?", (name,)).fetchone()
        return _row_to_service(row) if row else None

    def set_service_status(self, name: str, status: str, restarted: bool = False) -> None:
        last_restarted = _now_iso() if restarted else None
        existing = self.get_service_status(name)
        if existing is None:
            self._conn.execute(
                "INSERT INTO services (name, status, last_restarted) VALUES (?, ?, ?)",
                (name, status, last_restarted),
            )
        else:
            self._conn.execute(
                "UPDATE services SET status = ?, last_restarted = COALESCE(?, last_restarted) "
                "WHERE name = ?",
                (status, last_restarted, name),
            )
        self._conn.commit()

    # --- Accounts ---

    def get_account_status(self, username: str) -> AccountStatus | None:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE username = ?", (username,)
        ).fetchone()
        return _row_to_account(row) if row else None

    def set_account_locked(self, username: str, locked: bool) -> None:
        existing = self.get_account_status(username)
        if existing is None:
            self._conn.execute(
                "INSERT INTO accounts (username, locked, last_password_reset) VALUES (?, ?, ?)",
                (username, int(locked), None),
            )
        else:
            self._conn.execute(
                "UPDATE accounts SET locked = ? WHERE username = ?", (int(locked), username)
            )
        self._conn.commit()

    def reset_account_password(self, username: str) -> bool:
        """Returns True if an account was found and reset, False otherwise."""
        existing = self.get_account_status(username)
        if existing is None:
            return False
        self._conn.execute(
            "UPDATE accounts SET locked = 0, last_password_reset = ? WHERE username = ?",
            (_now_iso(), username),
        )
        self._conn.commit()
        return True


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_ticket(row: sqlite3.Row) -> Ticket:
    return Ticket(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
        category=row["category"],
        requester=row["requester"],
        created_at=row["created_at"],
        resolution_notes=row["resolution_notes"],
    )


def _row_to_service(row: sqlite3.Row) -> ServiceStatus:
    return ServiceStatus(
        name=row["name"], status=row["status"], last_restarted=row["last_restarted"]
    )


def _row_to_account(row: sqlite3.Row) -> AccountStatus:
    return AccountStatus(
        username=row["username"],
        locked=bool(row["locked"]),
        last_password_reset=row["last_password_reset"],
    )