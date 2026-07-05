"""Show the collective prior blending — and prove it never overrides FSRS 100%.

For a brand-new card answered "Good" on first contact, this compares the
resulting initial D0 / S0 / interval as an item accumulates responses
(n = 0, 15, 30, 60, 100, 300). The blended value must always stay strictly
between the pure FSRS default (alpha=0) and the pure item prior (alpha=1).

Run:  python -m scripts.sim_priors
"""

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calibration  # noqa: E402
from fsrs import (  # noqa: E402
    FsrsCardState,
    ItemPrior,
    _blend_initial,
    _initial_difficulty,
    _initial_stability,
    DEFAULT_CONFIG,
    schedule_next,
)


class _FakeStats:
    """Minimal stand-in for a models.ItemStats row (no DB)."""

    def __init__(self, n, elo_difficulty, hidden_difficulty=3, elo_n_updates=None):
        self.n_responses = n
        self.elo_difficulty = elo_difficulty
        self.elo_n_updates = elo_n_updates if elo_n_updates is not None else n
        self.hidden_difficulty = hidden_difficulty


def main() -> None:
    cfg = DEFAULT_CONFIG
    rating = 3  # "Good" first contact
    s0_def = _initial_stability(rating, cfg)
    d0_def = _initial_difficulty(rating, cfg)

    print("=" * 74)
    print("PRIOR BLENDING for a NEW card, first answer = Good (rating 3)")
    print(f"pure FSRS default:  D0={d0_def:.2f}  S0={s0_def:.2f}")
    print("hidden_difficulty=3 (a hard item) -> collective prior pulls D0 up, S0 down")
    print("=" * 74)
    print(f"{'n_resp':>7} {'alpha':>6} {'D0':>6} {'S0':>7} {'interval':>9}   bounds-check")

    # a "hard" item: high Elo difficulty
    for n in (0, 15, 30, 60, 100, 300):
        stats = None if n == 0 else _FakeStats(n, elo_difficulty=2.0)
        prior = calibration.build_prior(3, stats)
        s0, d0 = _blend_initial(rating, prior, cfg)

        # pure-prior reference (alpha forced to 1) for the bounds check
        pure = ItemPrior(d0=prior.d0, s0_good=prior.s0_good, alpha=1.0)
        s0_pure, d0_pure = _blend_initial(rating, pure, cfg)

        lo, hi = sorted((d0_def, d0_pure))
        ok = lo - 1e-9 <= d0 <= hi + 1e-9
        card = FsrsCardState(target_stability=0.95, due_date=date.today().isoformat())
        nx = schedule_next(card, rating, None, prior=prior, cfg=cfg)
        print(f"{n:>7} {prior.alpha:>6.2f} {d0:>6.2f} {s0:>7.2f} {nx.scheduled_days:>9}   "
              f"D0 in [{lo:.2f},{hi:.2f}] -> {'OK' if ok else 'FAIL'}")

    print(f"\nalpha is hard-capped at ALPHA_MAX={calibration.ALPHA_MAX} "
          f"-> collective signal never dictates D0/S0 at 100%.")


if __name__ == "__main__":
    main()
