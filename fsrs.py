"""FSRS-6 scheduler with speed-based automatic rating + per-item priors.

Implements the full FSRS-6 mathematical model (21 weights, w0-w20) as a
dependency-free port of the reference implementation
(open-spaced-repetition / py-fsrs). Rating (1-4) is derived automatically
from correctness + response speed rather than user self-assessment.

On top of vanilla FSRS-6 this module adds product-specific tuning knobs,
all exposed as named constants / an ``FsrsConfig`` object so they can be
swept and evaluated (see ``scripts/sim_schedule.py``):

  * CAP_FIRST      — ceiling on the very first interval (failure mode "a":
                     a card answered right on the first pass must not vanish
                     for a week).
  * WARMUP_INTERVALS — conservative fixed ramp for the first few successful
                     passes before FSRS fully takes over.
  * W7_FLOOR       — floor on the mean-reversion weight w7 so a card that was
                     failed once climbs back to average difficulty quickly
                     (failure mode "b"); the FSRS-6 default w7 = 0.001 is
                     effectively inert.
  * ItemPrior / alpha — collective per-item difficulty prior, *blended* into
                     S0/D0 for brand-new cards. The blend weight alpha is
                     capped (see calibration.py) so the collective signal
                     never overrides the FSRS computation 100%.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# FSRS-6 default weights (w0-w20) — canonical defaults from py-fsrs.
# Verified against the reference implementation (21 parameters).
# ---------------------------------------------------------------------------
DEFAULT_W = [
    0.212, 1.2931, 2.3065, 8.2956,    # w0-w3 : S0 per rating 1-4 (Again/Hard/Good/Easy)
    6.4133, 0.8334,                   # w4-w5 : initial difficulty D0
    3.0194, 0.001,                    # w6-w7 : difficulty delta + mean reversion
    1.8722, 0.1666, 0.796,            # w8-w10: recall stability
    1.4835, 0.0614, 0.2629, 1.6483,   # w11-w14: forget stability
    0.6014, 1.8729,                   # w15-w16: hard penalty + easy bonus
    0.5425, 0.0912, 0.0658,           # w17-w19: short-term (same-day) stability
    0.1542,                           # w20    : forgetting-curve decay
]

MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0
STABILITY_MIN = 0.001
MAX_INTERVAL = 365

# ---------------------------------------------------------------------------
# Product-specific tuning knobs (Phase 1 quick wins). All named + documented
# so they can be swept in the simulation scripts and validated empirically.
# ---------------------------------------------------------------------------
CAP_FIRST = 4               # hard ceiling (days) on the very first interval
WARMUP_INTERVALS = [1, 3, 7]  # conservative ramp for the first successful passes
W7_FLOOR = 0.15             # floor on mean-reversion weight (default w7=0.001 is inert)

# Flat points awarded for the very first successful answer to a card, before
# FSRS scheduling has ever run on it (see blueprints/api.py "Cas A").
FIRST_CONTACT_POINTS = 20


@dataclass
class FsrsConfig:
    """Bundles the weights + tuning knobs so callers/sim scripts can sweep them."""

    w: list[float] = field(default_factory=lambda: list(DEFAULT_W))
    cap_first: int = CAP_FIRST
    warmup_intervals: list[int] = field(default_factory=lambda: list(WARMUP_INTERVALS))
    w7_floor: float = W7_FLOOR
    max_interval: int = MAX_INTERVAL

    @property
    def decay(self) -> float:
        return -self.w[20]

    @property
    def factor(self) -> float:
        return 0.9 ** (1.0 / self.decay) - 1.0


DEFAULT_CONFIG = FsrsConfig()

# Module-level decay/factor derived from the default weights (used by the
# public helpers that don't take a config).
DECAY = DEFAULT_CONFIG.decay
FACTOR = DEFAULT_CONFIG.factor

# ---------------------------------------------------------------------------
# Difficulty -> (fast_ms, medium_ms) thresholds (absolute fallback; the
# collective z-score path in calibration.py supersedes this once an item has
# enough responses).
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
# Speed -> rating helpers
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


def personal_bucket(reference_ms: int | None, rt_ms: int) -> str:
    """Speed bucket derived from the student's own reference time for this
    card (not a collective z-score). ``reference_ms`` is the previous response
    time to compare against (first-success time, or the rolling average once
    FSRS has engaged). ±1/3 relative rule: faster -> "fast", slower -> "slow".
    """
    if not reference_ms or reference_ms <= 0:
        return "medium"
    if rt_ms <= reference_ms * 2 / 3:
        return "fast"
    if rt_ms >= reference_ms * 4 / 3:
        return "slow"
    return "medium"


def soften_first_contact(rating: int, is_correct: bool, is_first_contact: bool) -> int:
    """Phase 1 #4 — the latency of a card's *first* contact reflects reading /
    discovery, not memory. So on the very first exposure never let a correct
    answer drop below "Good" (3); a wrong answer still maps to "Again" (1).
    """
    if is_first_contact and is_correct:
        return max(rating, 3)
    return rating


# ---------------------------------------------------------------------------
# Per-item collective prior (Phase 2). Blended into S0/D0 for new cards.
# ---------------------------------------------------------------------------

@dataclass
class ItemPrior:
    """Collective difficulty prior for a question, blended with weight ``alpha``.

    ``alpha`` is produced by calibration.py and is always < 1 (capped by
    ALPHA_MAX there) so the collective signal never fully overrides FSRS.
    """

    d0: float          # collective difficulty estimate, 1..10
    s0_good: float     # per-item initial stability for a "Good" first answer (days)
    alpha: float = 0.0  # blend weight in [0, ALPHA_MAX]


# ---------------------------------------------------------------------------
# FSRS-6 core formulas
# ---------------------------------------------------------------------------

def _clamp_difficulty(d: float) -> float:
    return min(max(d, MIN_DIFFICULTY), MAX_DIFFICULTY)


def _clamp_stability(s: float) -> float:
    return max(s, STABILITY_MIN)


def retrievability(elapsed_days: float, stability: float, cfg: FsrsConfig = DEFAULT_CONFIG) -> float:
    """R(t, S) = (1 + FACTOR * t / S)^DECAY — probability of recall."""
    if stability <= 0:
        return 0.0
    return (1.0 + cfg.factor * elapsed_days / stability) ** cfg.decay


def _initial_stability(rating: int, cfg: FsrsConfig = DEFAULT_CONFIG) -> float:
    """S0 for a brand-new card, indexed by rating 1-4 -> w0-w3."""
    return _clamp_stability(cfg.w[rating - 1])


def _initial_difficulty(rating: int, cfg: FsrsConfig = DEFAULT_CONFIG, clamp: bool = True) -> float:
    """D0(G) = w4 - e^(w5*(G-1)) + 1."""
    d = cfg.w[4] - math.exp(cfg.w[5] * (rating - 1)) + 1.0
    return _clamp_difficulty(d) if clamp else d


def _next_difficulty(D: float, rating: int, cfg: FsrsConfig = DEFAULT_CONFIG) -> float:
    """FSRS-6 difficulty update: linear damping + mean reversion toward D0(Easy).

    The mean-reversion weight w7 is floored at ``cfg.w7_floor`` so a once-failed
    card returns to average difficulty in a handful of reviews instead of
    thousands (the raw FSRS-6 default w7 = 0.001 is effectively inert).
    """
    delta = -(cfg.w[6] * (rating - 3))
    damped = (10.0 - D) * delta / 9.0
    arg_2 = D + damped
    arg_1 = _initial_difficulty(4, cfg, clamp=False)  # D0(Easy), unclamped
    w7 = max(cfg.w[7], cfg.w7_floor)
    d = w7 * arg_1 + (1.0 - w7) * arg_2
    return _clamp_difficulty(d)


def _next_recall_stability(
    D: float, S: float, R: float, rating: int, cfg: FsrsConfig = DEFAULT_CONFIG
) -> float:
    """S'_r after a successful recall (rating 2, 3, or 4)."""
    hard_penalty = cfg.w[15] if rating == 2 else 1.0
    easy_bonus = cfg.w[16] if rating == 4 else 1.0
    return S * (
        1.0
        + math.exp(cfg.w[8])
        * (11.0 - D)
        * (S ** (-cfg.w[9]))
        * (math.exp((1.0 - R) * cfg.w[10]) - 1.0)
        * hard_penalty
        * easy_bonus
    )


def _next_forget_stability(
    D: float, S: float, R: float, cfg: FsrsConfig = DEFAULT_CONFIG
) -> float:
    """S'_f after forgetting (rating 1) — min of long-term and short-term forms.

    The short-term cap (S / e^(w17*w18)) guarantees a lapse never *increases*
    stability, the FSRS-6 fix for the "failed card stuck as hard" mode.
    """
    long_term = (
        cfg.w[11]
        * (D ** (-cfg.w[12]))
        * ((S + 1.0) ** cfg.w[13] - 1.0)
        * math.exp((1.0 - R) * cfg.w[14])
    )
    short_term = S / math.exp(cfg.w[17] * cfg.w[18])
    return min(long_term, short_term)


def _short_term_stability(S: float, rating: int, cfg: FsrsConfig = DEFAULT_CONFIG) -> float:
    """Same-day review stability increase (elapsed < 1 day)."""
    increase = math.exp(cfg.w[17] * (rating - 3 + cfg.w[18])) * (S ** (-cfg.w[19]))
    if rating >= 3:  # Good / Easy never shrink stability on a same-day success
        increase = max(increase, 1.0)
    return _clamp_stability(S * increase)


def interval_for_stability(
    S: float, target_r: float = 0.9, cfg: FsrsConfig = DEFAULT_CONFIG
) -> int:
    """Optimal review interval in days to hit target retention."""
    days = S / cfg.factor * (target_r ** (1.0 / cfg.decay) - 1.0)
    return max(1, min(cfg.max_interval, round(days)))


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
# Prior blending (Phase 2) — never lets the collective signal win 100%.
# ---------------------------------------------------------------------------

def _blend_initial(
    rating: int, prior: ItemPrior | None, cfg: FsrsConfig
) -> tuple[float, float]:
    """Return (S0, D0) for a new card, blending FSRS defaults with the item prior.

    D0 is a straight convex blend. S0 keeps the rating ordering
    (Easy > Good > Hard > Again) by scaling the item's "Good" prior to the
    actual rating via the ratio of the default S0s.
    """
    s0_default = _initial_stability(rating, cfg)
    d0_default = _initial_difficulty(rating, cfg)
    if prior is None or prior.alpha <= 0.0:
        return s0_default, d0_default

    a = prior.alpha
    d0 = (1.0 - a) * d0_default + a * prior.d0
    # scale the per-item "Good" stability to this rating
    s0_good_default = _initial_stability(3, cfg)
    rating_scale = s0_default / s0_good_default if s0_good_default else 1.0
    s0_prior = prior.s0_good * rating_scale
    s0 = (1.0 - a) * s0_default + a * s0_prior
    return _clamp_stability(s0), _clamp_difficulty(d0)


# ---------------------------------------------------------------------------
# Main scheduling function
# ---------------------------------------------------------------------------

def _days_from_today(days: int) -> str:
    d = date.today() + timedelta(days=max(0, days))
    return d.isoformat()


def _apply_warmup(scheduled_days: int, reps: int, cfg: FsrsConfig) -> int:
    """Cap the interval by the conservative warm-up grid for early passes."""
    idx = reps - 1  # reps is 1-based after increment
    if 0 <= idx < len(cfg.warmup_intervals):
        return min(scheduled_days, cfg.warmup_intervals[idx])
    return scheduled_days


def schedule_next(
    card: FsrsCardState,
    rating: int,
    exam_date: str | None,
    prior: ItemPrior | None = None,
    cfg: FsrsConfig = DEFAULT_CONFIG,
) -> FsrsCardState:
    """Compute next card state after a review with the given rating (1-4).

    ``prior`` (optional) supplies a collective per-item difficulty prior that
    is *blended* — never substituted — into S0/D0 for brand-new cards.
    """
    # Elapsed days since last actual review
    if card.last_review is not None:
        elapsed = (date.today() - card.last_review.date()).days
    else:
        elapsed = max(card.elapsed_days, 0)

    reps = card.reps + 1
    lapses = card.lapses
    state = card.state

    if state == "new":
        # First-ever review — initialise from scratch (blended with item prior)
        S, D = _blend_initial(rating, prior, cfg)
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
        R = retrievability(elapsed, card.stability, cfg)
        S = _next_forget_stability(card.fsrs_difficulty, card.stability, R, cfg)
        D = _next_difficulty(card.fsrs_difficulty, rating, cfg)
        state = "relearning"

    else:
        # Recalled (rating 2, 3, or 4)
        D = _next_difficulty(card.fsrs_difficulty, rating, cfg)
        if elapsed < 1:
            # same-day re-review
            S = _short_term_stability(card.stability, rating, cfg)
        else:
            R = retrievability(elapsed, card.stability, cfg)
            S = _next_recall_stability(card.fsrs_difficulty, card.stability, R, rating, cfg)
        state = "review" if reps >= 2 else "learning"

    S = _clamp_stability(S)

    # Compute interval from stability
    if rating == 1:
        scheduled_days = 0  # see again today/tomorrow
    else:
        scheduled_days = interval_for_stability(S, card.target_stability, cfg)
        if state == "learning":
            scheduled_days = min(scheduled_days, 1)
        # Phase 1 #1 — hard ceiling on the very first interval
        if card.state == "new":
            scheduled_days = min(scheduled_days, cfg.cap_first)
        # Phase 1 #3 — conservative warm-up ramp for the first passes
        scheduled_days = _apply_warmup(scheduled_days, reps, cfg)

    # Exam-date pressure — smooth linear compression + hard cap when exam is near
    if exam_date and scheduled_days > 0:
        today = datetime.now()
        try:
            exam = datetime.fromisoformat(str(exam_date))
        except ValueError:
            exam = datetime.strptime(str(exam_date)[:10], "%Y-%m-%d")
        days_left = math.ceil((exam - today).total_seconds() / 86400)
        if days_left > 0:
            # Linear pressure: no compression at 90+ days, 30% floor at 0 days
            if days_left < 90:
                pressure = max(0.3, days_left / 90)
                scheduled_days = max(1, round(scheduled_days * pressure))
            # Hard cap: never schedule a review after the exam date
            scheduled_days = min(scheduled_days, days_left)

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
