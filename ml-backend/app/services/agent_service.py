"""
Agent Service — ml-backend/app/services/agent_service.py

Responsibility: Orchestrate the shopping agent for one user turn.
- Fetches user profile from PostgreSQL for context.
- Builds ToolRegistry with the three wired-in service functions.
- Calls shopping_agent.run_agent().
- Returns the shaped response dict.

Layer rules (service):
  - Knows about DB models (SQLAlchemy).
  - Knows about integrations (llm_client via shopping_agent).
  - Does NOT contain HTTP knowledge (lives in routers/controllers).
  - Does NOT contain raw LLM/prompt logic (lives in core/shopping_agent).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.shopping_agent import ToolRegistry, run_agent
from app.db.models.user import User
from app.db.models.wardrobe_item import WardrobeItem
from app.integrations.llm_client import get_llm_client
from app.services.similarity_service import find_similar_products
from app.services.budget_service import optimize_budget
from app.models.budget_models import BudgetOptimizeRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Wardrobe fetcher — DB-aware, injected into ToolRegistry
# ---------------------------------------------------------------------------

def _make_wardrobe_fetcher(db: Session):
    """
    Factory that returns a wardrobe_fetcher callable closed over the DB session.

    The returned function accepts user_id and optional category, returns a list
    of wardrobe item dicts the agent can include in its context.
    """
    def wardrobe_fetcher(*, user_id: str, category: Optional[str] = None) -> list[dict[str, Any]]:
        logger.info(
            "[agent_service] wardrobe_fetcher user_id=%s category=%s", user_id, category
        )
        stmt = (
            select(WardrobeItem)
            .where((WardrobeItem.user_id == user_id))
        )
        if category:
            stmt = stmt.where(WardrobeItem.category == category)
        stmt = stmt.limit(20)

        items = list(db.scalars(stmt).all())
        return [
            {
                "name": item.name,
                "category": item.category or "clothing",
                "color": item.color or "unknown",
                "item_id": str(item.id),
            }
            for item in items
        ]

    return wardrobe_fetcher


# ---------------------------------------------------------------------------
# Budget optimizer adapter — wraps budget_service for the agent
# ---------------------------------------------------------------------------

def _budget_optimizer_adapter(*, total_budget_inr: int, occasion: str) -> dict[str, Any]:
    """
    Adapter that wraps budget_service.optimize_budget() for the agent tool interface.

    Converts BudgetOptimizeResponse to a plain dict the agent can read.
    Falls back to casual if occasion is invalid.
    """
    valid_occasions = {
        "wedding", "festive", "formal", "office",
        "casual", "party", "sports", "activewear"
    }
    safe_occasion = occasion.strip().lower() if occasion.strip().lower() in valid_occasions else "casual"

    request = BudgetOptimizeRequest(budget_inr=total_budget_inr, occasion=safe_occasion)
    response = optimize_budget(request)

    return {
        "total_budget_inr": response.total_budget_inr,
        "occasion": response.occasion,
        "allocations": [
            {
                "category": item.category,
                "allocated_amount_inr": item.allocated_amount_inr,
                "percentage": item.percentage,
                "description": item.description,
            }
            for item in response.allocations
        ],
        "tips": response.tips,
    }


# ---------------------------------------------------------------------------
# Similarity search adapter — wraps similarity_service for the agent
# ---------------------------------------------------------------------------

def _similarity_search_adapter(
    *,
    query_text: str,
    max_price_inr: Optional[int] = None,
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Adapter wrapping similarity_service.find_similar_products() for the agent.
    """
    return find_similar_products(
        text_query=query_text,
        limit=5,
        max_price_inr=max_price_inr,
        category=category,
    )


# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------

def run_agent_turn(
    db: Session,
    *,
    user_id: str,
    message: str,
    session_messages: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Run one agent conversation turn and return the shaped response dict.

    Args:
        db:               SQLAlchemy session.
        user_id:          UUID (or clerk_id) of the authenticated user.
        message:          Current user message text.
        session_messages: Previous turns in the conversation (role/content dicts).

    Returns:
        Dict matching the spec API response shape:
        {
            "reply": str,
            "tools_called": list[str],
            "products_cited": list[dict],
            "session_messages": list[dict],
        }

    Raises:
        KeyError: If user_id is not found in the database.
        RuntimeError: If the LLM call fails.
    """
    logger.info(
        "[agent_service] run_agent_turn user_id=%s message_len=%d",
        user_id, len(message)
    )

    # 1. Resolve user to internal UUID (accepts both internal UUID and clerk_id)
    user = db.scalar(
        select(User).where(
            (User.id == user_id) | (User.clerk_id == user_id)
        )
    )
    if user is not None:
        internal_user_id = str(user.id)
    else:
        # Fallback for guest or un-synced dev users
        first_user = db.scalar(select(User))
        internal_user_id = str(first_user.id) if first_user else user_id

    # 2. Build ToolRegistry with injected callables
    registry = ToolRegistry(
        similarity_search_fn=_similarity_search_adapter,
        budget_optimizer_fn=_budget_optimizer_adapter,
        wardrobe_fetcher_fn=_make_wardrobe_fetcher(db),
    )

    # 3. Get LLM client
    llm_client = get_llm_client()

    # 4. Run the agent
    result = run_agent(
        user_id=internal_user_id,
        message=message,
        session_messages=session_messages,
        registry=registry,
        llm_client=llm_client,
    )

    logger.info(
        "[agent_service] agent turn complete tools=%s products=%d",
        result.tools_called, len(result.products_cited)
    )

    return {
        "reply": result.reply,
        "tools_called": result.tools_called,
        "products_cited": result.products_cited,
        "session_messages": result.updated_messages,
    }
