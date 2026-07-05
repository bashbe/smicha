"""Tests for the collective calibration module.

pytest-compatible, also runnable standalone:  python tests/test_calibration.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calibration  # noqa: E402


class _Stats:
    def __init__(self, **kw):
        self.log_rt_mean = kw.get("log_rt_mean")
        self.log_rt_sd = kw.get("log_rt_sd")
        self.n_responses = kw.get("n_responses", 0)
        self.elo_difficulty = kw.get("elo_difficulty", 0.0)
        self.elo_n_updates = kw.get("elo_n_updates", 0)
        self.hidden_difficulty = kw.get("hidden_difficulty", 2)


def test_clean_rt_filters_extremes():
    assert calibration.clean_rt(100) is None          # below physiological floor
    assert calibration.clean_rt(0) is None
    assert calibration.clean_rt(5000) == 5000.0
    assert calibration.clean_rt(999_999) == calibration.MAX_RT_MS  # winsorised


def test_running_logrt_matches_batch():
    rts = [3000, 5000, 8000, 4000, 6000]
    mean = sd = None
    n = 0
    for rt in rts:
        mean, sd, n = calibration.update_running_logrt(mean, sd, n, rt)
    logs = [math.log(r) for r in rts]
    exp_mean = sum(logs) / len(logs)
    exp_var = sum((x - exp_mean) ** 2 for x in logs) / (len(logs) - 1)
    assert n == len(rts)
    assert abs(mean - exp_mean) < 1e-9
    assert abs(sd - math.sqrt(exp_var)) < 1e-9


def test_bucket_falls_back_when_uncalibrated():
    # no z available -> absolute thresholds (backward compatible)
    assert calibration.bucket_from_z(None, None, 2, 3000) == "fast"
    assert calibration.bucket_from_z(None, None, 2, 30000) == "slow"


def test_bucket_from_zscore():
    assert calibration.bucket_from_z(-1.0, None, 2, 9999) == "fast"
    assert calibration.bucket_from_z(0.0, None, 2, 9999) == "medium"
    assert calibration.bucket_from_z(1.0, None, 2, 9999) == "slow"


def test_auto_grade_monotonic():
    fast = calibration.auto_grade_from_latency(True, -1.0)
    med = calibration.auto_grade_from_latency(True, 0.0)
    slow = calibration.auto_grade_from_latency(True, 1.0)
    assert fast > med > slow
    assert calibration.auto_grade_from_latency(False, -1.0) == 1.0  # wrong = Again
    assert 1.0 <= slow <= 4.0 and 1.0 <= fast <= 4.0


def test_elo_direction():
    # correct answer -> item gets easier, learner gets stronger
    diff, ability = calibration.update_elo(0.0, 0, 0.0, True, z_item=-1.0)
    assert diff < 0.0
    assert ability > 0.0
    # wrong answer -> item gets harder, learner weaker
    diff2, ability2 = calibration.update_elo(0.0, 0, 0.0, False, z_item=None)
    assert diff2 > 0.0
    assert ability2 < 0.0


def test_elo_k_decreases():
    assert calibration.elo_k(0) > calibration.elo_k(10) > calibration.elo_k(100)


def test_alpha_capped_and_gated():
    # None item -> light content alpha
    p0 = calibration.build_prior(3, None)
    assert p0.alpha == calibration.ALPHA_CONTENT
    # scarce data -> content alpha
    assert calibration.build_prior(3, _Stats(n_responses=10)).alpha == calibration.ALPHA_CONTENT
    # lots of data -> capped at ALPHA_MAX, never 1.0
    big = calibration.build_prior(3, _Stats(n_responses=1000, elo_difficulty=2.0, elo_n_updates=1000))
    assert big.alpha == calibration.ALPHA_MAX
    assert big.alpha < 1.0


def test_derive_priors_hard_item_short_stability():
    easy = _Stats(n_responses=200, elo_difficulty=-2.0, elo_n_updates=200, hidden_difficulty=1)
    hard = _Stats(n_responses=200, elo_difficulty=2.0, elo_n_updates=200, hidden_difficulty=3)
    d0_easy, s0_easy = calibration.derive_priors(easy)
    d0_hard, s0_hard = calibration.derive_priors(hard)
    assert d0_hard > d0_easy      # harder item -> higher difficulty prior
    assert s0_hard < s0_easy      # harder item -> shorter initial stability


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
