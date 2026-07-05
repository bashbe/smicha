"""Evaluation harness for the scheduler — no database required.

Replays answer sequences through the scheduler and prints readable tables so
you can *see* the effect of the changes and of every user-facing option.

It sweeps two things:
  1. RESPONSE SCENARIOS (the two failure modes + a few others).
  2. USER OPTIONS: target_stability (0.92 / 0.95 / 0.96), question difficulty
     (1/2/3), and exam pressure (none / 90d / 30d / 7d).

For each scenario it contrasts:
  * "vanilla"  — raw FSRS-6, product knobs OFF (no cap, no warm-up, w7 as-is,
                 no first-contact softening, no item prior);
  * "tuned"    — FSRS-6 + Phase 1 quick wins + first-contact softening.

Run:  python -m scripts.sim_schedule            (summary tables)
      python -m scripts.sim_schedule --csv      (also dump CSV to scratchpad)
"""

from __future__ import annotations

import csv
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fsrs import (  # noqa: E402
    FsrsCardState,
    FsrsConfig,
    rating_for,
    schedule_next,
    soften_first_contact,
)

# A "vanilla" config with every product knob disabled -> raw FSRS-6.
VANILLA = FsrsConfig(cap_first=10_000, warmup_intervals=[], w7_floor=0.0)
TUNED = FsrsConfig()  # module defaults (cap, warm-up, w7 floor)

# Response scenarios as (is_correct, speed_bucket) per pass.
SCENARIOS: dict[str, list[tuple[bool, str]]] = {
    "a_fast_correct   (mode a)": [(True, "fast")] * 6,
    "b_slow_correct   (mode a)": [(True, "slow")] * 6,
    "c_fail_then_good (mode b)": [(False, "slow")] + [(True, "medium")] * 5,
    "d_good_then_lapse       ": [(True, "fast"), (True, "fast"), (False, "slow"),
                                 (True, "medium"), (True, "medium"), (True, "medium")],
    "e_alternate            ": [(True, "medium"), (False, "slow")] * 3,
}


def _exam_iso(days: int | None) -> str | None:
    return (date.today() + timedelta(days=days)).isoformat() if days else None


def simulate(seq, cfg, *, soften, target, exam_days):
    """Replay a sequence; the learner reviews exactly when each card is due."""
    exam = _exam_iso(exam_days)
    card = FsrsCardState(target_stability=target, due_date=date.today().isoformat())
    rows = []
    for i, (correct, bucket) in enumerate(seq):
        rating = rating_for(correct, bucket)
        if soften:
            rating = soften_first_contact(rating, correct, is_first_contact=(card.state == "new"))
        nx = schedule_next(card, rating, exam, cfg=cfg)
        rows.append({
            "pass": i + 1,
            "rating": rating,
            "S": round(nx.stability, 2),
            "D": round(nx.fsrs_difficulty, 2),
            "interval": nx.scheduled_days,
            "state": nx.state,
        })
        # next review happens `interval` days later
        card = FsrsCardState(
            stability=nx.stability, fsrs_difficulty=nx.fsrs_difficulty,
            reps=nx.reps, lapses=nx.lapses, state=nx.state,
            elapsed_days=nx.scheduled_days, target_stability=target,
            due_date=nx.due_date,
        )
    return rows


def _fmt(rows) -> str:
    head = f"{'#':>2} {'R':>2} {'S':>7} {'D':>6} {'int':>4} {'state':<10}"
    lines = [head]
    for r in rows:
        lines.append(f"{r['pass']:>2} {r['rating']:>2} {r['S']:>7} {r['D']:>6} "
                     f"{r['interval']:>4} {r['state']:<10}")
    return "\n".join(lines)


def main() -> None:
    dump_csv = "--csv" in sys.argv
    csv_rows = []

    print("=" * 78)
    print("SCENARIOS — vanilla FSRS-6  vs  tuned (quick wins)   [target=0.95, diff=2, no exam]")
    print("=" * 78)
    for name, seq in SCENARIOS.items():
        van = simulate(seq, VANILLA, soften=False, target=0.95, exam_days=None)
        tun = simulate(seq, TUNED, soften=True, target=0.95, exam_days=None)
        print(f"\n### {name}")
        print("-- vanilla --")
        print(_fmt(van))
        print("-- tuned --")
        print(_fmt(tun))
        for tag, rows in (("vanilla", van), ("tuned", tun)):
            for r in rows:
                csv_rows.append({"scenario": name.strip(), "variant": tag, **r})

    print("\n" + "=" * 78)
    print("USER OPTIONS — 'tuned', scenario c_fail_then_good (mode b)")
    print("=" * 78)
    seq = SCENARIOS["c_fail_then_good (mode b)"]
    print("\n[target_stability]")
    for t in (0.92, 0.95, 0.96):
        rows = simulate(seq, TUNED, soften=True, target=t, exam_days=None)
        ints = [r["interval"] for r in rows]
        print(f"  target={t}: intervals={ints}")
    print("\n[exam pressure]  (scenario a_fast_correct, target=0.95)")
    for d in (None, 90, 30, 7):
        rows = simulate(SCENARIOS["a_fast_correct   (mode a)"], TUNED,
                        soften=True, target=0.95, exam_days=d)
        ints = [r["interval"] for r in rows]
        print(f"  exam in {str(d)+'d' if d else 'none':>4}: intervals={ints}")

    if dump_csv:
        scratch = os.environ.get("SCRATCHPAD", ".")
        path = os.path.join(scratch, "sim_schedule.csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["scenario", "variant", "pass", "rating",
                                              "S", "D", "interval", "state"])
            w.writeheader()
            w.writerows(csv_rows)
        print(f"\nCSV written to {path}")


if __name__ == "__main__":
    main()
