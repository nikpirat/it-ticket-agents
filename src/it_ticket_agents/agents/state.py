"""Shared state schema for the ticket-processing agent graph.

A TypedDict, LangGraph's standard state representation - every node in
the graph reads from and writes to this same shared structure.
"""

from typing import TypedDict


class TicketState(TypedDict):
    """State threaded through the whole agent graph for one ticket."""

    ticket_id: str
    ticket: dict[str, object]
    """Full ticket details, from the get_ticket tool."""

    category: str
    """Supervisor's classification: network, account, service, or other."""

    escalate_immediately: bool
    """Supervisor's decision - True skips straight to escalation, bypassing
    diagnosis/KB/action entirely (see escalation-criteria.md runbook)."""

    supervisor_reasoning: str

    diagnosis: str
    """Diagnosis agent's findings, grounded in tool calls against current
    system state (not just the ticket description)."""

    kb_context: list[dict[str, object]]
    """Retrieved runbook chunks relevant to this ticket's category and diagnosis."""

    proposed_action: dict[str, object] | None
    """Action agent's proposed remediation, grounded in kb_context. None if
    no automatable action applies (e.g. the runbook says escalate)."""

    requires_human_approval: bool

    status: str
    """Final ticket status: resolved or escalated."""

    resolution_notes: str