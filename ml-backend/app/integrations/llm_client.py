"""
LLM Client Integration — ml-backend/app/integrations/llm_client.py

Responsibility: LangChain + Gemini client — isolated here only.
No business logic. Just client initialisation and a single generate() method.

Layer rules (integrations):
  - All external LLM API calls live here.
  - No HTTP routing knowledge.
  - No business logic or prompt construction.

Environment variables required:
  GOOGLE_API_KEY — Google Generative AI API key

Configuration (from spec):
  - Model: gemini-1.5-flash
  - Temperature: 0.3 — factual and consistent, never higher for this feature
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singleton — avoids importing heavy google-generativeai at module load
# ---------------------------------------------------------------------------

_llm_client: Optional["LLMClient"] = None


class LLMClient:
    """
    Thin wrapper around LangChain ChatGoogleGenerativeAI.

    Public methods:
      generate(prompt: str) -> str
        Send a prompt to Gemini 1.5 Flash and return the text response.
    """

    def __init__(self) -> None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY environment variable is not set. "
                "Add it to ml-backend/.env"
            )

        from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore[import]

        self._llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.3,  # spec constraint — never higher for this feature
            google_api_key=api_key,
        )
        logger.info("[llm_client] LangChain ChatGoogleGenerativeAI initialised (model=gemini-1.5-flash, temp=0.3)")

    def generate(self, prompt: str) -> str:
        """
        Send a prompt to Gemini 1.5 Flash via LangChain and return the text response.

        Args:
            prompt: The full prompt string (constructed by rag_engine.py).

        Returns:
            The model's text output as a plain string.

        Raises:
            RuntimeError: If the LLM call fails or returns an empty response.
        """
        from langchain_core.messages import HumanMessage  # type: ignore[import]

        logger.debug("[llm_client] sending prompt to Gemini (len=%d)", len(prompt))

        try:
            response = self._llm.invoke([HumanMessage(content=prompt)])
            text = response.content.strip()
        except Exception as exc:
            logger.error("[llm_client] Gemini call failed: %s", exc)
            raise RuntimeError(f"LLM call failed: {exc}") from exc

        if not text:
            raise RuntimeError("LLM returned an empty response")

        logger.debug("[llm_client] received response (len=%d)", len(text))
        return text


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def get_llm_client() -> LLMClient:
    """
    Return the singleton LLMClient, initialising it on first call.
    Thread-safe for read access in production (single-process FastAPI).
    """
    global _llm_client  # noqa: PLW0603
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
