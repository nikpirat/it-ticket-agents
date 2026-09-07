"""MCP server exposing IT-ops tools to agents.

Wraps the plain, testable functions in tools.py as MCP tools — protocol
wiring is kept separate from business logic (tools.py is fully testable
without any MCP machinery at all).
"""

from mcp.server.mcpserver import MCPServer

from it_ticket_agents.mcp_server import tools
from it_ticket_agents.mcp_server.mock_state import MockStateStore

DEFAULT_DB_PATH = "mock_it_state.db"


def build_server(db_path: str = DEFAULT_DB_PATH) -> MCPServer:
    """Build the MCP server with all IT-ops tools registered against a
    MockStateStore backed by db_path.
    """
    store = MockStateStore(db_path)
    app: MCPServer = MCPServer(name="it-ops-tools")

    @app.tool()
    def get_ticket(ticket_id: str) -> dict[str, object]:
        """Fetch a ticket's full details by its id."""
        return tools.get_ticket(store, ticket_id)

    @app.tool()
    def list_open_tickets() -> list[dict[str, object]]:
        """List all open or in-progress tickets."""
        return tools.list_open_tickets(store)

    @app.tool()
    def check_service_status(service_name: str) -> dict[str, object]:
        """Check whether a service is running, degraded, or down."""
        return tools.check_service_status(store, service_name)

    @app.tool()
    def restart_service(service_name: str) -> dict[str, object]:
        """Restart a service, bringing it back to a running state."""
        return tools.restart_service(store, service_name)

    @app.tool()
    def check_account_status(username: str) -> dict[str, object]:
        """Check whether a user account is locked."""
        return tools.check_account_status(store, username)

    @app.tool()
    def reset_password(username: str) -> dict[str, object]:
        """Reset a user's password and unlock their account."""
        return tools.reset_password(store, username)

    @app.tool()
    def update_ticket_status(
        ticket_id: str, status: str, resolution_notes: str | None = None
    ) -> dict[str, object]:
        """Update a ticket's status (open/in_progress/resolved/escalated)."""
        return tools.update_ticket_status(store, ticket_id, status, resolution_notes)

    return app


def main() -> None:
    server = build_server()
    server.run()


if __name__ == "__main__":
    main()