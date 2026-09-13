"""Tests for it_ticket_agents.agents.action.

Fakes the `decide` callable, same pattern as the supervisor tests —
verifies our own node logic, not Claude's actual reasoning.
"""

from it_ticket_agents.agents.action import ProposedAction, _build_messages, action_node
from it_ticket_agents.agents.state import TicketState


def _make_state(
    diagnosis: str = "vpn-gateway is down.",
    kb_context: list | None = None,  # type: ignore[type-arg]
) -> TicketState:
    return TicketState(
        ticket_id="T-1",
        ticket={"title": "VPN down", "description": "Cannot connect"},
        category="network",
        escalate_immediately=False,
        supervisor_reasoning="",
        diagnosis=diagnosis,
        kb_context=kb_context
        if kb_context is not None
        else [
            {
                "text": "Restart vpn-gateway to resolve gateway unreachable errors.",
                "section_heading": "VPN fix",
                "source_document": "vpn.md",
                "score": 0.9,
            }
        ],
        proposed_action=None,
        requires_human_approval=False,
        status="",
        resolution_notes="",
    )


class TestBuildMessages:
    def test_includes_diagnosis_and_kb_context(self) -> None:
        messages = _build_messages(_make_state())

        user_content = messages[1]["content"]
        assert "vpn-gateway is down." in user_content
        assert "Restart vpn-gateway" in user_content
        assert "vpn.md" in user_content

    def test_handles_empty_kb_context(self) -> None:
        messages = _build_messages(_make_state(kb_context=[]))

        assert "(none found)" in messages[1]["content"]


class TestActionNode:
    def test_proposes_action_when_decision_has_action(self) -> None:
        def fake_decide(messages: list[dict[str, str]]) -> ProposedAction:
            return ProposedAction(
                has_action=True,
                action_type="restart_service",
                target="vpn-gateway",
                reasoning="Runbook says restart resolves this.",
            )

        result = action_node(_make_state(), decide=fake_decide)

        assert result["requires_human_approval"] is True
        assert result["proposed_action"] == {
            "action_type": "restart_service",
            "target": "vpn-gateway",
            "reasoning": "Runbook says restart resolves this.",
        }

    def test_no_action_when_decision_says_escalate(self) -> None:
        def fake_decide(messages: list[dict[str, str]]) -> ProposedAction:
            return ProposedAction(
                has_action=False,
                action_type="none",
                target="",
                reasoning="Privileged account, runbook says escalate.",
            )

        result = action_node(_make_state(), decide=fake_decide)

        assert result["proposed_action"] is None
        assert result["requires_human_approval"] is False
