"""Wires the ticket-processing agent nodes into an executable LangGraph
StateGraph.

Topology:
    supervisor --(escalate_immediately?)--> escalate [terminal]
               --(else)--> diagnosis -> knowledge_base -> action -> finalize [terminal]

Phase 4 will add human-in-the-loop interruption before actually executing
a proposed action — this phase stops at "pending_approval", not
execution itself. Confirmed via a minimal real test that LangGraph
correctly supports mixing sync nodes (supervisor, knowledge_base, action,
escalate, finalize) and async nodes (diagnosis, which awaits its
create_react_agent tool-calling loop) within one graph, invoked via
.ainvoke().
"""

from collections.abc import Callable
from functools import partial
from typing import Any

from langchain_core.tools import StructuredTool
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from it_ticket_agents.agents.action import action_node
from it_ticket_agents.agents.diagnosis import diagnosis_node
from it_ticket_agents.agents.knowledge_base import knowledge_base_node
from it_ticket_agents.agents.state import TicketState
from it_ticket_agents.agents.supervisor import supervisor_node

# LangGraph's add_node has a heavily overloaded, structurally specific
# generic protocol (_Node[NodeInputT] and friends) that our own node
# functions satisfy individually (each has its own precise signature),
# but a shared Callable type alias doesn't structurally match closely
# enough for mypy to accept it as a swappable parameter. Callable[...,
# Any] here is a pragmatic concession to that framework typing
# complexity, not a sign the underlying functions are loosely typed —
# each one (supervisor_node, diagnosis_node, etc.) still has its own
# strict signature where it's actually defined.
NodeFn = Callable[..., Any]


def _escalate_node(state: TicketState) -> dict[str, object]:
    """Terminal node for tickets the supervisor flags for immediate
    escalation — no diagnosis/KB/action processing needed."""
    return {
        "status": "escalated",
        "resolution_notes": f"Escalated by supervisor: {state['supervisor_reasoning']}",
    }


def _finalize_node(state: TicketState) -> dict[str, object]:
    """Terminal node after the action agent has run. If it proposed an
    action, the ticket is pending human approval (Phase 4 executes it
    upon approval); if not, the action agent itself determined
    escalation is appropriate given what the runbooks say.
    """
    if state["requires_human_approval"]:
        return {
            "status": "pending_approval",
            "resolution_notes": f"Proposed action awaiting approval: {state['proposed_action']}",
        }
    return {
        "status": "escalated",
        "resolution_notes": "Escalated: no safe automated action identified.",
    }


def _route_after_supervisor(state: TicketState) -> str:
    return "escalate" if state["escalate_immediately"] else "diagnosis"


def build_graph(
    tools: list[StructuredTool],
    supervisor_fn: NodeFn = supervisor_node,
    diagnosis_fn: NodeFn | None = None,
    knowledge_base_fn: NodeFn = knowledge_base_node,
    action_fn: NodeFn = action_node,
) -> CompiledStateGraph[TicketState]:
    """Build and compile the ticket-processing agent graph.

    Accepts pre-configured node callables (each defaulting to the real
    implementation) rather than exposing every node's own internal
    dependencies (LLM clients, Qdrant clients, etc.) through this
    function's signature — that would make this signature unwieldy given
    four different nodes each with their own injectable seams. Tests
    instead pass simple fake node functions directly to verify the
    graph's routing/topology (escalation branching, sequential flow)
    without needing real API keys for every node's LLM call.

    Args:
        tools: pre-loaded LangChain tools (via
            mcp_bridge.load_mcp_tools_as_langchain_tools) for the
            diagnosis node. Loading MCP tools is itself an async
            operation, so it happens once before graph construction, not
            per ticket.
        diagnosis_fn: defaults to diagnosis_node with `tools` bound via
            partial — pass a fake async callable in tests instead.
    """
    if diagnosis_fn is None:
        diagnosis_fn = partial(diagnosis_node, tools=tools)

    graph: StateGraph[TicketState] = StateGraph(TicketState)

    graph.add_node("supervisor", supervisor_fn)
    graph.add_node("diagnosis", diagnosis_fn)
    graph.add_node("knowledge_base", knowledge_base_fn)
    graph.add_node("action", action_fn)
    graph.add_node("escalate", _escalate_node)
    graph.add_node("finalize", _finalize_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {"escalate": "escalate", "diagnosis": "diagnosis"},
    )
    graph.add_edge("diagnosis", "knowledge_base")
    graph.add_edge("knowledge_base", "action")
    graph.add_edge("action", "finalize")
    graph.add_edge("escalate", END)
    graph.add_edge("finalize", END)

    return graph.compile()