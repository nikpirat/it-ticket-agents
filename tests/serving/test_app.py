"""Tests for the FastAPI serving application.

Uses a REAL compiled graph with fake node functions (same pattern as
test_graph.py/test_execute_action.py) rather than a bare stub object -
this gives genuine confidence the app-to-graph wiring (state
construction, config/thread_id handling, interrupt/resume across two
separate requests) actually works, not just that a mock was called
correctly.
"""

from pathlib import Path

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from it_ticket_agents.agents.graph import build_graph
from it_ticket_agents.agents.state import TicketState
from it_ticket_agents.mcp_server.mock_state import MockStateStore, Ticket
from it_ticket_agents.serving.app import create_app


def _fake_supervisor_escalate(state: TicketState) -> dict[str, object]:
    return {
        "category": "other",
        "escalate_immediately": True,
        "supervisor_reasoning": "Privileged account.",
    }


def _fake_supervisor_normal(state: TicketState) -> dict[str, object]:
    return {"category": "network", "escalate_immediately": False, "supervisor_reasoning": ""}


async def _fake_diagnosis(state: TicketState) -> dict[str, object]:
    return {"diagnosis": "vpn-gateway is down."}


def _fake_knowledge_base(state: TicketState) -> dict[str, object]:
    return {"kb_context": []}


def _fake_action_proposes(state: TicketState) -> dict[str, object]:
    return {
        "proposed_action": {
            "action_type": "restart_service",
            "target": "vpn-gateway",
            "reasoning": "Runbook says restart.",
        },
        "requires_human_approval": True,
    }


async def _fake_execute_action(state: TicketState) -> dict[str, object]:
    from langgraph.types import interrupt

    approved = interrupt({"proposed_action": state["proposed_action"]})
    if approved:
        return {"status": "resolved", "resolution_notes": "Restarted vpn-gateway."}
    return {"status": "escalated", "resolution_notes": "Rejected by human reviewer."}


def _make_app(tmp_path: Path, escalate_immediately: bool) -> tuple[object, Path]:
    db_path = tmp_path / "state.db"
    store = MockStateStore(db_path)
    store.create_ticket(
        Ticket(
            id="T-1",
            title="VPN down",
            description="Cannot connect",
            status="open",
            priority="high",
            category="network",
            requester="jsmith",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    store.close()

    supervisor_fn = _fake_supervisor_escalate if escalate_immediately else _fake_supervisor_normal

    async def fake_graph_builder() -> CompiledStateGraph[TicketState]:
        return build_graph(
            tools=[],
            checkpointer=InMemorySaver(),
            supervisor_fn=supervisor_fn,
            diagnosis_fn=_fake_diagnosis,
            knowledge_base_fn=_fake_knowledge_base,
            action_fn=_fake_action_proposes,
            execute_action_fn=_fake_execute_action,
        )

    app = create_app(
        graph_builder=fake_graph_builder,
        ticket_store_builder=lambda: MockStateStore(db_path),
    )
    return app, db_path


class TestHealthEndpoint:
    def test_returns_ok(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path, escalate_immediately=False)
        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestProcessTicket:
    def test_unknown_ticket_returns_404(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path, escalate_immediately=False)
        with TestClient(app) as client:
            response = client.post("/tickets/does-not-exist/process")

        assert response.status_code == 404

    def test_immediate_escalation_returns_escalated_directly(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path, escalate_immediately=True)
        with TestClient(app) as client:
            response = client.post("/tickets/T-1/process")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "escalated"
        assert body["pending_approval"] is False

    def test_normal_flow_pauses_for_approval(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path, escalate_immediately=False)
        with TestClient(app) as client:
            response = client.post("/tickets/T-1/process")

        assert response.status_code == 200
        body = response.json()
        assert body["pending_approval"] is True
        assert body["proposed_action"]["action_type"] == "restart_service"


class TestApproval:
    def test_approving_resolves_the_ticket(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path, escalate_immediately=False)
        with TestClient(app) as client:
            client.post("/tickets/T-1/process")
            response = client.post("/tickets/T-1/approval", json={"approved": True})

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "resolved"
        assert body["pending_approval"] is False

    def test_rejecting_escalates_the_ticket(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path, escalate_immediately=False)
        with TestClient(app) as client:
            client.post("/tickets/T-1/process")
            response = client.post("/tickets/T-1/approval", json={"approved": False})

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "escalated"
