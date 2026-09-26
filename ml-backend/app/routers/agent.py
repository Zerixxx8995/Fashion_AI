"""
Agent Router — ml-backend/app/routers/agent.py

Responsibility: Map URLs and HTTP methods for the conversational shopping agent.

Layer rules (router):
  - Declares routes with @router.post
  - Injects DB session via FastAPI Depends(get_db)
  - Passes params to agent_controller
  - NEVER contains business logic, database queries, or algorithms

Endpoints:
  POST /agent/chat — Feature 2 conversational shopping agent
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.controllers import agent_controller
from app.db.database import get_db

router = APIRouter(prefix="/agent", tags=["Shopping Agent"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SessionMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class AgentChatRequest(BaseModel):
    user_id: str
    message: str
    session_messages: list[SessionMessage] = []

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("message must not be empty")
        return v.strip()

    @field_validator("user_id")
    @classmethod
    def user_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("user_id must not be empty")
        return v.strip()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/chat",
    status_code=status.HTTP_200_OK,
    summary="Send a message to the conversational shopping assistant",
    response_description=(
        "Agent reply with tools called, products cited, and updated session history"
    ),
)
def agent_chat(
    body: AgentChatRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Run one turn of the LangGraph conversational shopping agent.

    The agent reasons over the user's query, calls one or more backend tools
    (similarity search, budget optimizer, wardrobe fetcher), and returns a
    cited, reasoned answer.

    Session history is maintained by the mobile app — send the full
    session_messages array with each request. The response includes an updated
    session_messages array including the current turn.

    The agent ALWAYS calls at least one tool before responding — it never
    answers from memory alone. products_cited only contains items actually
    returned by tools — never hallucinated.
    """
    return agent_controller.handle_agent_chat(
        db,
        user_id=body.user_id,
        message=body.message,
        session_messages=[m.model_dump() for m in body.session_messages],
    )
