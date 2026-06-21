"""Points / combo / streak scoring. Port of src/lib/points.ts."""

from __future__ import annotations


def compute_points(is_correct: bool, difficulty: int, speed: str, combo: int, streak_days: int) -> dict:
    if not is_correct:
        return {
            "base": 0,
            "difficultyBonus": 0,
            "speedBonus": 0,
            "comboMultiplier": 1,
            "streakMultiplier": 1,
            "total": 0,
        }

    base = 10
    difficulty_bonus = 2 if difficulty == 1 else 4 if difficulty == 2 else 6
    speed_bonus = 5 if speed == "fast" else 2 if speed == "medium" else 0

    combo_multiplier = 1.0
    if combo >= 5:
        combo_multiplier = 1.5
    elif combo == 4:
        combo_multiplier = 1.3
    elif combo == 3:
        combo_multiplier = 1.2
    elif combo == 2:
        combo_multiplier = 1.1

    streak_multiplier = 1.0
    if streak_days >= 30:
        streak_multiplier = 1.5
    elif streak_days >= 7:
        streak_multiplier = 1.2

    raw = (base + difficulty_bonus + speed_bonus) * combo_multiplier * streak_multiplier
    return {
        "base": base,
        "difficultyBonus": difficulty_bonus,
        "speedBonus": speed_bonus,
        "comboMultiplier": combo_multiplier,
        "streakMultiplier": streak_multiplier,
        "total": round(raw),
    }


def combo_label(combo: int) -> str | None:
    if combo < 2:
        return None
    if combo >= 5:
        return f"🔥 ×{combo} ומעלה!"
    return f"🔥 ×{combo}"
