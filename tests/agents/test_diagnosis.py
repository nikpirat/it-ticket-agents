"""Tests for it_ticket_agents.agents.diagnosis.

Fakes the `diagnose` callable rather than create_react_agent/Claude
internals - verifies our own node logic (message construction, tools
threading, state merging), not the agent's actual reasoning, which needs
a real API key.
"""

from langchain_core.tools import StructuredTool

from it_ticket_agents.agents.diagnosis import _build_user_message, diagnosis_node
from it_ticket_agents.agents.state import TicketState


def _make_state(category: str = "network") -> TicketState:
    return TicketState(
        ticket_id="T-1",
        ticket={"title": "VPN down", "description": "Cannot connect to VPN"},
        category=category,
        escalate_immediately=False,
        supervisor_reasoning="",
        diagnosis="",
        kb_context=[],
        proposed_action=None,
        requires_human_approval=False,
        status="",
        resolution_notes="",
    )


class TestBuildUserMessage:
    def test_includes_category_and_ticket_details(self) -> None:
        message = _build_user_message(_make_state(category="network"))

        assert "network" in message
        assert "VPN down" in message
        assert "Cannot connect to VPN" in message


class TestDiagnosisNode:
    async def test_returns_diagnosis_from_agent(self) -> None:
        async def fake_diagnose(user_message: str, tools: list[StructuredTool]) -> str:
            return "vpn-gateway service is currently down."

        result = await diagnosis_node(_make_state(), tools=[], diagnose=fake_diagnose)

        assert result == {"diagnosis": "vpn-gateway service is currently down."}

    async def test_passes_ticket_details_through_to_diagnose(self) -> None:
        captured: dict[str, object] = {}

        async def fake_diagnose(user_message: str, tools: list[StructuredTool]) -> str:
            captured["user_message"] = user_message
            captured["tool_count"] = len(tools)
            return "diagnosis"

        fake_tool = StructuredTool.from_function(
            func=lambda: "ok", name="fake_tool", description="A fake tool."
        )

        await diagnosis_node(_make_state(), tools=[fake_tool], diagnose=fake_diagnose)

        assert "VPN down" in str(captured["user_message"])
        assert captured["tool_count"] == 1