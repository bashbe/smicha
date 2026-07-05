"""Collective calibration (Phase 2): latency normalisation, HSHS auto-grade,
per-item Elo, and derivation of the per-item FSRS priors.

Dependency-free (stdlib ``math`` only), to keep the project's "no external
dependency" contract. All tuning knobs are named constants so they can be
swept in the simulation scripts.

The public entry points used by ``blueprints/api.py`` are:

  * ``clean_rt``            — winsorise / reject raw response times
  * ``normalize_latency``  — (z_item, z_user) from log(rt)
  * ``bucket_from_z``      — speed bucket from z-scores (falls back to absolute)
  * ``auto_grade_from_latency`` — continuous 1.0..4.0 grade
  * ``update_elo``         — online Elo update (item difficulty + user ability)
  * ``update_running_logrt`` — online Welford update of a log(rt) mean/sd/n
  * ``build_prior``        — assemble an ``fsrs.ItemPrior`` (blended, capped)
"""

from __future__ import annotations

import math

from fsrs import ItemPrior, DEFAULT_W, speed_bucket

# ---------------------------------------------------------------------------
# Response-time hygiene
# ---------------------------------------------------------------------------
MIN_RT_MS = 400        # below this = not a real read (physiological floor)
MAX_RT_MS = 120_000    # winsorise anything above (timeout / distraction)

# ---------------------------------------------------------------------------
# Confidence gating for the collective prior (number of responses per item)
# ---------------------------------------------------------------------------
N_MIN_PRIOR = 30       # below → content prior only (hidden difficulty)
N_FULL_PRIOR = 100     # at/above → full (still capped) collective prior
ALPHA_MAX = 0.6        # HARD CAP: the collective prior never exceeds this weight
ALPHA_CONTENT = 0.15   # light nudge from the content prior when data is scarce

MIN_N_FOR_Z = 5        # need at least this many samples before trusting mu/sigma

# ---------------------------------------------------------------------------
# Elo (dynamic Rasch) parameters — K decreases as an item accrues updates.
# ---------------------------------------------------------------------------
ELO_K_MAX = 0.5
ELO_K_MIN = 0.1
ELO_K_DECAY_N = 15     # updates over which K decays toward ELO_K_MIN

# Default "Good" initial stability (w2) — anchor for the per-item S0 prior.
_S0_GOOD_DEFAULT = DEFAULT_W[2]

# Content-only difficulty prior from the hidden difficulty level (1..3).
_CONTENT_D0 = {1: 3.0, 2: 5.5, 3: 8.0}


def _sigmoid(x: float) -> float:
    if x < -60:
        return 0.0
    if x > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------------------------------------------------------
# Response-time hygiene + running distribution
# ---------------------------------------------------------------------------

def clean_rt(rt_ms: int | None) -> float | None:
    """Return a winsorised RT (ms) or None if it should be ignored entirely."""
    if not rt_ms or rt_ms < MIN_RT_MS:
        return None
    return float(min(rt_ms, MAX_RT_MS))


def update_running_logrt(
    mean: float | None, sd: float | None, n: int, rt_ms: int
) -> tuple[float, float, int]:
    """Online Welford update of the log(rt) mean/sd/n for a single stream.

    The authoritative mean/sd are recomputed in batch (scripts/recompute_item_stats.py);
    this keeps a live estimate between batches.
    """
    rt = clean_rt(rt_ms)
    if rt is None:
        return (mean or 0.0, sd or 0.0, n)
    x = math.log(rt)
    if n <= 0 or mean is None:
        return (x, 0.0, 1)
    m2 = (sd or 0.0) ** 2 * (n - 1)
    n1 = n + 1
    delta = x - mean
    mean1 = mean + delta / n1
    m2 += delta * (x - mean1)
    sd1 = math.sqrt(m2 / (n1 - 1)) if n1 > 1 else 0.0
    return (mean1, sd1, n1)


# ---------------------------------------------------------------------------
# Latency -> z-scores -> bucket / grade
# ---------------------------------------------------------------------------

def _z(logrt: float, mean: float | None, sd: float | None, n: int) -> float | None:
    if mean is None or not sd or sd <= 0 or n < MIN_N_FOR_Z:
        return None
    return (logrt - mean) / sd


def normalize_latency(rt_ms: int, item_stats, user_speed) -> tuple[float | None, float | None]:
    """Return (z_item, z_user) on log(rt). Either may be None if uncalibrated."""
    rt = clean_rt(rt_ms)
    if rt is None:
        return (None, None)
    logrt = math.log(rt)
    z_item = z_user = None
    if item_stats is not None:
        z_item = _z(logrt, item_stats.log_rt_mean, item_stats.log_rt_sd, item_stats.n_responses)
    if user_speed is not None:
        z_user = _z(logrt, user_speed.log_rt_mean, user_speed.log_rt_sd, user_speed.n_responses)
    return (z_item, z_user)


def _effective_z(z_item: float | None, z_user: float | None) -> float | None:
    """Prefer the per-item z (neutralises question length); fall back to the
    per-user z (neutralises reading speed)."""
    if z_item is not None:
        return z_item
    return z_user


def bucket_from_z(
    z_item: float | None, z_user: float | None, difficulty: int, rt_ms: int
) -> str:
    """Speed bucket from z-scores; falls back to the absolute thresholds when
    neither the item nor the user is calibrated yet (backward compatible)."""
    z = _effective_z(z_item, z_user)
    if z is None:
        return speed_bucket(difficulty, rt_ms)
    if z <= -0.5:      # faster than typical for this item/user
        return "fast"
    if z >= 0.5:       # slower than typical
        return "slow"
    return "medium"


def auto_grade_from_latency(is_correct: bool, z: float | None, bucket: str | None = None) -> float:
    """Continuous 1.0..4.0 grade (HSHS/SRT flavour).

    Correct + fast -> ~4.0, correct + slow -> ~2.5, incorrect -> 1.0 with a
    deliberately moderate penalty (the grade is never shown to the student, so
    we avoid the harsh fast-wrong penalty that Math Garden users rejected).
    """
    if not is_correct:
        return 1.0
    if z is not None:
        return max(2.0, min(4.0, 3.0 - z))
    if bucket == "fast":
        return 4.0
    if bucket == "slow":
        return 2.5
    return 3.0


# ---------------------------------------------------------------------------
# Elo (dynamic Rasch) — updates item difficulty and learner ability together
# ---------------------------------------------------------------------------

def elo_k(n_updates: int) -> float:
    """Decreasing learning rate: high at first, settling toward ELO_K_MIN."""
    return ELO_K_MIN + (ELO_K_MAX - ELO_K_MIN) * math.exp(-n_updates / ELO_K_DECAY_N)


def update_elo(
    item_difficulty: float,
    item_n_updates: int,
    user_ability: float,
    is_correct: bool,
    z_item: float | None,
) -> tuple[float, float]:
    """Return (new_item_difficulty, new_user_ability).

    Performance is the continuous grade mapped to [0, 1] so speed feeds the
    rating (High-Speed-High-Stakes), not just accuracy.
    """
    grade = auto_grade_from_latency(is_correct, z_item)
    perf = (grade - 1.0) / 3.0  # -> [0, 1]
    p_expected = _sigmoid(user_ability - item_difficulty)
    k = elo_k(item_n_updates)
    new_ability = user_ability + k * (perf - p_expected)
    new_difficulty = item_difficulty + k * (p_expected - perf)
    return (new_difficulty, new_ability)


# ---------------------------------------------------------------------------
# Prior derivation
# ---------------------------------------------------------------------------

def _d0_from_content(hidden_difficulty: int | None) -> float:
    return _CONTENT_D0.get(hidden_difficulty or 2, 5.5)


def _d0_from_elo(elo_difficulty: float) -> float:
    """Map an Elo difficulty (logit-ish) to the FSRS 1..10 difficulty scale."""
    return 1.0 + 9.0 * _sigmoid(elo_difficulty)


def _s0_from_d0(d0: float) -> float:
    """Harder item -> shorter initial stability. Multiplier 2.0 (easy) .. 0.4 (hard)."""
    mult = 2.0 - (d0 - 1.0) / 9.0 * 1.6
    return _S0_GOOD_DEFAULT * mult


def _alpha(n_responses: int) -> float:
    """Confidence-gated, hard-capped blend weight (never reaches 1.0)."""
    if n_responses < N_MIN_PRIOR:
        return ALPHA_CONTENT
    ramp = min(1.0, (n_responses - N_MIN_PRIOR) / (N_FULL_PRIOR - N_MIN_PRIOR))
    return ALPHA_CONTENT + (ALPHA_MAX - ALPHA_CONTENT) * ramp


def derive_priors(item_stats) -> tuple[float, float]:
    """Return (d0_prior, s0_prior_good) for an ItemStats row (for the batch job)."""
    hidden = getattr(item_stats, "hidden_difficulty", None)
    n = item_stats.n_responses or 0
    d0_content = _d0_from_content(hidden)
    if n >= N_MIN_PRIOR and item_stats.elo_n_updates:
        d0_elo = _d0_from_elo(item_stats.elo_difficulty or 0.0)
        w = min(1.0, (n - N_MIN_PRIOR) / (N_FULL_PRIOR - N_MIN_PRIOR))
        d0 = w * d0_elo + (1.0 - w) * d0_content
    else:
        d0 = d0_content
    return (d0, _s0_from_d0(d0))


def build_prior(hidden_difficulty: int | None, item_stats) -> ItemPrior:
    """Assemble the (blended, capped) ItemPrior handed to fsrs.schedule_next.

    Works even when ``item_stats`` is None (brand-new question with no row yet):
    it falls back to the content prior with a light alpha.
    """
    if item_stats is None:
        d0 = _d0_from_content(hidden_difficulty)
        return ItemPrior(d0=d0, s0_good=_s0_from_d0(d0), alpha=ALPHA_CONTENT)
    d0, s0_good = derive_priors(item_stats)
    return ItemPrior(d0=d0, s0_good=s0_good, alpha=_alpha(item_stats.n_responses or 0))
