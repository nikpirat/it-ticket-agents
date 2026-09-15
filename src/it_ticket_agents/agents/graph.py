"""Wires the ticket-processing agent nodes into an executable LangGraph
StateGraph.

Topology:
    supervisor --(escalate_immediately?)--> escalate ------\
               --(else)--> diagnosis -> knowledge_base -> action  |
                   --(requires_human_approval?)--> execute_action |
                       [pauses for approval, then resolved         |
                       or escalated]                               |--> persist_status --> END
                   --(else)--> finalize [escalated — no safe      |
                       action found]                               |
                                                            -------/

persist_status is a shared convergence point: all three terminal
outcomes (immediate escalation, no-safe-action escalation, and
resolved/rejected via execute_action) route through it before END, so
the graph's final status/resolution_notes gets written back to the
ticket's actual persisted record via the update_ticket_status MCP tool —
without this, a "resolved" outcome only existed in LangGraph's own state
and the API response, never reaching the real ticket record (a real gap
found via live end-to-end testing).

execute_action's human-in-the-loop pause requires a checkpointer (see
build_graph's `checkpointer` parameter) — confirmed via a minimal real
test before building this that LangGraph's interrupt()/Command(resume=)
mechanism needs one to persist state between the pause and the resume.

Confirmed via a minimal real test that LangGraph correctly supports
mixing sync nodes (supervisor, knowledge_base, action, escalate,
finalize) and async nodes (diagnosis, execute_action, persist_status)
within one graph, invoked via .ainvoke().
"""

from collections.abc import Callable
from functools import partial
from typing import Any

from langchain_core.tools import StructuredTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from it_ticket_agents.agents.action import action_node
from it_ticket_agents.agents.diagnosis import diagnosis_node
from it_ticket_agents.agents.execute_action import execute_action_node
from it_ticket_agents.agents.knowledge_base import knowledge_base_node
from it_ticket_agents.agents.persist_status import persist_status_node
from it_ticket_agents.agents.state import TicketState
from it_ticket_agents.agents.supervisor import supervisor_node

NodeFn = Callable[..., Any]


def _escalate_node(state: TicketState) -> dict[str, object]:
    """Terminal node for tickets the supervisor flags for immediate
    escalation — no diagnosis/KB/action processing needed."""
    return {
        "status": "escalated",
        "resolution_notes": f"Escalated by supervisor: {state['supervisor_reasoning']}",
    }


def _finalize_node(state: TicketState) -> dict[str, object]:
    """Reached only when the action agent found no safe automated action
    to propose (requires_human_approval is False) — the action agent
    itself determined escalation is appropriate given what the runbooks
    say. When an action WAS proposed, execute_action_node handles the
    outcome instead, after the human-in-the-loop pause.
    """
    return {
        "status": "escalated",
        "resolution_notes": "Escalated: no safe automated action identified.",
    }


def _route_after_supervisor(state: TicketState) -> str:
    return "escalate" if state["escalate_immediately"] else "diagnosis"


def _route_after_action(state: TicketState) -> str:
    return "execute_action" if state["requires_human_approval"] else "finalize"


def build_graph(
    tools: list[StructuredTool],
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    supervisor_fn: NodeFn = supervisor_node,
    diagnosis_fn: NodeFn | None = None,
    knowledge_base_fn: NodeFn = knowledge_base_node,
    action_fn: NodeFn = action_node,
    execute_action_fn: NodeFn | None = None,
    persist_status_fn: NodeFn | None = None,
) -> CompiledStateGraph[TicketState]:
    """Build and compile the ticket-processing agent graph.

    Accepts pre-configured node callables (each defaulting to the real
    implementation) rather than exposing every node's own internal
    dependencies (LLM clients, Qdrant clients, etc.) through this
    function's signature — that would make this signature unwieldy given
    several nodes each with their own injectable seams. Tests instead
    pass simple fake node functions directly to verify the graph's
    routing/topology without needing real API keys for every node's LLM
    call.

    Args:
        tools: pre-loaded LangChain tools (via
            mcp_bridge.load_mcp_tools_as_langchain_tools) for the
            diagnosis, execute_action, and persist_status nodes. Loading
            MCP tools is itself an async operation, so it happens once
            before graph construction, not per ticket.
        checkpointer: required for execute_action's human-in-the-loop
            pause to work — without one, a paused graph has nowhere to
            persist its state between the pause and the resume. None is
            accepted (and left to LangGraph's own default handling) for
            graphs that never reach execute_action in tests.
        diagnosis_fn / execute_action_fn / persist_status_fn: default to
            the real node with `tools` bound via partial — pass fake
            callables in tests.
    """
    if diagnosis_fn is None:
        diagnosis_fn = partial(diagnosis_node, tools=tools)
    if execute_action_fn is None:
        execute_action_fn = partial(execute_action_node, tools=tools)
    if persist_status_fn is None:
        persist_status_fn = partial(persist_status_node, tools=tools)

    graph: StateGraph[TicketState] = StateGraph(TicketState)

    graph.add_node("supervisor", supervisor_fn)
    graph.add_node("diagnosis", diagnosis_fn)
    graph.add_node("knowledge_base", knowledge_base_fn)
    graph.add_node("action", action_fn)
    graph.add_node("execute_action", execute_action_fn)
    graph.add_node("escalate", _escalate_node)
    graph.add_node("finalize", _finalize_node)
    graph.add_node("persist_status", persist_status_fn)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {"escalate": "escalate", "diagnosis": "diagnosis"},
    )
    graph.add_edge("diagnosis", "knowledge_base")
    graph.add_edge("knowledge_base", "action")
    graph.add_conditional_edges(
        "action",
        _route_after_action,
        {"execute_action": "execute_action", "finalize": "finalize"},
    )
    graph.add_edge("execute_action", "persist_status")
    graph.add_edge("escalate", "persist_status")
    graph.add_edge("finalize", "persist_status")
    graph.add_edge("persist_status", END)

    return graph.compile(checkpointer=checkpointer)
