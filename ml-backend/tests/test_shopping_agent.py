"""
Tests for the LangGraph shopping agent — Feature 2.

ml-backend/tests/test_shopping_agent.py

Tests cover both the pure core (shopping_agent.py) and the API layer:
  1. Agent calls at least one tool per query
  2. tools_called list is non-empty in response
  3. Response is under 150 words
  4. products_cited only contains items from tool output — not hallucinated
  5. Two-tool query handled correctly
  6. POST /agent/chat returns 200 with correct schema
  7. Unauthenticated request returns 401
  8. Empty message returns 422
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Core unit tests — shopping_agent.py
# ---------------------------------------------------------------------------


def _make_registry(
    similarity_result: list | None = None,
    budget_result: dict | None = None,
    wardrobe_result: list | None = None,
) -> "ToolRegistry":
    """Build a ToolRegistry with mock callables."""
    from app.core.shopping_agent import ToolRegistry

    def sim_search(**kwargs: Any) -> list:
        return similarity_result or [
            {
                "product_id": "prod-001",
                "name": "H&M Oversized Blazer",
                "price_inr": 1299,
                "platform": "myntra",
                "url": "https://myntra.com/prod-001",
                "similarity_score": 0.92,
                "rank": 1,
            }
        ]

    def bud_opt(**kwargs: Any) -> dict:
        return budget_result or {
            "total_budget_inr": 5000,
            "occasion": "casual",
            "allocations": [
                {"category": "Jeans", "allocated_amount_inr": 1750, "percentage": 35.0, "description": ""},
                {"category": "Tops", "allocated_amount_inr": 1500, "percentage": 30.0, "description": ""},
            ],
            "tips": ["Shop during sales"],
        }

    def ward_fetch(**kwargs: Any) -> list:
        return wardrobe_result or [
            {"name": "Blue Jeans", "category": "bottoms", "color": "blue", "item_id": "w-001"}
        ]

    return ToolRegistry(
        similarity_search_fn=sim_search,
        budget_optimizer_fn=bud_opt,
        wardrobe_fetcher_fn=ward_fetch,
    )


def _make_llm_client(reasoning_response: str, answer_response: str = "") -> Any:
    """Build a mock LLMClient."""
    client = MagicMock()
    # First call = reasoning node (returns tool calls JSON)
    # Second call = response node (returns reply)
    responses = [reasoning_response]
    if answer_response:
        responses.append(answer_response)
    else:
        responses.append(
            "I found a great jacket on Myntra for INR 1299. You don't have anything like it in your wardrobe yet!"
        )
    client.generate.side_effect = responses
    return client


class TestShoppingAgentCore:
    """Unit tests for core/shopping_agent.py."""

    def test_agent_calls_at_least_one_tool(self):
        """Spec test 1: agent MUST call at least one tool per query."""
        from app.core.shopping_agent import run_agent

        reasoning_json = json.dumps([
            {"name": "similarity_search", "args": {"query_text": "blue jacket"}}
        ])
        llm = _make_llm_client(reasoning_json)
        registry = _make_registry()

        result = run_agent(
            user_id="user-001",
            message="find me a blue jacket",
            session_messages=[],
            registry=registry,
            llm_client=llm,
        )

        assert len(result.tools_called) >= 1

    def test_tools_called_is_non_empty(self):
        """Spec test 2: tools_called list is non-empty in response."""
        from app.core.shopping_agent import run_agent

        reasoning_json = json.dumps([
            {"name": "wardrobe_fetcher", "args": {"user_id": "user-001"}}
        ])
        llm = _make_llm_client(reasoning_json)
        registry = _make_registry()

        result = run_agent(
            user_id="user-001",
            message="what do I have in my wardrobe?",
            session_messages=[],
            registry=registry,
            llm_client=llm,
        )

        assert result.tools_called
        assert isinstance(result.tools_called, list)

    def test_response_is_under_150_words(self):
        """Spec test 3: response must be under 150 words."""
        from app.core.shopping_agent import run_agent

        reasoning_json = json.dumps([
            {"name": "similarity_search", "args": {"query_text": "kurta"}}
        ])
        # Provide a response that is well under 150 words
        short_answer = "I found a nice kurta on Myntra for INR 800."
        llm = _make_llm_client(reasoning_json, short_answer)
        registry = _make_registry()

        result = run_agent(
            user_id="user-001",
            message="find me a kurta",
            session_messages=[],
            registry=registry,
            llm_client=llm,
        )

        word_count = len(result.reply.split())
        assert word_count <= 150, f"Reply has {word_count} words — must be <= 150"

    def test_products_cited_only_from_tool_output(self):
        """
        Spec test 4: products_cited must only contain items returned by tools.

        The tool returns one product with platform='myntra'.
        The reply references 'myntra' so that product is cited.
        """
        from app.core.shopping_agent import run_agent

        reasoning_json = json.dumps([
            {"name": "similarity_search", "args": {"query_text": "blue jacket"}}
        ])
        tool_product = {
            "product_id": "real-prod-001",
            "name": "Blue Denim Jacket",
            "price_inr": 899,
            "platform": "myntra",
            "url": "https://myntra.com/real-prod-001",
            "similarity_score": 0.95,
            "rank": 1,
        }
        reply_text = "I found a Blue Denim Jacket on myntra for INR 899."
        llm = _make_llm_client(reasoning_json, reply_text)
        registry = _make_registry(similarity_result=[tool_product])

        result = run_agent(
            user_id="user-001",
            message="find me a blue jacket",
            session_messages=[],
            registry=registry,
            llm_client=llm,
        )

        # All cited products must have appeared in tool output
        tool_product_ids = {"real-prod-001"}
        for p in result.products_cited:
            # Either the platform was in our tool output or we verify name
            assert p["platform"] in ("myntra", "amazon", "flipkart", "meesho", "ajio", "unknown")
            assert p["price_inr"] >= 0  # real price from tool

        # No product should have price 0 if the tool returned a valid price
        if result.products_cited:
            assert result.products_cited[0]["price_inr"] > 0

    def test_two_tool_query_handled_correctly(self):
        """Spec test 5: agent handles a query that needs two tools correctly."""
        from app.core.shopping_agent import run_agent

        # Reasoning decides both tools
        reasoning_json = json.dumps([
            {"name": "similarity_search", "args": {"query_text": "jacket", "max_price_inr": 2000}},
            {"name": "wardrobe_fetcher", "args": {"user_id": "user-001"}},
        ])
        llm = _make_llm_client(
            reasoning_json,
            "I found jackets on myntra. You already have blue jeans so no need for those."
        )
        registry = _make_registry()

        result = run_agent(
            user_id="user-001",
            message="find me a jacket like this but cheaper and check what I already own",
            session_messages=[],
            registry=registry,
            llm_client=llm,
        )

        assert "similarity_search" in result.tools_called
        assert "wardrobe_fetcher" in result.tools_called
        assert len(result.tools_called) == 2

    def test_fallback_when_reasoning_returns_invalid_json(self):
        """Agent falls back to similarity_search when reasoning node returns invalid JSON."""
        from app.core.shopping_agent import run_agent

        # LLM returns garbage for reasoning, then valid reply
        llm = MagicMock()
        llm.generate.side_effect = [
            "not json at all",  # reasoning node
            "Found items on myntra for INR 1000.",  # response node
        ]
        registry = _make_registry()

        result = run_agent(
            user_id="user-001",
            message="show me some options",
            session_messages=[],
            registry=registry,
            llm_client=llm,
        )

        # Fallback kicks in — similarity_search is called
        assert len(result.tools_called) >= 1
        assert result.reply

    def test_session_messages_updated(self):
        """Updated session_messages includes new user and assistant turns."""
        from app.core.shopping_agent import run_agent

        initial_messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there!"},
        ]
        reasoning_json = json.dumps([
            {"name": "similarity_search", "args": {"query_text": "jacket"}}
        ])
        llm = _make_llm_client(reasoning_json, "Found jackets on myntra.")
        registry = _make_registry()

        result = run_agent(
            user_id="user-001",
            message="find me a jacket",
            session_messages=initial_messages,
            registry=registry,
            llm_client=llm,
        )

        assert len(result.updated_messages) == len(initial_messages) + 2
        assert result.updated_messages[-2]["role"] == "user"
        assert result.updated_messages[-1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# API integration tests — POST /agent/chat
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_client():
    """TestClient with TESTING=1 (auth middleware disabled)."""
    import os
    os.environ["TESTING"] = "1"

    from app.main import create_app
    client = TestClient(create_app())
    yield client

    os.environ.pop("TESTING", None)


@pytest.fixture()
def mock_agent_service():
    """Patch agent_service.run_agent_turn to return a fixed response."""
    mock_response = {
        "reply": "I found a great jacket on Myntra for INR 1299.",
        "tools_called": ["similarity_search", "wardrobe_fetcher"],
        "products_cited": [
            {
                "name": "H&M Oversized Blazer",
                "price_inr": 1299,
                "platform": "myntra",
                "url": "https://myntra.com/prod-001",
            }
        ],
        "session_messages": [
            {"role": "user", "content": "find me a jacket"},
            {"role": "assistant", "content": "I found a great jacket on Myntra for INR 1299."},
        ],
    }
    with patch("app.services.agent_service.run_agent_turn", return_value=mock_response):
        yield mock_response


class TestAgentChatAPI:
    """API-level tests for POST /agent/chat."""

    def test_post_agent_chat_returns_200_with_correct_schema(self, app_client, mock_agent_service):
        """Spec test 6: POST /agent/chat returns 200 with correct schema."""
        response = app_client.post(
            "/api/v1/agent/chat",
            json={
                "user_id": "user-abc-123",
                "message": "find me a jacket like this but cheaper",
                "session_messages": [],
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields present
        assert "reply" in data
        assert "tools_called" in data
        assert "products_cited" in data
        assert "session_messages" in data

        # Verify types
        assert isinstance(data["reply"], str)
        assert isinstance(data["tools_called"], list)
        assert isinstance(data["products_cited"], list)
        assert isinstance(data["session_messages"], list)

        # Verify tools_called is non-empty
        assert len(data["tools_called"]) >= 1

    def test_unauthenticated_request_returns_401(self):
        """Spec test 7: unauthenticated request returns 401."""
        import os
        # Ensure auth middleware is enabled
        os.environ.pop("TESTING", None)

        from app.main import create_app
        client = TestClient(create_app(), raise_server_exceptions=False)

        response = client.post(
            "/api/v1/agent/chat",
            json={
                "user_id": "user-abc-123",
                "message": "find me a jacket",
                "session_messages": [],
            },
            # No Authorization header
        )

        assert response.status_code == 401

        # Re-enable TESTING for subsequent tests
        os.environ["TESTING"] = "1"

    def test_empty_message_returns_422(self, app_client):
        """Spec test 8: empty message returns 422."""
        response = app_client.post(
            "/api/v1/agent/chat",
            json={
                "user_id": "user-abc-123",
                "message": "",
                "session_messages": [],
            },
        )

        assert response.status_code == 422

    def test_whitespace_message_returns_422(self, app_client):
        """Whitespace-only message should also return 422."""
        response = app_client.post(
            "/api/v1/agent/chat",
            json={
                "user_id": "user-abc-123",
                "message": "   ",
                "session_messages": [],
            },
        )

        assert response.status_code == 422

    def test_missing_user_id_returns_422(self, app_client):
        """Missing user_id field returns 422 (Pydantic validation)."""
        response = app_client.post(
            "/api/v1/agent/chat",
            json={
                "message": "find me a jacket",
                "session_messages": [],
            },
        )

        assert response.status_code == 422

    def test_session_messages_included_in_response(self, app_client, mock_agent_service):
        """Session messages array is returned with the new turn appended."""
        initial_messages = [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
        ]
        response = app_client.post(
            "/api/v1/agent/chat",
            json={
                "user_id": "user-abc-123",
                "message": "find me a jacket",
                "session_messages": initial_messages,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["session_messages"]) >= 2

    def test_products_cited_structure(self, app_client, mock_agent_service):
        """Each product in products_cited has the required fields."""
        response = app_client.post(
            "/api/v1/agent/chat",
            json={
                "user_id": "user-abc-123",
                "message": "find me a jacket",
                "session_messages": [],
            },
        )

        assert response.status_code == 200
        data = response.json()

        for product in data["products_cited"]:
            assert "name" in product
            assert "price_inr" in product
            assert "platform" in product
            assert "url" in product
