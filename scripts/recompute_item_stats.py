"""Nightly batch: recompute the authoritative collective aggregates.

Run manually or from a scheduler (e.g. PythonAnywhere):

    python -m scripts.recompute_item_stats

For every question it recomputes, from the append-only UserAnswer log:
  * n_responses / n_correct / accuracy
  * log_rt_mean / log_rt_sd over the CORRECT, hygiene-filtered responses
  * d0_prior / s0_prior_good (via calibration.derive_priors)

It also refreshes each user's reading-speed distribution (user_speed).
Elo ratings are maintained online in the API and are left untouched here.
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calibration  # noqa: E402
from app import create_app  # noqa: E402
from models import ItemStats, Question, UserAnswer, UserSpeed, db  # noqa: E402


def _mean_sd(values: list[float]) -> tuple[float | None, float | None]:
    n = len(values)
    if n == 0:
        return (None, None)
    mean = sum(values) / n
    if n < 2:
        return (mean, 0.0)
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return (mean, math.sqrt(var))


def recompute() -> None:
    app = create_app()
    with app.app_context():
        # ---- per-item aggregates -------------------------------------------
        n_items = 0
        for q in Question.query.all():
            answers = UserAnswer.query.filter_by(question_id=q.id).all()
            stats = ItemStats.query.get(q.id)
            if stats is None:
                stats = ItemStats(
                    question_id=q.id,
                    question_type=q.question_type,
                    hidden_difficulty=q.difficulty,
                )
                db.session.add(stats)

            n_responses = len(answers)
            correct = [a for a in answers if a.is_correct]
            n_correct = len(correct)
            log_rts = [
                math.log(rt)
                for a in correct
                if (rt := calibration.clean_rt(a.response_time_ms)) is not None
            ]
            mean, sd = _mean_sd(log_rts)

            stats.question_type = q.question_type
            stats.hidden_difficulty = q.difficulty
            stats.n_responses = n_responses
            stats.n_correct = n_correct
            stats.accuracy = (n_correct / n_responses) if n_responses else 0.0
            stats.log_rt_mean = mean
            stats.log_rt_sd = sd
            stats.d0_prior, stats.s0_prior_good = calibration.derive_priors(stats)
            n_items += 1

        # ---- per-user reading speed ----------------------------------------
        n_users = 0
        for us in UserSpeed.query.all():
            answers = UserAnswer.query.filter_by(user_id=us.user_id).all()
            log_rts = [
                math.log(rt)
                for a in answers
                if (rt := calibration.clean_rt(a.response_time_ms)) is not None
            ]
            mean, sd = _mean_sd(log_rts)
            us.log_rt_mean, us.log_rt_sd, us.n_responses = mean, sd, len(log_rts)
            n_users += 1

        db.session.commit()
        print(f"recomputed {n_items} item_stats rows and {n_users} user_speed rows")

        # ---- retention calibration rollup (read-only) ----------------------
        # Score FSRS's predicted retention against observed outcomes, from the
        # append-only UserAnswer log (predicted_r is stored per review). This
        # is the primary "are our settings actually working?" signal — without
        # it, CAP_FIRST / WARMUP / W7_FLOOR / Elo are unfalsifiable.
        rows = (
            db.session.query(UserAnswer.predicted_r, UserAnswer.is_correct, Question.parcours)
            .join(Question, Question.id == UserAnswer.question_id)
            .filter(UserAnswer.predicted_r.isnot(None))
            .all()
        )
        overall = calibration.retention_report([(pr, c) for pr, c, _ in rows])
        if not overall["n"]:
            print("retention: no predicted_r data yet (needs reviews of engaged cards)")
            return

        print(
            f"retention: n={overall['n']} log_loss={overall['log_loss']:.4f} "
            f"rmse_bins={overall['rmse_bins']:.4f} "
            f"true_ret={overall['true_retention']:.3f} pred_ret={overall['predicted_retention']:.3f}"
        )
        by_parcours: dict[str, list] = {}
        for pr, correct, parcours in rows:
            by_parcours.setdefault(parcours or "—", []).append((pr, correct))
        for parcours, pairs in sorted(by_parcours.items()):
            rep = calibration.retention_report(pairs)
            if rep["n"] >= 20:  # skip too-small slices (noise)
                print(
                    f"  [{parcours}] n={rep['n']} log_loss={rep['log_loss']:.4f} "
                    f"true_ret={rep['true_retention']:.3f} pred_ret={rep['predicted_retention']:.3f}"
                )


if __name__ == "__main__":
    recompute()
