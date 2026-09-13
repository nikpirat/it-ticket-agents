"""Action agent node: proposes a remediation action grounded in the
knowledge base, WITHOUT executing it.

Actual execution requires human-in-the-loop approval (Phase 4) - this
node's job is only to decide WHAT to propose, using structured output
(like the supervisor) rather than a tool-calling loop, since proposing
an action doesn't require calling any tools itself.
"""

from collections.abc import Callable
from typing import Literal

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from it_ticket_agents.agents.state import TicketState
from it_ticket_agents.config.settings import settings

SYSTEM_PROMPT = """You are an IT remediation planning agent. Given a \
ticket's diagnosis and relevant runbook excerpts, decide what \
remediation action to propose, if any.

Only propose an action if the runbook excerpts clearly describe it as a \
standard, safe remediation for this situation. If the runbooks indicate \
escalation is appropriate instead (e.g. a privileged account, a repeat \
failure, or a pattern the runbooks explicitly say to escalate), set \
has_action=false and explain why in your reasoning.

Available actions: restart_service (requires service_name), \
reset_password (requires username). Do not propose any other action."""


class ProposedAction(BaseModel):
    has_action: bool = Field(
        description="True if a specific, safe remediation action should be proposed."
    )
    action_type: Literal["restart_service", "reset_password", "none"] = Field(
        description="Which action to take, or 'none' if has_action is false."
    )
    target: str = Field(
        description=("The service_name or username the action applies to, or empty string if none.")
    )
    reasoning: str = Field(
        description=(
            "Why this action (or no action) is appropriate, grounded in the runbook excerpts."
        )
    )


def build_action_llm() -> ChatAnthropic:
    """Build the Sonnet-backed LLM used for action planning - this needs
    real reasoning about whether the runbooks actually support
    automating this specific situation, not just pattern-matching a
    category."""
    return ChatAnthropic(
        model=settings.claude_sonnet_model,
        max_tokens=settings.anthropic_max_tokens,
        temperature=0,
    )


def _build_messages(state: TicketState) -> list[dict[str, str]]:
    kb_text = "\n\n".join(
        f"[{c['section_heading']}] ({c['source_document']})\n{c['text']}"
        for c in state["kb_context"]
    )
    user_content = (
        f"Diagnosis: {state['diagnosis']}\n\n"
        f"Relevant runbook excerpts:\n{kb_text if kb_text else '(none found)'}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _default_decide(messages: list[dict[str, str]]) -> ProposedAction:
    llm = build_action_llm()
    structured_llm = llm.with_structured_output(ProposedAction)
    decision = structured_llm.invoke(messages)
    if not isinstance(decision, ProposedAction):
        raise TypeError(f"Expected ProposedAction, got {type(decision).__name__}")
    return decision


def action_node(
    state: TicketState,
    decide: Callable[[list[dict[str, str]]], ProposedAction] = _default_decide,
) -> dict[str, object]:
    """LangGraph node: propose a remediation action grounded in
    kb_context.

    Never executes anything itself - the graph's next step (Phase 4)
    gates actual execution on human approval.
    """
    messages = _build_messages(state)
    decision = decide(messages)

    if not decision.has_action:
        return {
            "proposed_action": None,
            "requires_human_approval": False,
        }

    return {
        "proposed_action": {
            "action_type": decision.action_type,
            "target": decision.target,
            "reasoning": decision.reasoning,
        },
        "requires_human_approval": True,
    }
