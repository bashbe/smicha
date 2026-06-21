"""FSRS-4.5 scheduler with speed-based automatic rating.

Implements the full FSRS-4.5 mathematical model using published default
weights. Rating (1-4) is derived automatically from correctness + response
speed rather than user self-assessment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# FSRS-4.5 default weights (w0–w18) — published by the FSRS team
# ---------------------------------------------------------------------------
DEFAULT_W = [
    0.4072, 1.1829, 3.1262, 15.4722,  # w0–w3: S0 per rating 1–4
    7.2102, 0.5316, 1.0651, 0.0589,   # w4–w7: difficulty params
    1.5330, 0.1544, 1.0045, 1.9813,   # w8–w11: recall stability
    0.0953, 0.2975, 2.2042, 0.2407,   # w12–w15: forget stability + hard mult
    2.9466, 0.5034, 0.6567,           # w16–w18: easy mult + interval modifier
]

# Forgetting curve parameters
DECAY = -0.5
FACTOR = 0.9 ** (1.0 / DECAY) - 1  # ≈ 0.2346

MAX_INTERVAL = 365

# ---------------------------------------------------------------------------
# Difficulty → (fast_ms, medium_ms) thresholds
# ---------------------------------------------------------------------------
THRESHOLDS = {
    1: (5000, 15000),
    2: (10000, 25000),
    3: (18000, 40000),
}

# Rating labels displayed in the UI
RATING_LABEL = {
    1: {"label": "לחזור", "emoji": "🔄", "tone": "tone-destructive"},
    2: {"label": "מהסס", "emoji": "⏱", "tone": "tone-warning"},
    3: {"label": "טוב", "emoji": "✓", "tone": "tone-info"},
    4: {"label": "שולט", "emoji": "⚡", "tone": "tone-success"},
}


# ---------------------------------------------------------------------------
# Speed → rating helpers (unchanged from original design)
# ---------------------------------------------------------------------------

def speed_bucket(difficulty: int, ms: int) -> str:
    fast, medium = THRESHOLDS.get(difficulty, THRESHOLDS[2])
    if ms < fast:
        return "fast"
    if ms < medium:
        return "medium"
    return "slow"


def rating_for(is_correct: bool, bucket: str) -> int:
    if not is_correct:
        return 1
    if bucket == "slow":
        return 2
    if bucket == "medium":
        return 3
    return 4


# ---------------------------------------------------------------------------
# Card state dataclass
# ---------------------------------------------------------------------------

@dataclass
class FsrsCardState:
    stability: float = 0.5
    fsrs_difficulty: float = 5.0
    scheduled_days: int = 1
    elapsed_days: int = 0
    reps: int = 0
    lapses: int = 0
    state: str = "new"  # new | learning | review | relearning
    due_date: str = ""  # ISO date string
    target_stability: float = 0.9
    avg_response_time_ms: int = 0
    last_review: datetime | None = field(default=None, compare=False)


# ---------------------------------------------------------------------------
# FSRS-4.5 core formulas
# ---------------------------------------------------------------------------

def retrievability(elapsed_days: float, stability: float) -> float:
    """R(t, S) = (1 + FACTOR * t / S)^DECAY — probability of recall."""
    if stability <= 0:
        return 0.0
    return (1.0 + FACTOR * elapsed_days / stability) ** DECAY


def _initial_stability(rating: int, w: list[float] = DEFAULT_W) -> float:
    """S0 for a brand-new card, indexed by rating 1–4 → w0–w3."""
    return max(0.1, w[rating - 1])


def _initial_difficulty(rating: int, w: list[float] = DEFAULT_W) -> float:
    """D0 for a brand-new card."""
    d = w[4] - math.exp(w[5] * (rating - 1)) + 1
    return max(1.0, min(10.0, d))


def _next_difficulty(D: float, rating: int, w: list[float] = DEFAULT_W) -> float:
    """Update difficulty with mean reversion toward D0(rating=3)."""
    d = D + w[6] * (rating - 3)
    # mean reversion
    d = w[7] * _initial_difficulty(3, w) + (1.0 - w[7]) * d
    return max(1.0, min(10.0, d))


def _next_stability_recall(
    D: float, S: float, R: float, rating: int, w: list[float] = DEFAULT_W
) -> float:
    """S'_r after a successful recall (rating 2, 3, or 4)."""
    hard_penalty = w[15] if rating == 2 else 1.0
    easy_bonus = w[16] if rating == 4 else 1.0
    return S * (
        math.exp(w[8])
        * (11.0 - D)
        * (S ** (-w[9]))
        * (math.exp(w[10] * (1.0 - R)) - 1.0)
        * hard_penalty
        * easy_bonus
        + 1.0
    )


def _next_stability_forget(
    D: float, S: float, R: float, w: list[float] = DEFAULT_W
) -> float:
    """S'_f after forgetting (rating 1)."""
    return (
        w[11]
        * (D ** (-w[12]))
        * ((S + 1.0) ** w[13] - 1.0)
        * math.exp(w[14] * (1.0 - R))
    )


def interval_for_stability(S: float, target_r: float = 0.9) -> int:
    """Optimal review interval in days to hit target retention."""
    days = S / FACTOR * (target_r ** (1.0 / DECAY) - 1.0)
    return max(1, min(MAX_INTERVAL, round(days)))


# ---------------------------------------------------------------------------
# Main scheduling function
# ---------------------------------------------------------------------------

def _days_from_today(days: int) -> str:
    d = date.today() + timedelta(days=max(0, days))
    return d.isoformat()


def schedule_next(card: FsrsCardState, rating: int, exam_date: str | None) -> FsrsCardState:
    """Compute next card state after a review with the given rating (1–4)."""
    # Elapsed days since last actual review
    if card.last_review is not None:
        elapsed = (date.today() - card.last_review.date()).days
    else:
        elapsed = max(card.elapsed_days, 0)

    reps = card.reps + 1
    lapses = card.lapses
    state = card.state

    if state == "new":
        # First-ever review — initialise from scratch
        S = _initial_stability(rating)
        D = _initial_difficulty(rating)
        if rating == 1:
            lapses += 1
            state = "relearning"
        elif rating == 2:
            state = "learning"
        else:
            state = "review"

    elif rating == 1:
        # Forgotten — use forgetting stability formula
        lapses += 1
        R = retrievability(elapsed, card.stability)
        S = _next_stability_forget(card.fsrs_difficulty, card.stability, R)
        D = _next_difficulty(card.fsrs_difficulty, rating)
        state = "relearning"

    else:
        # Recalled (rating 2, 3, or 4)
        R = retrievability(elapsed, card.stability)
        S = _next_stability_recall(card.fsrs_difficulty, card.stability, R, rating)
        D = _next_difficulty(card.fsrs_difficulty, rating)
        state = "review" if reps >= 2 else "learning"

    S = max(0.1, S)

    # Compute interval from stability
    if rating == 1:
        scheduled_days = 0  # see again tomorrow
    else:
        scheduled_days = interval_for_stability(S, card.target_stability)
        if state == "learning":
            scheduled_days = min(scheduled_days, 1)

    # Exam-date pressure — compress intervals when exam is near
    if exam_date and scheduled_days > 0:
        today = datetime.now()
        try:
            exam = datetime.fromisoformat(str(exam_date))
        except ValueError:
            exam = datetime.strptime(str(exam_date)[:10], "%Y-%m-%d")
        days_left = math.ceil((exam - today).total_seconds() / 86400)
        if 0 < days_left <= 7:
            scheduled_days = max(1, round(scheduled_days * 0.5))
        elif 0 < days_left <= 30:
            scheduled_days = max(1, round(scheduled_days * 0.8))

    return replace(
        card,
        stability=S,
        fsrs_difficulty=D,
        scheduled_days=scheduled_days,
        elapsed_days=0,
        reps=reps,
        lapses=lapses,
        state=state,
        due_date=_days_from_today(scheduled_days),
        last_review=None,  # cleared; persisted separately in the DB
    )


def roll_avg(prev: int, sample: int, n: int = 3) -> int:
    """Rolling average over n samples for response time tracking."""
    if not prev:
        return sample
    return round((prev * (n - 1) + sample) / n)
