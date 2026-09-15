"""Diagnosis agent node: investigates a ticket by calling diagnostic
tools against current system state, then synthesizes findings.

Uses Sonnet with LangGraph's prebuilt create_react_agent - this needs
real reasoning (deciding which tool to call based on ticket category,
interpreting the result), not just classification like the supervisor.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from it_ticket_agents.agents.state import TicketState
from it_ticket_agents.config.settings import settings

SYSTEM_PROMPT = """You are an IT diagnosis agent. Given a ticket's \
details, investigate the relevant system state using the tools \
available to you (checking service status for network/service issues, \
account status for account issues) and summarize your findings in one \
or two clear sentences. Always call at least one relevant tool before \
responding - do not guess at system state from the ticket description \
alone."""


def build_diagnosis_llm() -> ChatAnthropic:
    """Build the Sonnet-backed LLM used for diagnosis — this needs real
    reasoning about which tool to call and how to interpret its result,
    unlike the supervisor's pure classification task.

    No temperature parameter: confirmed via multiple current sources and
    Anthropic's own Sonnet 5 migration notes that Sonnet 5 (and Opus
    4.7+) reject temperature/top_p/top_k entirely at any non-default
    value, returning a 400 error — "steer with the prompt" is the
    documented replacement. Haiku 4.5 (used by the supervisor) still
    accepts temperature fine; this constraint is specific to the newer
    Sonnet/Opus generation, not a general Anthropic API change.
    """
    return ChatAnthropic(
        model=settings.claude_sonnet_model,
        max_tokens=settings.anthropic_max_tokens,
    )


def _build_user_message(state: TicketState) -> str:
    ticket = state["ticket"]
    return (
        f"Ticket category: {state['category']}\n"
        f"Title: {ticket.get('title', '')}\n"
        f"Description: {ticket.get('description', '')}"
    )


async def _default_diagnose(user_message: str, tools: list[StructuredTool]) -> str:
    llm = build_diagnosis_llm()
    agent = create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": user_message}]})
    final_message = result["messages"][-1]
    return str(final_message.content)


async def diagnosis_node(
    state: TicketState,
    tools: list[StructuredTool],
    diagnose: Callable[[str, list[StructuredTool]], Coroutine[Any, Any, str]] = _default_diagnose,
) -> dict[str, object]:
    """LangGraph node: investigate the ticket using diagnostic tools.

    `tools` must be provided by the caller (built once via the MCP
    bridge when the graph is constructed, not rebuilt on every node
    call - MCP tool loading is itself an async operation against the
    server's list_tools(), not something to repeat per ticket).

    Accepts an optional `diagnose` callable (same dependency-injection
    pattern as the supervisor's `decide`) so tests can fake the agent's
    reasoning without needing a real Anthropic API key or invoking a
    real create_react_agent loop.
    """
    user_message = _build_user_message(state)
    diagnosis = await diagnose(user_message, tools)
    return {"diagnosis": diagnosis}
