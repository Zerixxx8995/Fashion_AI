"""
Shopping Agent — ml-backend/app/core/shopping_agent.py

Responsibility: Pure LangGraph agent logic and tool definitions.
No HTTP. No database access. No caching. No business logic outside tool calls.

Architecture (Feature 2):
  The agent is a stateful graph:
    [reasoning node]     — LLM reads query, decides which tool(s) to call
    [tool execution]     — calls one or more of the three tools below
    [observation node]   — LLM reads tool results, loops back if more tools needed
    [response node]      — LLM generates final cited answer from all tool results

Three tools the agent can call:
  1. similarity_search   — calls similarity_service.find_similar_products()
  2. budget_optimizer    — calls budget_service.optimize_budget()
  3. wardrobe_fetcher    — fetches wardrobe items from PostgreSQL

Design constraints (from spec):
  - Agent MUST call at least one tool before responding — never answers from memory.
  - products_cited ONLY contains items returned by tools — validated in agent loop.
  - Response is under 150 words — enforced in system prompt.
  - System prompt says "Never invent product names, prices, or URLs".
  - Agent logs which tools were called and in what order (NF16).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — spec constraint: must contain "Never invent product names..."
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a personal shopping assistant for an Indian fashion app.
You help users find products, plan outfits, and make smart purchasing decisions.

You have access to three tools:
- similarity_search: find visually similar products at a given price point
- budget_optimizer: allocate a budget across an outfit for a specific occasion
- wardrobe_fetcher: retrieve what the user already owns

Rules:
- Always call at least one tool before responding — never answer from memory alone
- Always cite specific products, prices, and platforms in your answer
- Reference the user's wardrobe when relevant — avoid suggesting items they already own
- Keep responses under 150 words
- Respond in a friendly, conversational tone
- Never invent product names, prices, or URLs — only reference tool output
"""


# ---------------------------------------------------------------------------
# Tool registry — functions the agent can call
# These callables are injected by agent_service so this module stays pure
# ---------------------------------------------------------------------------

class ToolRegistry:
    """
    Holds the three callable tools the agent can invoke.

    Each tool is a plain Python callable — no LangChain @tool decorator needed.
    The agent decides which to call based on the LLM's tool-call decision.

    Tools are injected (not hardcoded) so they can be mocked in tests.
    """

    def __init__(
        self,
        similarity_search_fn: Callable[..., Any],
        budget_optimizer_fn: Callable[..., Any],
        wardrobe_fetcher_fn: Callable[..., Any],
    ) -> None:
        self._tools = {
            "similarity_search": similarity_search_fn,
            "budget_optimizer": budget_optimizer_fn,
            "wardrobe_fetcher": wardrobe_fetcher_fn,
        }

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        fn = self._tools.get(tool_name)
        if fn is None:
            raise ValueError(f"Unknown tool: {tool_name!r}")
        logger.info("[shopping_agent] calling tool=%s args=%s", tool_name, tool_args)
        return fn(**tool_args)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())


# ---------------------------------------------------------------------------
# Tool schemas — sent to the LLM so it knows what arguments each tool expects
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "similarity_search",
        "description": (
            "Find visually similar fashion products. "
            "Use this when the user wants to find products similar to something they describe or show, "
            "or wants cheaper alternatives."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_text": {
                    "type": "string",
                    "description": "Natural language description of the product to search for",
                },
                "max_price_inr": {
                    "type": "integer",
                    "description": "Maximum price in INR — optional, omit if no price constraint",
                },
                "category": {
                    "type": "string",
                    "description": (
                        "Fashion category to filter by: tops, bottoms, ethnic, formals, "
                        "outerwear, footwear, accessories, sportswear — optional"
                    ),
                },
            },
            "required": ["query_text"],
        },
    },
    {
        "name": "budget_optimizer",
        "description": (
            "Allocate a total outfit budget across clothing categories for a specific occasion. "
            "Use when the user mentions a budget and wants to know what to spend on each piece."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "total_budget_inr": {
                    "type": "integer",
                    "description": "Total outfit budget in Indian Rupees",
                },
                "occasion": {
                    "type": "string",
                    "description": (
                        "The occasion: wedding, festive, formal, office, casual, party, "
                        "sports, or activewear"
                    ),
                },
            },
            "required": ["total_budget_inr", "occasion"],
        },
    },
    {
        "name": "wardrobe_fetcher",
        "description": (
            "Retrieve what the user already owns in their wardrobe. "
            "Always call this when the user's question involves their existing clothes "
            "or when you want to avoid suggesting items they already have."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The user's UUID",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter: tops, bottoms, ethnic, etc.",
                },
            },
            "required": ["user_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

class AgentState:
    """
    Mutable state threaded through the agent graph nodes.

    Tracks the conversation, tool call history, and accumulated tool outputs.
    """

    def __init__(
        self,
        user_id: str,
        message: str,
        session_messages: list[dict[str, str]],
    ) -> None:
        self.user_id = user_id
        self.message = message
        # Full conversation history including the new user turn
        self.messages: list[dict[str, str]] = list(session_messages) + [
            {"role": "user", "content": message}
        ]
        # Ordered list of tool names called during this turn
        self.tools_called: list[str] = []
        # Raw tool outputs keyed by tool_name
        self.tool_outputs: dict[str, Any] = {}
        # Products that came from tool output — validated before citing
        self.tool_products: list[dict[str, Any]] = []
        # Final reply generated by the response node
        self.reply: Optional[str] = None


# ---------------------------------------------------------------------------
# Agent graph nodes
# ---------------------------------------------------------------------------

def _build_tool_descriptions() -> str:
    """Format TOOL_SCHEMAS into a compact description string for the LLM prompt."""
    lines = []
    for schema in TOOL_SCHEMAS:
        param_names = list(schema["parameters"]["properties"].keys())
        lines.append(f"- {schema['name']}({', '.join(param_names)}): {schema['description']}")
    return "\n".join(lines)


def _format_tool_outputs(state: AgentState) -> str:
    """Format accumulated tool outputs into a readable context block."""
    if not state.tool_outputs:
        return "No tool output available."

    sections: list[str] = []
    for tool_name, output in state.tool_outputs.items():
        sections.append(f"=== {tool_name} output ===")
        if isinstance(output, list):
            for i, item in enumerate(output[:5], 1):  # top 5 items
                sections.append(f"{i}. {json.dumps(item, ensure_ascii=False)}")
        elif isinstance(output, dict):
            sections.append(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            sections.append(str(output))
    return "\n".join(sections)


def _format_conversation(messages: list[dict[str, str]]) -> str:
    """Format conversation history for the LLM prompt."""
    lines: list[str] = []
    for msg in messages[-6:]:  # last 6 turns to avoid token bloat
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def reasoning_node(state: AgentState, llm_client: Any) -> list[dict[str, Any]]:
    """
    Node 1 — Reasoning: Ask the LLM which tools to call, and with what args.

    Returns a list of tool calls: [{"name": str, "args": dict}, ...]
    The agent MUST call at least one tool — the prompt enforces this.
    """
    tool_descriptions = _build_tool_descriptions()
    conversation = _format_conversation(state.messages)

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Available tools:\n{tool_descriptions}\n\n"
        f"Conversation so far:\n{conversation}\n\n"
        f"Current user message: {state.message}\n"
        f"User ID: {state.user_id}\n\n"
        f"Decide which tool(s) to call to answer this query. You MUST call at least one tool.\n"
        f"Respond with a JSON array of tool calls. Each object must have \"name\" and \"args\" keys.\n"
        f"Only use tool names from the list above. Use user_id=\"{state.user_id}\" for wardrobe_fetcher.\n\n"
        f"Example response format:\n"
        f'[{{"name": "similarity_search", "args": {{"query_text": "blue kurta", "max_price_inr": 1500}}}}]\n\n'
        f"Respond with ONLY the JSON array — no explanation, no markdown."
    )

    raw = llm_client.generate(prompt)

    # Extract JSON array from response
    try:
        # Strip markdown code fences if present
        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        tool_calls = json.loads(clean)
        if not isinstance(tool_calls, list):
            tool_calls = [tool_calls]
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "[shopping_agent] reasoning_node failed to parse tool calls: %s — raw=%s",
            exc, raw[:200]
        )
        # Fallback: force a similarity_search with the raw message
        tool_calls = [{"name": "similarity_search", "args": {"query_text": state.message}}]

    logger.info(
        "[shopping_agent] reasoning_node decided tool_calls=%s",
        [tc.get("name") for tc in tool_calls]
    )
    return tool_calls


def tool_execution_node(
    state: AgentState,
    tool_calls: list[dict[str, Any]],
    registry: ToolRegistry,
) -> None:
    """
    Node 2 — Tool Execution: Run each tool call and accumulate outputs in state.

    Mutates state.tool_outputs and state.tools_called.
    Collects product dicts from tool outputs into state.tool_products.
    """
    for call in tool_calls:
        tool_name = call.get("name", "")
        tool_args = call.get("args", {})

        if tool_name not in registry.tool_names:
            logger.warning("[shopping_agent] unknown tool skipped: %r", tool_name)
            continue

        try:
            result = registry.call(tool_name, tool_args)
            state.tool_outputs[tool_name] = result
            state.tools_called.append(tool_name)

            # Collect products for citation validation
            if tool_name == "similarity_search" and isinstance(result, list):
                for item in result:
                    if isinstance(item, dict):
                        state.tool_products.append(item)

        except Exception as exc:
            logger.error(
                "[shopping_agent] tool %r raised exception: %s", tool_name, exc
            )
            state.tool_outputs[tool_name] = {"error": str(exc)}


def response_node(state: AgentState, llm_client: Any) -> str:
    """
    Node 3 — Response: Generate the final cited answer from all tool outputs.

    Spec constraints:
    - Under 150 words
    - Only cite products returned by tools — never hallucinate
    - Reference user's wardrobe when relevant
    """
    tool_context = _format_tool_outputs(state)
    conversation = _format_conversation(state.messages[:-1])  # exclude current turn

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Conversation history:\n{conversation}\n\n"
        f"User's question: {state.message}\n\n"
        f"Tool results (you MUST base your answer ONLY on these results):\n{tool_context}\n\n"
        f"Tools called: {', '.join(state.tools_called)}\n\n"
        f"Write a friendly, helpful response to the user's question.\n"
        f"- Cite specific products, prices (in INR), and platform names from the tool results above.\n"
        f"- Keep response under 150 words.\n"
        f"- If wardrobe data is available, mention whether they already own something similar.\n"
        f"- Never mention tool names (similarity_search, budget_optimizer, wardrobe_fetcher) to the user.\n"
        f"- Never invent product names, prices, or URLs not present in the tool results.\n\n"
        f"Response:"
    )

    reply = llm_client.generate(prompt)
    # Trim to 150 words if LLM overshoots
    words = reply.split()
    if len(words) > 150:
        reply = " ".join(words[:150]) + "..."
        logger.info("[shopping_agent] response trimmed to 150 words")

    return reply.strip()


# ---------------------------------------------------------------------------
# Extract products_cited — validate against tool output (no hallucination)
# ---------------------------------------------------------------------------

def _extract_products_cited(
    reply: str,
    tool_products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build products_cited from tool_products that are mentioned in the reply.

    Only products whose platform or id appears in the reply text are included.
    This prevents hallucinated products from appearing in products_cited.
    If no exact match, cite the top 3 tool products (agent referenced implicitly).
    """
    cited: list[dict[str, Any]] = []
    reply_lower = reply.lower()

    for product in tool_products:
        product_id = str(product.get("product_id", ""))
        platform = str(product.get("platform", ""))

        if platform.lower() in reply_lower or product_id in reply:
            cited.append({
                "name": product.get("name", product_id),
                "price_inr": product.get("price_inr", 0),
                "platform": platform,
                "url": product.get("url", ""),
            })

    # Fallback: cite top 3 if no text match found
    if not cited and tool_products:
        for p in tool_products[:3]:
            cited.append({
                "name": p.get("name", p.get("product_id", "Unknown")),
                "price_inr": p.get("price_inr", 0),
                "platform": p.get("platform", "unknown"),
                "url": p.get("url", ""),
            })

    return cited


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------

class AgentResult:
    """Return value of run_agent()."""

    def __init__(
        self,
        reply: str,
        tools_called: list[str],
        products_cited: list[dict[str, Any]],
        updated_messages: list[dict[str, str]],
    ) -> None:
        self.reply = reply
        self.tools_called = tools_called
        self.products_cited = products_cited
        self.updated_messages = updated_messages


def run_agent(
    *,
    user_id: str,
    message: str,
    session_messages: list[dict[str, str]],
    registry: ToolRegistry,
    llm_client: Any,
) -> AgentResult:
    """
    Run the full LangGraph-style agent for one user turn.

    Args:
        user_id:          UUID of the authenticated user.
        message:          Current user message.
        session_messages: Previous turns in the conversation (role/content dicts).
        registry:         ToolRegistry with the three callable tools.
        llm_client:       LLMClient instance (from integrations/llm_client.py).

    Returns:
        AgentResult with reply, tools_called, products_cited, updated_messages.

    Raises:
        RuntimeError: If the LLM call fails entirely.
    """
    logger.info(
        "[shopping_agent] run_agent start user_id=%s message=%s",
        user_id, message[:80]
    )

    state = AgentState(user_id=user_id, message=message, session_messages=session_messages)

    # Node 1 — Reasoning: decide which tools to call
    tool_calls = reasoning_node(state, llm_client)

    # Node 2 — Tool Execution: run the decided tools
    tool_execution_node(state, tool_calls, registry)

    # Guard: if no tools were called (shouldn't happen but defend against it)
    if not state.tools_called:
        logger.warning(
            "[shopping_agent] no tools were called — forcing similarity_search fallback"
        )
        fallback_calls = [{"name": "similarity_search", "args": {"query_text": message}}]
        tool_execution_node(state, fallback_calls, registry)

    logger.info("[shopping_agent] tools_called=%s", state.tools_called)

    # Node 3 — Response: generate cited answer
    reply = response_node(state, llm_client)

    # Extract products_cited — validated against tool output
    products_cited = _extract_products_cited(reply, state.tool_products)

    # Update session history with this turn
    updated_messages = list(session_messages) + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]

    logger.info(
        "[shopping_agent] run_agent done tools=%s reply_len=%d products_cited=%d",
        state.tools_called, len(reply), len(products_cited)
    )

    return AgentResult(
        reply=reply,
        tools_called=state.tools_called,
        products_cited=products_cited,
        updated_messages=updated_messages,
    )
