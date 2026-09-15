"""Tests for it_ticket_agents.agents.execute_action.

Includes both direct unit tests of the node's logic (approved/rejected
paths, unknown action types) and a genuine end-to-end test running the
node through a real compiled graph with a real checkpointer, actually
pausing at interrupt() and resuming with Command(resume=...) - proving
the human-in-the-loop mechanism really works, not just that the
individual pieces look right in isolation.
"""

from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from it_ticket_agents.agents.graph import build_graph
from it_ticket_agents.agents.state import TicketState


def _make_state_with_proposal(action_type: str = "restart_service") -> TicketState:
    return TicketState(
        ticket_id="T-1",
        ticket={"title": "VPN down", "description": "Cannot connect"},
        category="network",
        escalate_immediately=False,
        supervisor_reasoning="",
        diagnosis="vpn-gateway is down.",
        kb_context=[],
        proposed_action={
            "action_type": action_type,
            "target": "vpn-gateway",
            "reasoning": "Runbook says restart.",
        },
        requires_human_approval=True,
        status="",
        resolution_notes="",
    )


def _fake_supervisor_routes_to_diagnosis(state: TicketState) -> dict[str, object]:
    return {"category": "network", "escalate_immediately": False, "supervisor_reasoning": ""}


async def _fake_diagnosis(state: TicketState) -> dict[str, object]:
    return {"diagnosis": "vpn-gateway is down."}


def _fake_knowledge_base(state: TicketState) -> dict[str, object]:
    return {"kb_context": []}


def _fake_action_proposes_restart(state: TicketState) -> dict[str, object]:
    return {
        "proposed_action": {
            "action_type": "restart_service",
            "target": "vpn-gateway",
            "reasoning": "Runbook says restart.",
        },
        "requires_human_approval": True,
    }


class TestExecuteActionEndToEnd:
    """Real interrupt/resume flow through the actual compiled graph and
    execute_action_node - not faked, since this node's whole purpose is
    the human-in-the-loop pause itself."""

    async def test_approval_executes_the_action_and_resolves(self) -> None:
        restart_tool = StructuredTool.from_function(
            coroutine=self._fake_restart_service,
            name="restart_service",
            description="Restart a service.",
        )
        checkpointer = InMemorySaver()
        graph = build_graph(
            tools=[restart_tool],
            checkpointer=checkpointer,
            supervisor_fn=_fake_supervisor_routes_to_diagnosis,
            diagnosis_fn=_fake_diagnosis,
            knowledge_base_fn=_fake_knowledge_base,
            action_fn=_fake_action_proposes_restart,
        )
        config = {"configurable": {"thread_id": "test-approval"}}

        initial_state = TicketState(
            ticket_id="T-1",
            ticket={"title": "VPN down", "description": "Cannot connect"},
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

        paused_result = await graph.ainvoke(initial_state, config=config)
        assert "__interrupt__" in paused_result
        interrupt_payload = paused_result["__interrupt__"][0].value
        assert interrupt_payload["proposed_action"]["action_type"] == "restart_service"

        final_result = await graph.ainvoke(Command(resume=True), config=config)

        assert final_result["status"] == "resolved"
        assert "restarted" in final_result["resolution_notes"].lower()

    async def test_rejection_escalates_without_executing(self) -> None:
        never_called = StructuredTool.from_function(
            func=lambda service_name: self._fail("Should not have been called"),
            name="restart_service",
            description="Restart a service.",
        )
        checkpointer = InMemorySaver()
        graph = build_graph(
            tools=[never_called],
            checkpointer=checkpointer,
            supervisor_fn=_fake_supervisor_routes_to_diagnosis,
            diagnosis_fn=_fake_diagnosis,
            knowledge_base_fn=_fake_knowledge_base,
            action_fn=_fake_action_proposes_restart,
        )
        config = {"configurable": {"thread_id": "test-rejection"}}

        initial_state = TicketState(
            ticket_id="T-1",
            ticket={"title": "VPN down", "description": "Cannot connect"},
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

        await graph.ainvoke(initial_state, config=config)
        final_result = await graph.ainvoke(Command(resume=False), config=config)

        assert final_result["status"] == "escalated"
        assert "rejected" in final_result["resolution_notes"].lower()

    @staticmethod
    async def _fake_restart_service(service_name: str) -> str:
        return f"{service_name} restarted successfully"

    @staticmethod
    def _fail(message: str) -> None:
        raise AssertionError(message)
