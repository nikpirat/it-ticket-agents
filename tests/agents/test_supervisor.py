"""Tests for it_ticket_agents.agents.supervisor.

Fakes the `decide` callable rather than the LLM/LangChain internals —
this verifies our own node logic (prompt construction, state merging),
not Claude's actual classification behavior, which needs a real API key
and isn't something a unit test should depend on.
"""

from it_ticket_agents.agents.state import TicketState
from it_ticket_agents.agents.supervisor import (
    SupervisorDecision,
    _build_messages,
    supervisor_node,
)


def _make_state(title: str = "VPN down", description: str = "desc") -> TicketState:
    return TicketState(
        ticket_id="T-1",
        ticket={"title": title, "description": description, "priority": "high"},
        category="",
        escalate_immediately=False,
        supervisor_reasoning="",
        diagnosis="",
        kb_context=[],
        proposed_action=None,
        requires_human_approval=False,
        status="",
        resolution_notes="",
    )


class TestBuildMessages:
    def test_includes_ticket_details(self) -> None:
        messages = _build_messages(
            {"title": "VPN down", "description": "Cannot connect", "priority": "high"}
        )

        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "VPN down" in messages[1]["content"]
        assert "Cannot connect" in messages[1]["content"]
        assert "high" in messages[1]["content"]


class TestSupervisorNode:
    def test_returns_only_the_state_keys_it_computes(self) -> None:
        def fake_decide(messages: list[dict[str, str]]) -> SupervisorDecision:
            return SupervisorDecision(
                category="network", escalate_immediately=False, reasoning="VPN issue."
            )

        result = supervisor_node(_make_state(), decide=fake_decide)

        assert result == {
            "category": "network",
            "escalate_immediately": False,
            "supervisor_reasoning": "VPN issue.",
        }

    def test_passes_ticket_details_through_to_decide(self) -> None:
        captured: list[dict[str, str]] = []

        def fake_decide(messages: list[dict[str, str]]) -> SupervisorDecision:
            captured.extend(messages)
            return SupervisorDecision(
                category="account", escalate_immediately=False, reasoning="Lockout."
            )

        supervisor_node(
            _make_state(title="Locked out", description="Cannot log in"), decide=fake_decide
        )

        assert any("Locked out" in m["content"] for m in captured)

    def test_escalate_immediately_flag_is_passed_through(self) -> None:
        def fake_decide(messages: list[dict[str, str]]) -> SupervisorDecision:
            return SupervisorDecision(
                category="other",
                escalate_immediately=True,
                reasoning="Privileged account, needs human review.",
            )

        result = supervisor_node(_make_state(), decide=fake_decide)

        assert result["escalate_immediately"] is True