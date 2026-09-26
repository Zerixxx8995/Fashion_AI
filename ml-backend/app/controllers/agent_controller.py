"""
Agent Controller — ml-backend/app/controllers/agent_controller.py

Responsibility: Parse HTTP request body, validate user_id exists,
call agent_service, shape errors into HTTPExceptions.

Layer rules (controller):
  - Receives parsed params from the router.
  - Calls app/services/agent_service.py.
  - Shapes errors into HTTPExceptions.
  - Does NOT contain business logic.
  - Does NOT contain HTTP routing declarations.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.services import agent_service

logger = logging.getLogger(__name__)


def handle_agent_chat(
    db: Session,
    *,
    user_id: str,
    message: str,
    session_messages: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Handle POST /agent/chat.

    Args:
        db:               SQLAlchemy session (injected by router via Depends).
        user_id:          User UUID or Clerk ID from request body.
        message:          Current user message — must be non-empty.
        session_messages: Previous turns from the mobile app state.

    Returns:
        Response dict matching the spec shape.

    Raises:
        HTTPException 422: If message is empty.
        HTTPException 404: If user_id is not found.
        HTTPException 500: If the agent or LLM call fails.
    """
    logger.info(
        "[agent_controller] handle_agent_chat user_id=%s", user_id
    )

    # Validate message is non-empty (422 per spec)
    if not message or not message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="message must be a non-empty string",
        )

    try:
        result = agent_service.run_agent_turn(
            db,
            user_id=user_id,
            message=message.strip(),
            session_messages=session_messages,
        )
    except KeyError as exc:
        logger.warning("[agent_controller] user not found: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id={user_id!r} not found",
        )
    except Exception as exc:
        logger.error("[agent_controller] agent turn failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent failed: {exc}",
        )

    return result
