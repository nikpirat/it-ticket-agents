"""Execute-action node: pauses for human approval, then executes the
approved remediation action via its MCP tool, or escalates if rejected.

Uses LangGraph's interrupt() (confirmed against a real minimal test
before building this): calling interrupt(payload) inside a node pauses
graph execution there and surfaces payload to whoever is running the
graph; resuming with Command(resume=value) causes interrupt() to return
value at that exact point, letting this node continue with the human's
decision. Requires a checkpointer (see graph.py) - without one, a paused
graph has nowhere to persist its state between the pause and the resume.
"""

from langchain_core.tools import StructuredTool
from langgraph.types import interrupt

from it_ticket_agents.agents.state import TicketState

_ACTION_ARG_NAMES = {
    "restart_service": "service_name",
    "reset_password": "username",
}


async def execute_action_node(state: TicketState, tools: list[StructuredTool]) -> dict[str, object]:
    """Pause for human approval of the proposed action, then execute it
    (via the matching MCP-bridged tool) if approved, or escalate if not.

    Only reachable when requires_human_approval is True (see graph.py's
    routing) - proposed_action is never None on this path.
    """
    proposed = state["proposed_action"]
    if proposed is None:
        raise ValueError("execute_action_node reached with no proposed_action")

    approved = interrupt(
        {
            "type": "approval_required",
            "ticket_id": state["ticket_id"],
            "proposed_action": proposed,
        }
    )

    if not approved:
        return {
            "status": "escalated",
            "resolution_notes": f"Action rejected by human reviewer: {proposed}",
        }

    action_type = str(proposed["action_type"])
    arg_name = _ACTION_ARG_NAMES.get(action_type)
    if arg_name is None:
        return {
            "status": "escalated",
            "resolution_notes": f"Unknown action type '{action_type}', cannot execute.",
        }

    tool = next((t for t in tools if t.name == action_type), None)
    if tool is None:
        return {
            "status": "escalated",
            "resolution_notes": f"Could not find tool '{action_type}' to execute.",
        }

    result = await tool.ainvoke({arg_name: proposed["target"]})

    return {
        "status": "resolved",
        "resolution_notes": f"Executed {action_type} on {proposed['target']}: {result}",
    }
