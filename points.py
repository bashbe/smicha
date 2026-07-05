"""Points scoring — étude normale, révision du jour, révision volontaire."""

from __future__ import annotations

import math


def _combo_multiplier(combo: int) -> float:
    if combo >= 5:
        return 1.5
    if combo == 4:
        return 1.3
    if combo == 3:
        return 1.2
    if combo == 2:
        return 1.1
    return 1.0


def compute_points(is_correct: bool, difficulty: int, speed: str, combo: int) -> dict:
    """Étude normale (hors révision). Pas de multiplicateur de streak — le
    seul mécanisme lié à la régularité est le bonus de complétion quotidienne
    explicite (voir blueprints/api.py), pour éviter un double comptage.
    """
    if not is_correct:
        return {"base": 0, "difficultyBonus": 0, "speedBonus": 0, "comboMultiplier": 1, "total": 0}

    base = 10
    difficulty_bonus = 2 if difficulty == 1 else 4 if difficulty == 2 else 6
    speed_bonus = 5 if speed == "fast" else 2 if speed == "medium" else 0
    combo_multiplier = _combo_multiplier(combo)

    raw = (base + difficulty_bonus + speed_bonus) * combo_multiplier
    return {
        "base": base,
        "difficultyBonus": difficulty_bonus,
        "speedBonus": speed_bonus,
        "comboMultiplier": combo_multiplier,
        "total": round(raw),
    }


def compute_daily_points(is_correct: bool, days_since_last_review: int, combo: int) -> dict:
    """Mode "Révision du jour" : points proportionnels au temps écoulé depuis
    la dernière réponse (pas à la stabilité), pour qu'échouer une carte exprès
    ne puisse jamais artificiellement augmenter les points futurs — le
    compteur de jours ne peut repartir que dans le futur, jamais en arrière.
    Courbe logarithmique (plus de différence sur les premiers jours, plateau
    ensuite), cappée à 30 points.
    """
    if not is_correct:
        return {"base": 0, "comboMultiplier": 1, "total": 0}

    days = max(0, days_since_last_review)
    base = min(30, round(10 * math.log10(days + 1)))
    combo_multiplier = _combo_multiplier(combo)
    total = min(30, round(base * combo_multiplier))
    return {"base": base, "comboMultiplier": combo_multiplier, "total": total}


def compute_stability_points(is_correct: bool, retrievability: float, combo: int) -> dict:
    """Modes "Révision par siman / sujet / aléatoire" : points inversement
    proportionnels à la rétrievabilité FSRS (fsrs.retrievability), cappés à 8
    pour limiter l'impact d'un éventuel abus (ces modes portent sur des
    cartes déjà apprises, hors calendrier de révision obligatoire).
    """
    if not is_correct:
        return {"base": 0, "comboMultiplier": 1, "total": 0}

    r = max(0.0, min(1.0, retrievability))
    base = min(8, round(8 * (1 - r)))
    combo_multiplier = _combo_multiplier(combo)
    total = min(8, round(base * combo_multiplier))
    return {"base": base, "comboMultiplier": combo_multiplier, "total": total}


def combo_label(combo: int) -> str | None:
    if combo < 2:
        return None
    if combo >= 5:
        return f"🔥 ×{combo} ומעלה!"
    return f"🔥 ×{combo}"
