"""Tests for the points scoring system with revision modes.

pytest-compatible, but also runnable standalone (no pytest required):

    python tests/test_points.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from points import (  # noqa: E402
    compute_daily_points,
    compute_points,
    compute_stability_points,
)


def test_compute_points_correct():
    """Correct answer with base stats."""
    result = compute_points(is_correct=True, difficulty=2, speed="medium", combo=1)
    assert result["base"] == 10
    assert result["difficultyBonus"] == 4
    assert result["speedBonus"] == 2
    assert result["comboMultiplier"] == 1.0
    assert result["total"] == round(10 + 4 + 2)


def test_compute_points_incorrect():
    """Incorrect answer yields 0 points."""
    result = compute_points(is_correct=False, difficulty=2, speed="medium", combo=1)
    assert result["base"] == 0
    assert result["difficultyBonus"] == 0
    assert result["speedBonus"] == 0
    assert result["comboMultiplier"] == 1
    assert result["total"] == 0


def test_compute_points_difficulty_levels():
    """Difficulty bonuses: 1 -> +2, 2 -> +4, 3 -> +6."""
    r1 = compute_points(is_correct=True, difficulty=1, speed="fast", combo=1)
    r2 = compute_points(is_correct=True, difficulty=2, speed="fast", combo=1)
    r3 = compute_points(is_correct=True, difficulty=3, speed="fast", combo=1)
    assert r1["difficultyBonus"] == 2
    assert r2["difficultyBonus"] == 4
    assert r3["difficultyBonus"] == 6


def test_compute_points_speed_bonuses():
    """Speed bonuses: fast -> +5, medium -> +2, slow -> 0."""
    rf = compute_points(is_correct=True, difficulty=1, speed="fast", combo=1)
    rm = compute_points(is_correct=True, difficulty=1, speed="medium", combo=1)
    rs = compute_points(is_correct=True, difficulty=1, speed="slow", combo=1)
    assert rf["speedBonus"] == 5
    assert rm["speedBonus"] == 2
    assert rs["speedBonus"] == 0


def test_compute_points_combo_multipliers():
    """Combo multipliers: 2 -> ×1.1, 3 -> ×1.2, 4 -> ×1.3, 5+ -> ×1.5."""
    r2 = compute_points(is_correct=True, difficulty=1, speed="fast", combo=2)
    r3 = compute_points(is_correct=True, difficulty=1, speed="fast", combo=3)
    r4 = compute_points(is_correct=True, difficulty=1, speed="fast", combo=4)
    r5 = compute_points(is_correct=True, difficulty=1, speed="fast", combo=5)
    r10 = compute_points(is_correct=True, difficulty=1, speed="fast", combo=10)
    assert r2["comboMultiplier"] == 1.1
    assert r3["comboMultiplier"] == 1.2
    assert r4["comboMultiplier"] == 1.3
    assert r5["comboMultiplier"] == 1.5
    assert r10["comboMultiplier"] == 1.5


def test_compute_daily_points_cap():
    """Daily points capped at 30."""
    result_0 = compute_daily_points(day_number=0)
    result_1 = compute_daily_points(day_number=1)
    result_30 = compute_daily_points(day_number=30)
    result_100 = compute_daily_points(day_number=100)
    result_1000 = compute_daily_points(day_number=1000)

    assert result_0 >= 0
    assert result_1 >= result_0
    assert result_30 <= 30
    assert result_100 <= 30
    assert result_1000 <= 30


def test_compute_daily_points_monotonic():
    """Daily points are monotonically increasing."""
    points = [compute_daily_points(day_number=i) for i in range(50)]
    for i in range(len(points) - 1):
        assert points[i] <= points[i + 1]


def test_compute_daily_points_logarithmic_growth():
    """Daily points grow logarithmically (smaller increments over time)."""
    p1 = compute_daily_points(day_number=1)
    p2 = compute_daily_points(day_number=2)
    p10 = compute_daily_points(day_number=10)
    p11 = compute_daily_points(day_number=11)
    p100 = compute_daily_points(day_number=100)
    p101 = compute_daily_points(day_number=101)

    # Early increments larger than late increments
    early_increment = p2 - p1
    mid_increment = p11 - p10
    late_increment = p101 - p100

    assert early_increment > mid_increment
    assert mid_increment > late_increment


def test_compute_stability_points_cap():
    """Stability points capped at 8."""
    result_0 = compute_stability_points(retrievability=0.0)
    result_05 = compute_stability_points(retrievability=0.5)
    result_095 = compute_stability_points(retrievability=0.95)
    result_1 = compute_stability_points(retrievability=1.0)

    assert result_0 <= 8
    assert result_05 <= 8
    assert result_095 <= 8
    assert result_1 <= 8
    assert result_1 >= result_0


def test_compute_stability_points_based_on_retrievability():
    """Stability points increase with retrievability."""
    points = [compute_stability_points(retrievability=r / 10) for r in range(11)]
    for i in range(len(points) - 1):
        assert points[i] <= points[i + 1], f"points[{i}]={points[i]} > points[{i+1}]={points[i+1]}"


def test_compute_stability_points_low_retrievability():
    """Low retrievability yields low points."""
    result = compute_stability_points(retrievability=0.1)
    assert result < 2


def test_compute_stability_points_high_retrievability():
    """High retrievability yields higher points."""
    result_low = compute_stability_points(retrievability=0.5)
    result_high = compute_stability_points(retrievability=0.95)
    assert result_high > result_low


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
