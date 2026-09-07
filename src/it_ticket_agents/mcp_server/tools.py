"""Agent-facing tool functions, operating on the mock IT environment.

Kept as plain, directly-testable Python functions separate from MCP
protocol wiring (server.py) - business logic is fully testable without
any MCP/async machinery, the same "logic separable from serving layer"
pattern used throughout this project's earlier phases (e.g. Project 2's
retrieval/store.py vs. serving/app.py split).
"""

from it_ticket_agents.mcp_server.mock_state import MockStateStore

VALID_TICKET_STATUSES = {"open", "in_progress", "resolved", "escalated"}


def get_ticket(store: MockStateStore, ticket_id: str) -> dict[str, object]:
    """Fetch a ticket's full details."""
    ticket = store.get_ticket(ticket_id)
    if ticket is None:
        return {"error": f"No ticket found with id '{ticket_id}'"}
    return {
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "category": ticket.category,
        "requester": ticket.requester,
        "created_at": ticket.created_at,
        "resolution_notes": ticket.resolution_notes,
    }


def list_open_tickets(store: MockStateStore) -> list[dict[str, object]]:
    """List all open or in-progress tickets."""
    return [
        {
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "category": t.category,
            "status": t.status,
        }
        for t in store.list_open_tickets()
    ]


def check_service_status(store: MockStateStore, service_name: str) -> dict[str, object]:
    """Check whether a service is running, degraded, or down."""
    status = store.get_service_status(service_name)
    if status is None:
        return {"error": f"Unknown service '{service_name}'"}
    return {"name": status.name, "status": status.status, "last_restarted": status.last_restarted}


def restart_service(store: MockStateStore, service_name: str) -> dict[str, object]:
    """Restart a service, bringing it back to a running state.

    A real remediation action — this is the kind of tool call that
    should go through human-in-the-loop approval before an agent invokes
    it in the full graph (Phase 4), not something to call automatically.
    """
    existing = store.get_service_status(service_name)
    if existing is None:
        return {"error": f"Unknown service '{service_name}'"}
    store.set_service_status(service_name, status="running", restarted=True)
    return {"name": service_name, "status": "running", "action": "restarted"}


def check_account_status(store: MockStateStore, username: str) -> dict[str, object]:
    """Check whether a user account is locked."""
    status = store.get_account_status(username)
    if status is None:
        return {"error": f"Unknown account '{username}'"}
    return {
        "username": status.username,
        "locked": status.locked,
        "last_password_reset": status.last_password_reset,
    }


def reset_password(store: MockStateStore, username: str) -> dict[str, object]:
    """Reset a user's password and unlock their account.

    Also a real remediation action requiring human-in-the-loop approval
    in the full agent graph (Phase 4).
    """
    reset = store.reset_account_password(username)
    if not reset:
        return {"error": f"Unknown account '{username}'"}
    return {"username": username, "locked": False, "action": "password_reset"}


def update_ticket_status(
    store: MockStateStore,
    ticket_id: str,
    status: str,
    resolution_notes: str | None = None,
) -> dict[str, object]:
    """Update a ticket's status (e.g. mark resolved) with optional notes."""
    if status not in VALID_TICKET_STATUSES:
        return {
            "error": f"Invalid status '{status}'. Must be one of: {sorted(VALID_TICKET_STATUSES)}"
        }
    updated = store.update_ticket_status(ticket_id, status, resolution_notes)
    if not updated:
        return {"error": f"No ticket found with id '{ticket_id}'"}
    return {"id": ticket_id, "status": status}
