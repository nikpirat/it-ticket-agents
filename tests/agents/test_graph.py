"""Tests for it_ticket_agents.agents.graph.

Uses simple fake node functions (not real LLM/Qdrant-backed nodes) to
verify the graph's actual routing and topology — the thing this module
is responsible for — without needing real API keys for every node. Each
individual node's own behavior is already tested in its own test file
(test_supervisor.py, test_diagnosis.py, etc.); this file verifies they're
wired together correctly.
"""

from it_ticket_agents.agents.graph import build_graph
from it_ticket_agents.agents.state import TicketState


def _make_initial_state(escalate_immediately: bool = False) -> TicketState:
    return TicketState(
        ticket_id="T-1",
        ticket={"title": "VPN down", "description": "Cannot connect"},
        category="",
        escalate_immediately=escalate_immediately,
        supervisor_reasoning="",
        diagnosis="",
        kb_context=[],
        proposed_action=None,
        requires_human_approval=False,
        status="",
        resolution_notes="",
    )


def _fake_supervisor(escalate: bool) -> object:
    def _node(state: TicketState) -> dict[str, object]:
        return {
            "category": "network",
            "escalate_immediately": escalate,
            "supervisor_reasoning": "Test reasoning.",
        }

    return _node


async def _fake_diagnosis(state: TicketState) -> dict[str, object]:
    return {"diagnosis": "vpn-gateway is down."}


def _fake_knowledge_base(state: TicketState) -> dict[str, object]:
    return {
        "kb_context": [
            {
                "text": "Restart vpn-gateway.",
                "section_heading": "Fix",
                "source_document": "vpn.md",
                "score": 0.9,
            }
        ]
    }


def _fake_action_with_proposal(state: TicketState) -> dict[str, object]:
    return {
        "proposed_action": {
            "action_type": "restart_service",
            "target": "vpn-gateway",
            "reasoning": "Runbook says restart.",
        },
        "requires_human_approval": True,
    }


def _fake_action_no_proposal(state: TicketState) -> dict[str, object]:
    return {"proposed_action": None, "requires_human_approval": False}


class TestGraphRouting:
    async def test_escalate_immediately_skips_straight_to_escalated(self) -> None:
        graph = build_graph(
            tools=[],
            supervisor_fn=_fake_supervisor(escalate=True),
            diagnosis_fn=_fake_diagnosis,
            knowledge_base_fn=_fake_knowledge_base,
            action_fn=_fake_action_with_proposal,
        )

        result = await graph.ainvoke(_make_initial_state(escalate_immediately=True))

        assert result["status"] == "escalated"
        assert "Test reasoning." in result["resolution_notes"]
        assert result["diagnosis"] == ""
        assert result["kb_context"] == []

    async def test_normal_flow_runs_all_worker_nodes_in_order(self) -> None:
        graph = build_graph(
            tools=[],
            supervisor_fn=_fake_supervisor(escalate=False),
            diagnosis_fn=_fake_diagnosis,
            knowledge_base_fn=_fake_knowledge_base,
            action_fn=_fake_action_with_proposal,
        )

        result = await graph.ainvoke(_make_initial_state())

        assert result["diagnosis"] == "vpn-gateway is down."
        assert len(result["kb_context"]) == 1
        assert result["status"] == "pending_approval"
        assert result["proposed_action"]["action_type"] == "restart_service"

    async def test_no_proposed_action_results_in_escalation(self) -> None:
        graph = build_graph(
            tools=[],
            supervisor_fn=_fake_supervisor(escalate=False),
            diagnosis_fn=_fake_diagnosis,
            knowledge_base_fn=_fake_knowledge_base,
            action_fn=_fake_action_no_proposal,
        )

        result = await graph.ainvoke(_make_initial_state())

        assert result["status"] == "escalated"
        assert result["proposed_action"] is None