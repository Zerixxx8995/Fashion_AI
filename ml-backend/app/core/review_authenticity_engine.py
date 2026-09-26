"""
Review Authenticity Engine — ml-backend/app/core/review_authenticity_engine.py

Responsibility: Pure RAG logic for structured review authenticity explanation.
No HTTP. No business logic. No DB access. No caching.

Layer rules (core):
  - Receives structured context dicts — no raw DB models.
  - Calls integrations/llm_client.py to execute the Gemini call.
  - Returns a validated ReviewAuthenticityExplanation Pydantic model.

Design constraints (from spec):
  - Temperature: 0.1  — analytical task, maximum consistency, never higher.
  - LLM output is parsed against schema. Retry once on failure.
  - Second failure returns Inconclusive fallback — never crash.
  - Never invent details not present in the supplied data.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic output schema — spec-defined, never modified
# ---------------------------------------------------------------------------

VALID_VERDICTS = {"Likely fake", "Possibly fake", "Inconclusive"}


class ReviewAuthenticityExplanation(BaseModel):
    """
    Structured explanation of why a review was flagged as potentially fake.

    All fields are required. overall_verdict must be one of the three
    canonical values defined in VALID_VERDICTS.
    """

    overall_verdict: str = Field(
        ...,
        description='One of: "Likely fake" | "Possibly fake" | "Inconclusive"',
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Maps directly to the stock_match_score from the CV engine.",
    )
    suspicious_phrases: list[str] = Field(
        ...,
        min_length=0,
        description="Specific phrases from the review text that match fake review patterns.",
    )
    image_mismatch_summary: str = Field(
        ...,
        description="One sentence describing the visual mismatch between reviewer and stock image.",
    )
    pattern_matches: list[str] = Field(
        ...,
        min_length=0,
        description="How this review matches patterns seen in historical fake reviews.",
    )
    recommendation: str = Field(
        ...,
        description="One sentence — what the user should do before purchasing.",
    )

    @field_validator("overall_verdict")
    @classmethod
    def verdict_must_be_valid(cls, v: str) -> str:
        if v not in VALID_VERDICTS:
            raise ValueError(
                f"overall_verdict must be one of {VALID_VERDICTS}, got {v!r}"
            )
        return v


# ---------------------------------------------------------------------------
# Inconclusive fallback — returned when both LLM attempts fail
# ---------------------------------------------------------------------------

def _inconclusive_fallback(confidence_score: float) -> ReviewAuthenticityExplanation:
    """Return a safe Inconclusive response when the LLM cannot produce valid output."""
    return ReviewAuthenticityExplanation(
        overall_verdict="Inconclusive",
        confidence_score=round(confidence_score, 4),
        suspicious_phrases=[],
        image_mismatch_summary=(
            "Unable to determine the extent of visual mismatch at this time."
        ),
        pattern_matches=[],
        recommendation=(
            "Exercise caution and check other reviews before purchasing."
        ),
    )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SCHEMA_JSON = json.dumps(
    {
        "overall_verdict": 'one of: "Likely fake" | "Possibly fake" | "Inconclusive"',
        "confidence_score": "float 0.0 to 1.0",
        "suspicious_phrases": ["list", "of", "suspicious", "phrases", "from", "review", "text"],
        "image_mismatch_summary": "one sentence describing visual mismatch",
        "pattern_matches": ["list", "of", "fake", "pattern", "matches"],
        "recommendation": "one sentence — what the user should do",
    },
    indent=2,
)

_PROMPT_TEMPLATE = """\
You are a review authenticity analyst for an Indian fashion e-commerce app.
Based ONLY on the data below, generate a structured explanation of why this
review may be fake. Be specific — reference exact phrases and visual details.
Do not invent details not present in the data.

Current review:
Text: {review_text}
Image match score vs stock photo: {stock_match_score}

Product: {product_name} on {platform}
Stock image URL: {stock_image_url}

Similar historical fake reviews (for pattern matching):
{formatted_historical_reviews}

Return ONLY a valid JSON object matching EXACTLY this schema — no markdown, no extra text:
{schema}
"""

_RETRY_PROMPT_TEMPLATE = """\
You are a review authenticity analyst. Your previous response was not valid JSON.
Return ONLY a JSON object matching EXACTLY this schema — no markdown fences, no explanation:
{schema}

Data to analyse:
Review text: {review_text}
Stock match score: {stock_match_score}
Product: {product_name}
Historical fake patterns found: {pattern_count} similar fake reviews retrieved.

Respond with JSON only.
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_historical_reviews(reviews: list[dict[str, Any]]) -> str:
    """Format historical fake reviews for prompt injection."""
    if not reviews:
        return "No similar historical fake reviews available."
    lines = []
    for i, r in enumerate(reviews, 1):
        text = r.get("reviewer_text", "")
        snippet = (text[:200] + "…") if len(text) > 200 else text
        lines.append(f"{i}. \"{snippet}\"")
    return "\n".join(lines)


def _get_llm_at_temp_01() -> Any:
    """
    Build a Gemini LLM instance at temperature=0.1 for analytical tasks.

    The global singleton from get_llm_client() uses 0.3. Feature 3 requires
    exactly 0.1 (spec constraint). We construct a separate one-shot instance.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY environment variable is not set. Add it to ml-backend/.env"
        )
    from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore[import]

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0.1,
        google_api_key=api_key,
    )


def _call_llm(llm: Any, prompt: str) -> str:
    """Invoke the LLM and return raw text. Raises on failure."""
    from langchain_core.messages import HumanMessage  # type: ignore[import]

    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content
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


def _parse_json_response(raw: str) -> dict[str, Any]:
    """
    Parse LLM response text as JSON, stripping markdown fences if present.

    Raises:
        json.JSONDecodeError: If the text is not valid JSON after stripping.
    """
    text = raw.strip()
    # Strip markdown code fences if the LLM wrapped the JSON
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop the opening fence line and the closing fence line
        inner = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                continue
            inner.append(line)
        text = "\n".join(inner).strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_review_explanation(
    *,
    review_text: str,
    stock_match_score: float,
    product_name: str,
    platform: str,
    stock_image_url: str,
    historical_fake_reviews: list[dict[str, Any]],
) -> ReviewAuthenticityExplanation:
    """
    Generate a structured explanation of why a review appears fake.

    Calls Gemini at temperature=0.1 with review text, stock match score,
    and top-5 historically similar fake reviews from Pinecone. Parses the
    response against the ReviewAuthenticityExplanation schema.

    Retry logic:
      - Attempt 1: full context prompt.
      - Attempt 2 (on parse failure): stricter, JSON-only prompt.
      - Both fail: return Inconclusive fallback with raw confidence_score.

    Args:
        review_text:              Full text of the flagged review.
        stock_match_score:        Float 0–1 from the existing CV engine.
        product_name:             Name of the product being reviewed.
        platform:                 Platform name (e.g. "myntra").
        stock_image_url:          First stock image URL for the product.
        historical_fake_reviews:  List of reviewer_text dicts from similar
                                  flagged reviews fetched from Pinecone+DB.

    Returns:
        ReviewAuthenticityExplanation — validated Pydantic model.
    """
    logger.info(
        "[review_authenticity_engine] generate_review_explanation "
        "product=%s score=%.3f historical_count=%d",
        product_name, stock_match_score, len(historical_fake_reviews),
    )

    llm = _get_llm_at_temp_01()
    formatted_history = _format_historical_reviews(historical_fake_reviews)

    # ── Attempt 1: full context prompt ──────────────────────────────────────
    prompt1 = _PROMPT_TEMPLATE.format(
        review_text=review_text,
        stock_match_score=round(stock_match_score, 4),
        product_name=product_name,
        platform=platform,
        stock_image_url=stock_image_url,
        formatted_historical_reviews=formatted_history,
        schema=_SCHEMA_JSON,
    )

    try:
        raw1 = _call_llm(llm, prompt1)
        data1 = _parse_json_response(raw1)
        # Override confidence_score with the authoritative CV engine value
        data1["confidence_score"] = round(stock_match_score, 4)
        result = ReviewAuthenticityExplanation(**data1)
        logger.info(
            "[review_authenticity_engine] attempt 1 succeeded verdict=%s",
            result.overall_verdict,
        )
        return result
    except Exception as exc:
        logger.warning(
            "[review_authenticity_engine] attempt 1 failed: %s — retrying", exc
        )

    # ── Attempt 2: stricter JSON-only prompt ─────────────────────────────────
    prompt2 = _RETRY_PROMPT_TEMPLATE.format(
        schema=_SCHEMA_JSON,
        review_text=review_text[:500],  # truncate to reduce confusion
        stock_match_score=round(stock_match_score, 4),
        product_name=product_name,
        pattern_count=len(historical_fake_reviews),
    )

    try:
        raw2 = _call_llm(llm, prompt2)
        data2 = _parse_json_response(raw2)
        data2["confidence_score"] = round(stock_match_score, 4)
        result = ReviewAuthenticityExplanation(**data2)
        logger.info(
            "[review_authenticity_engine] attempt 2 succeeded verdict=%s",
            result.overall_verdict,
        )
        return result
    except Exception as exc2:
        logger.error(
            "[review_authenticity_engine] attempt 2 failed: %s — returning Inconclusive fallback",
            exc2,
        )

    # ── Fallback: both attempts failed ───────────────────────────────────────
    return _inconclusive_fallback(stock_match_score)
