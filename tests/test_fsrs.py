"""Tests for the FSRS-6 scheduler + Phase 1 quick wins.

pytest-compatible, but also runnable standalone (no pytest required):

    python tests/test_fsrs.py
"""

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fsrs import (  # noqa: E402
    CAP_FIRST,
    DEFAULT_W,
    FIRST_CONTACT_POINTS,
    FsrsCardState,
    FsrsConfig,
    ItemPrior,
    WARMUP_INTERVALS,
    _blend_initial,
    _initial_difficulty,
    _initial_stability,
    _next_difficulty,
    personal_bucket,
    rating_for,
    retrievability,
    schedule_next,
    soften_first_contact,
)

VANILLA = FsrsConfig(cap_first=10_000, warmup_intervals=[], w7_floor=0.0)


def _new_card(target=0.95):
    return FsrsCardState(target_stability=target, due_date=date.today().isoformat())


def test_weights_count():
    assert len(DEFAULT_W) == 21


def test_retrievability_at_stability_is_090():
    s = _initial_stability(3)
    assert abs(retrievability(s, s) - 0.9) < 1e-6


def test_retrievability_monotonic_decreasing_in_time():
    s = 10.0
    assert retrievability(1, s) > retrievability(5, s) > retrievability(20, s)


def test_first_easy_interval_capped():
    # Phase 1 #1/#3: a first "Easy" must NOT project a week out.
    nx = schedule_next(_new_card(), 4, None)
    assert nx.scheduled_days <= CAP_FIRST
    assert nx.scheduled_days <= WARMUP_INTERVALS[0]


def test_warmup_ramp_followed():
    # first successful passes are capped by the warm-up grid
    card = _new_card()
    intervals = []
    for _ in range(len(WARMUP_INTERVALS)):
        nx = schedule_next(card, 4, None)
        intervals.append(nx.scheduled_days)
        card = FsrsCardState(
            stability=nx.stability, fsrs_difficulty=nx.fsrs_difficulty,
            reps=nx.reps, lapses=nx.lapses, state=nx.state,
            elapsed_days=nx.scheduled_days, target_stability=0.95, due_date=nx.due_date,
        )
    for got, cap in zip(intervals, WARMUP_INTERVALS):
        assert got <= cap


def test_mean_reversion_faster_than_vanilla():
    # Phase 1 #2 (mode b): after a lapse, difficulty must return to average
    # much faster with the w7 floor than with raw FSRS-6.
    start = FsrsCardState(stability=5.0, fsrs_difficulty=9.0, reps=3, state="review",
                          target_stability=0.95, elapsed_days=5, due_date=date.today().isoformat())
    d_tuned = start.fsrs_difficulty
    d_vanilla = start.fsrs_difficulty
    for _ in range(5):
        d_tuned = _next_difficulty(d_tuned, 3)                 # tuned: w7 floored
        d_vanilla = _next_difficulty(d_vanilla, 3, VANILLA)    # vanilla: w7=0.001
    # tuned drops meaningfully; vanilla barely moves
    assert d_tuned < d_vanilla
    assert (9.0 - d_tuned) > 3 * (9.0 - d_vanilla)


def test_lapse_never_increases_stability():
    card = FsrsCardState(stability=20.0, fsrs_difficulty=5.0, reps=4, state="review",
                         target_stability=0.95, elapsed_days=15, due_date=date.today().isoformat())
    nx = schedule_next(card, 1, None)
    assert nx.stability <= card.stability
    assert nx.lapses == card.lapses + 1


def test_soften_first_contact():
    # correct-but-slow first contact -> Good (3), not Hesitant (2)
    assert soften_first_contact(2, True, True) == 3
    # fast first contact stays Easy
    assert soften_first_contact(4, True, True) == 4
    # wrong stays Again
    assert soften_first_contact(1, False, True) == 1
    # once the card has history, no softening
    assert soften_first_contact(2, True, False) == 2


def test_personal_bucket_no_reference():
    # No reference time yet (very first exposure) -> neutral "medium"
    assert personal_bucket(None, 5000) == "medium"
    assert personal_bucket(0, 5000) == "medium"


def test_personal_bucket_relative_thresholds():
    reference = 9000
    # More than 1/3 faster than the reference -> fast
    assert personal_bucket(reference, 6000) == "fast"
    # More than 1/3 slower than the reference -> slow
    assert personal_bucket(reference, 12000) == "slow"
    # In between -> medium (the "Good" zone)
    assert personal_bucket(reference, 9000) == "medium"
    assert personal_bucket(reference, 7500) == "medium"


def test_personal_bucket_boundary_is_inclusive():
    reference = 9000
    assert personal_bucket(reference, round(reference * 2 / 3)) == "fast"
    assert personal_bucket(reference, round(reference * 4 / 3)) == "slow"


def test_activation_rating_matches_personal_bucket():
    # Mirrors the "activation" transition (Cas C in blueprints/api.py): the
    # rating fed into schedule_next comes straight from the comparison to the
    # first-success response time, with no soften_first_contact floor.
    reference = 9000
    assert rating_for(True, personal_bucket(reference, 6000)) == 4   # 1/3 faster -> Easy
    assert rating_for(True, personal_bucket(reference, 9000)) == 3   # unchanged -> Good
    assert rating_for(True, personal_bucket(reference, 12000)) == 2  # 1/3 slower -> Hard
    assert rating_for(False, personal_bucket(reference, 6000)) == 1  # wrong -> Again regardless of speed


def test_first_contact_points_constant():
    assert FIRST_CONTACT_POINTS == 20


def test_prior_blend_is_bounded():
    # collective prior must never override the FSRS default 100%
    s0_def = _initial_stability(3)
    d0_def = _initial_difficulty(3)
    prior = ItemPrior(d0=9.0, s0_good=0.5, alpha=0.6)
    s0, d0 = _blend_initial(3, prior, FsrsConfig())
    assert min(d0_def, 9.0) <= d0 <= max(d0_def, 9.0)
    assert d0 != 9.0  # strictly blended, not substituted
    assert min(s0_def, 0.5) <= s0 <= max(s0_def, 0.5)


def test_exam_pressure_caps_interval():
    from datetime import timedelta
    card = FsrsCardState(stability=200.0, fsrs_difficulty=3.0, reps=5, state="review",
                         target_stability=0.95, elapsed_days=100, due_date=date.today().isoformat())
    exam = (date.today() + timedelta(days=10)).isoformat()
    nx = schedule_next(card, 3, exam)
    assert nx.scheduled_days <= 10  # never scheduled after the exam


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
