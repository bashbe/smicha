"""Tests for points.py scoring formulas.

pytest-compatible, but also runnable standalone (no pytest required):

    python tests/test_points.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from points import compute_points, compute_daily_points, compute_stability_points  # noqa: E402


def test_compute_points_wrong_answer_is_zero():
    b = compute_points(False, 2, "fast", 3)
    assert b["total"] == 0


def test_compute_points_has_no_streak_key():
    # streak multiplier removed — replaced by the explicit daily completion bonus
    b = compute_points(True, 2, "fast", 0)
    assert "streakMultiplier" not in b


def test_compute_points_combo_multiplier_applied():
    b1 = compute_points(True, 2, "medium", 0)
    b5 = compute_points(True, 2, "medium", 5)
    assert b5["total"] > b1["total"]


def test_compute_daily_points_wrong_answer_is_zero():
    b = compute_daily_points(False, 30, 0)
    assert b["total"] == 0


def test_compute_daily_points_increases_with_days():
    # 2 days since last review must score less than 30 days — the whole point
    # of this mode is to reward genuinely stale cards, not gaming via failure.
    b_short = compute_daily_points(True, 2, 0)
    b_long = compute_daily_points(True, 30, 0)
    assert b_long["total"] > b_short["total"]


def test_compute_daily_points_capped_at_30():
    b = compute_daily_points(True, 10_000, 5)  # huge gap + max combo multiplier
    assert b["total"] <= 30


def test_compute_stability_points_fresh_card_scores_high():
    # low retrievability (card mostly forgotten) -> near-max points
    b = compute_stability_points(True, 0.1, 0)
    assert b["total"] >= 6


def test_compute_stability_points_well_known_card_scores_low():
    # high retrievability (card solidly remembered) -> near-zero points
    b = compute_stability_points(True, 0.98, 0)
    assert b["total"] <= 1


def test_compute_stability_points_capped_at_8():
    b = compute_stability_points(True, 0.0, 5)  # zero retrievability + max combo
    assert b["total"] <= 8


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
