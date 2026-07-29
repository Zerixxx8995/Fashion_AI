"""
Trend Scorer — ml-backend.

Responsibility: Pure algorithm layer to compute trend signal scores and determine
the trend lifecycle stage (emerging | peaking | dying).

Layer rules:
  - Pure algorithms and mathematical calculations.
  - No database knowledge, no Celery jobs, no HTTP knowledge.
"""

from __future__ import annotations

import math
from typing import Literal


def calculate_signal_score(
    *,
    appearance_count: int,
    growth_rate: float,
    social_mention_count: int = 0,
    review_volume: int = 0,
) -> float:
    """
    Calculate a normalized trend signal score [0.0 to 10.0] based on volume,
    growth rate, and external social signals.

    Formula combines:
      - Log-scaled volume (appearance count + review volume)
      - Growth rate multiplier
      - Log-scaled social mentions
    """
    if appearance_count <= 0:
        return 0.0

    # Log volume scaling
    volume_score = math.log1p(appearance_count + review_volume)
    
    # Growth multiplier (bound negative growth, scale positive growth)
    # E.g. growth of -0.5 maps to 0.5, growth of 2.0 maps to 3.0
    growth_multiplier = max(0.1, 1.0 + growth_rate)

    # Social component
    social_score = math.log1p(social_mention_count) * 0.5

    # Raw blended score
    blended = (volume_score * growth_multiplier) + social_score

    # Normalize to [0.0, 10.0] using a soft sigmoid-like cap
    # 10 * (x / (5 + x)) maps: 0 -> 0, 5 -> 5, 20 -> 8, infinity -> 10
    normalized = 10.0 * (blended / (5.0 + blended))
    return round(normalized, 2)


def determine_lifecycle_stage(
    *,
    signal_score: float,
    acceleration: float,
) -> Literal["emerging", "peaking", "dying"]:
    """
    Determine trend lifecycle stage based on signal score and acceleration (momentum velocity).

    Logic:
      - emerging: Acceleration is positive (> 0.2) and score is not yet saturated.
      - peaking: High signal score (> 6.0) with slowing velocity/acceleration.
      - dying: Negative acceleration (< -0.1) or very low score (< 2.0).
    """
    if signal_score < 2.0:
        return "dying"

    if acceleration < -0.1:
        return "dying"

    if signal_score >= 6.5 and abs(acceleration) <= 0.3:
        return "peaking"

    if acceleration >= 0.2:
        return "emerging"

    # Default fallback based on absolute score thresholds
    if signal_score >= 5.0:
        return "peaking"
    else:
        return "emerging"
