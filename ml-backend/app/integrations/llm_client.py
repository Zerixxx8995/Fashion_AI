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


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part["text"]))
            elif hasattr(part, "text"):
                parts.append(str(getattr(part, "text")))
        return "".join(parts).strip()
    return str(content).strip()


class LLMClient:
    """
    Thin wrapper around LangChain ChatGoogleGenerativeAI.

    Public methods:
      generate(prompt: str) -> str
        Send a prompt to Gemini Flash and return the text response.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY environment variable is not set. "
                "Add it to ml-backend/.env"
            )

        from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore[import]

        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        self._llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            temperature=0.3,  # spec constraint — never higher for this feature
            google_api_key=self.api_key,
        )
        logger.info("[llm_client] LangChain ChatGoogleGenerativeAI initialised (model=%s, temp=0.3)", self.model_name)

    def generate(self, prompt: str) -> str:
        """
        Send a prompt to Gemini via LangChain and return the text response.

        Args:
            prompt: The full prompt string (constructed by rag_engine.py).

        Returns:
            The model's text output as a plain string.

        Raises:
            RuntimeError: If all LLM model attempts fail or return an empty response.
        """
        from langchain_core.messages import HumanMessage  # type: ignore[import]
        from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore[import]

        logger.debug("[llm_client] sending prompt to Gemini (len=%d)", len(prompt))

        fallback_models = list(dict.fromkeys([
            self.model_name,
            "gemini-3.8-flash",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ]))

        last_exc: Optional[Exception] = None
        for model in fallback_models:
            try:
                if model != self.model_name:
                    logger.info("[llm_client] retrying Gemini call with fallback model: %s", model)
                    llm = ChatGoogleGenerativeAI(
                        model=model,
                        temperature=0.3,
                        google_api_key=self.api_key,
                    )
                else:
                    llm = self._llm

                response = llm.invoke([HumanMessage(content=prompt)])
                text = _extract_text(response.content)
                if text:
                    self._llm = llm
                    self.model_name = model
                    logger.debug("[llm_client] received response using %s (len=%d)", model, len(text))
                    return text
            except Exception as exc:
                last_exc = exc
                logger.warning("[llm_client] Gemini model '%s' call failed: %s", model, exc)

        raise RuntimeError(f"LLM call failed: {last_exc}") from last_exc


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
