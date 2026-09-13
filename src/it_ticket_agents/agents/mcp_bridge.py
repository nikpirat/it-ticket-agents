"""Bridges our MCP server's tools into LangChain-compatible tools.

Written by hand because langchain-mcp-adapters (the "official" bridge
package) has a hard, currently-unresolved dependency conflict with our
installed mcp SDK version: every published release (confirmed up through
0.3.2, the latest) requires mcp<2.0.0, while our own MCP server (Phase 1)
was correctly built against the current v2.x API. Rather than downgrade
our own, already-built and tested server back to the older FastMCP API,
this builds directly on the server's own list_tools()/call_tool()
methods - the same real, protocol-level operations the official bridge
package would itself be calling under the hood.
"""

import json
from collections.abc import Callable, Coroutine
from typing import Any

from langchain_core.tools import StructuredTool
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult
from pydantic import BaseModel, create_model

_JSON_SCHEMA_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def _build_args_schema(tool_name: str, input_schema: dict[str, Any]) -> type[BaseModel]:
    """Dynamically build a Pydantic model from an MCP tool's JSON schema
    so LangChain can validate and present arguments correctly.

    Deliberately simple, not general-purpose JSON-schema-to-Pydantic
    conversion - our own tools (Phase 1) only ever use simple scalar
    parameter types (str, and one optional str), so this covers our real
    tools without needing to handle nested objects, arrays, or enums.
    """
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    fields: dict[str, Any] = {}
    for field_name, field_schema in properties.items():
        json_type = field_schema.get("type", "string")
        python_type = _JSON_SCHEMA_TYPE_MAP.get(json_type, str)

        if field_name in required:
            fields[field_name] = (python_type, ...)
        else:
            fields[field_name] = (python_type | None, None)

    return create_model(f"{tool_name}Args", **fields)


async def _call_and_extract_text(
    server: MCPServer,
    tool_name: str,
    **kwargs: Any,  # noqa: ANN401
) -> str:
    """Call an MCP tool and extract its text content for the agent to read.

    kwargs is genuinely Any here, not a shortcut - these arguments match
    a dynamically-built Pydantic schema (_build_args_schema) whose field
    types vary per tool (str, int, float, bool), so there's no single
    concrete type to declare.
    """
    result = await server.call_tool(tool_name, kwargs)
    if not isinstance(result, CallToolResult):
        # call_tool's return type also allows InputRequiredResult, used
        # for MCP's interactive input-elicitation flow - none of our own
        # tools use that feature, so this should never happen
        # in practice, but failing clearly here beats an unhandled
        # AttributeError or silently wrong behavior if it ever does.
        raise TypeError(
            f"Tool '{tool_name}' returned {type(result).__name__}, "
            "expected CallToolResult (input-elicitation tools aren't supported)"
        )
    text_parts = [block.text for block in result.content if hasattr(block, "text")]
    return "\n".join(text_parts) if text_parts else json.dumps(result.structured_content)


def _make_tool_coroutine(
    server: MCPServer, tool_name: str
) -> Callable[..., Coroutine[Any, Any, str]]:
    """Build a coroutine bound to one specific tool name.

    A real, easy-to-get-wrong detail: without this factory function
    (i.e. defining the coroutine inline inside the loop below with
    tool_name captured directly from the loop variable), every generated
    tool would call whichever tool happened to be LAST in the loop - a
    classic late-binding closure bug in Python. Binding tool_name as a
    parameter to this outer function captures its value at call time,
    not at the loop's end.
    """

    async def _coroutine(**kwargs: Any) -> str:  # noqa: ANN401 - see _call_and_extract_text
        return await _call_and_extract_text(server, tool_name, **kwargs)

    return _coroutine


async def load_mcp_tools_as_langchain_tools(server: MCPServer) -> list[StructuredTool]:
    """Convert every tool registered on an MCP server into a LangChain
    StructuredTool, so LangGraph agents can bind and call them directly.
    """
    mcp_tools = await server.list_tools()
    langchain_tools = []

    for mcp_tool in mcp_tools:
        args_schema = _build_args_schema(mcp_tool.name, mcp_tool.input_schema)
        coroutine = _make_tool_coroutine(server, mcp_tool.name)

        langchain_tools.append(
            StructuredTool.from_function(
                coroutine=coroutine,
                name=mcp_tool.name,
                description=mcp_tool.description or "",
                args_schema=args_schema,
            )
        )

    return langchain_tools