"""Persist-status node: writes the graph's final status/resolution_notes
back to the ticket's persisted record via the update_ticket_status MCP
tool.

Without this, a resolved or escalated outcome only exists in LangGraph's
own in-memory/checkpointed state and the API response — it never reaches
the actual ticket record in mock_it_state.db, even when a remediation
action genuinely executed. Real gap found via live end-to-end testing:
querying the tickets table directly after a successful "resolved"
response showed the ticket's own status column unchanged.
"""

from langchain_core.tools import StructuredTool

from it_ticket_agents.agents.state import TicketState


async def persist_status_node(state: TicketState, tools: list[StructuredTool]) -> dict[str, object]:
    """Write state['status']/state['resolution_notes'] back to the
    ticket's persisted record. A shared convergence point all three
    terminal paths (escalate, finalize, execute_action) route through
    before END, rather than duplicating this call in each of them.
    """
    tool = next((t for t in tools if t.name == "update_ticket_status"), None)
    if tool is None:
        # Shouldn't happen given our own MCP server always registers
        # this tool, but fail gracefully rather than crash an otherwise-
        # successful ticket resolution over a missing tool reference.
        return {}

    await tool.ainvoke(
        {
            "ticket_id": state["ticket_id"],
            "status": state["status"],
            "resolution_notes": state["resolution_notes"],
        }
    )
    return {}
