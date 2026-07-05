"""Points / combo / streak scoring. Port of src/lib/points.ts.

Task 2: Formulas de points with revision modes support.
"""

from __future__ import annotations

import math


def compute_points(is_correct: bool, difficulty: int, speed: str, combo: int) -> dict:
    """Compute points for a standard revision answer (no streak multiplier).

    Args:
        is_correct: Whether the answer was correct
        difficulty: Question difficulty (1, 2, or 3)
        speed: Speed classification ("fast", "medium", or "slow")
        combo: Current combo count (1+)

    Returns:
        Dictionary with breakdown and total points.
    """
    if not is_correct:
        return {
            "base": 0,
            "difficultyBonus": 0,
            "speedBonus": 0,
            "comboMultiplier": 1,
            "total": 0,
        }

    base = 10
    difficulty_bonus = 2 if difficulty == 1 else 4 if difficulty == 2 else 6
    speed_bonus = 5 if speed == "fast" else 2 if speed == "medium" else 0

    combo_multiplier = 1.0
    if combo >= 5:
        combo_multiplier = 1.5
    elif combo == 4:
        combo_multiplier = 1.3
    elif combo == 3:
        combo_multiplier = 1.2
    elif combo == 2:
        combo_multiplier = 1.1

    raw = (base + difficulty_bonus + speed_bonus) * combo_multiplier
    return {
        "base": base,
        "difficultyBonus": difficulty_bonus,
        "speedBonus": speed_bonus,
        "comboMultiplier": combo_multiplier,
        "total": round(raw),
    }


def compute_daily_points(day_number: int) -> float:
    """Compute bonus points for daily revision mode (logarithmic scale, capped at 30).

    Args:
        day_number: Day number in the streak (0-indexed)

    Returns:
        Points value, capped at 30. Uses logarithmic formula for diminishing returns.
    """
    if day_number <= 0:
        return 0.0
    # Logarithmic formula: cap is 30
    # Formula: 30 * (1 - e^(-ln(2) * day_number / k))
    # where k controls the decay rate. Using k=5 for reasonable growth.
    points = 30.0 * (1.0 - math.exp(-math.log(2) * day_number / 5.0))
    return min(30.0, points)


def compute_stability_points(retrievability: float) -> float:
    """Compute bonus points based on FSRS retrievability (capped at 8).

    Args:
        retrievability: FSRS retrievability value (0.0 to 1.0)

    Returns:
        Points value, capped at 8. Linearly scales with retrievability.
    """
    if retrievability < 0.0 or retrievability > 1.0:
        raise ValueError("retrievability must be in range [0.0, 1.0]")
    # Linear formula: 8 * retrievability
    points = 8.0 * retrievability
    return min(8.0, max(0.0, points))


def combo_label(combo: int) -> str | None:
    if combo < 2:
        return None
    if combo >= 5:
        return f"🔥 ×{combo} ומעלה!"
    return f"🔥 ×{combo}"
