"""Supervisor node: classifies a ticket and decides initial routing.

Uses Haiku (fast, cheap) since this is a classification task, not one
requiring deep reasoning - reserving Sonnet for the agents that actually
need it (diagnosis, action proposals).
"""

from collections.abc import Callable
from typing import Literal

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from it_ticket_agents.agents.state import TicketState
from it_ticket_agents.config.settings import settings

SYSTEM_PROMPT = """You are the triage supervisor for an IT support ticket \
system. Given a ticket's title and description, classify it and decide \
whether it should be escalated to a human immediately rather than \
processed automatically.

Categories: network (VPN, connectivity), account (lockouts, password \
resets), service (internal service outages, e.g. wiki, file share), \
other (anything that doesn't clearly fit the above).

Escalate immediately (escalate_immediately=true) if the ticket:
- Involves a privileged, administrative, or customer-facing system
- Shows signs of a security incident rather than a routine operational \
issue
- Cannot be clearly categorized into one of the three known categories

Otherwise, escalate_immediately=false - it will be routed to the \
appropriate specialist agent for diagnosis and remediation."""


class SupervisorDecision(BaseModel):
    category: Literal["network", "account", "service", "other"] = Field(
        description="The ticket's category, based on its title and description."
    )
    escalate_immediately: bool = Field(
        description=(
            "True if this ticket should skip automated handling and go straight to a human."
        )
    )
    reasoning: str = Field(
        description="Brief explanation of the classification and escalation decision."
    )


def build_supervisor_llm() -> ChatAnthropic:
    """Build the Haiku-backed LLM used for triage classification."""
    return ChatAnthropic(
        model=settings.claude_haiku_model,
        max_tokens=settings.anthropic_max_tokens,
        temperature=0,
    )


def _build_messages(ticket: dict[str, object]) -> list[dict[str, str]]:
    user_content = (
        f"Ticket title: {ticket.get('title', '')}\n"
        f"Ticket description: {ticket.get('description', '')}\n"
        f"Priority: {ticket.get('priority', '')}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _default_decide(messages: list[dict[str, str]]) -> SupervisorDecision:
    llm = build_supervisor_llm()
    structured_llm = llm.with_structured_output(SupervisorDecision)
    decision = structured_llm.invoke(messages)
    if not isinstance(decision, SupervisorDecision):
        raise TypeError(f"Expected SupervisorDecision, got {type(decision).__name__}")
    return decision


def supervisor_node(
    state: TicketState,
    decide: Callable[[list[dict[str, str]]], SupervisorDecision] = _default_decide,
) -> dict[str, object]:
    """LangGraph node: classify the ticket and decide initial routing.

    Accepts an optional `decide` callable (rather than always calling the
    real LLM internally) so tests can inject a fake decision-maker
    without needing a real Anthropic API key or faking LangChain's
    internal Runnable chains.
    """
    messages = _build_messages(state["ticket"])
    decision = decide(messages)

    return {
        "category": decision.category,
        "escalate_immediately": decision.escalate_immediately,
        "supervisor_reasoning": decision.reasoning,
    }
