# Modes de révision multiples + refonte des points — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter 4 modes de révision (jour / siman / sujet / aléatoire) accessibles depuis un hub `/app/revision`, et refondre le système de points pour que les révisions rapportent des points selon deux logiques anti-abus distinctes, plus un bonus de complétion quotidienne avec streak.

**Architecture:** Flask + Jinja2 + SQLAlchemy (SQLite dev / Postgres prod), joueur de questions vanilla JS partagé (`chapitre.js`) piloté par des attributs `data-*` sur un `<div id="player">`. Aucun framework front-end — chaque nouveau mode de révision est une route Flask qui prépare une liste de questions et réutilise soit le template `chapitre.html` (sessions de questions), soit de nouveaux templates de listing (hub, siman, sujet).

**Tech Stack:** Python 3.8+, Flask 3.0, Flask-SQLAlchemy 3.1, SQLite/Postgres, Jinja2, vanilla JS. pytest 8.3 déjà présent comme dépendance de dev (utilisé par `tests/test_fsrs.py`, `tests/test_calibration.py`).

## Global Constraints

- Toute modification de code doit être vérifiée manuellement sur les interfaces impactées : `/app/home`, `/app/parcours`, `/app/chapitre/…`, `/app/revision/*` (règle du `CLAUDE.md` / `README.md` du projet).
- Interface hébreu RTL — vérifier l'alignement après toute modification HTML/CSS.
- Pas de nouvelle dépendance externe (le projet n'a que Flask / Flask-SQLAlchemy / Werkzeug en prod ; pytest est dev-only et déjà présent).
- Pas de système de migration formel — toute nouvelle colonne sur un modèle existant nécessite un script `scripts/migrate_*.py` idempotent suivant le patron de `scripts/migrate_phase2.py` (ALTER TABLE si colonne absente).
- Suivre le style de tests existant : fichiers `tests/test_*.py` à la fois pytest-compatibles et exécutables en standalone (`if __name__ == "__main__"`), voir `tests/test_fsrs.py`.
- Créer des commits fréquents, un par tâche.

---

## Checkpoints de reprise

Chaque tâche ci-dessous est indépendante et se termine par un commit. Pour reprendre le travail après une pause : `git log --oneline -10` pour voir la dernière tâche committée, puis reprendre à la tâche suivante non cochée dans ce fichier. Les cases à cocher (`- [ ]`) de ce document font office de suivi de progression — les cocher au fur et à mesure (`- [x]`) permet de savoir exactement où reprendre.

---

### Task 1 : Migration DB — bonus de complétion quotidienne

**Files:**
- Modify: `models.py:64-81` (classe `StudentProfile`)
- Create: `scripts/migrate_revision_modes.py`

**Interfaces:**
- Produces: `StudentProfile.daily_completion_streak` (Integer, défaut 0), `StudentProfile.last_daily_completion_date` (Date, nullable) — utilisés par Task 3 (`blueprints/api.py`).

- [x] **Step 1: Ajouter les 2 colonnes à `StudentProfile`**

Dans `models.py`, remplacer :

```python
    total_points = db.Column(db.Integer, default=0, nullable=False)
    streak_days = db.Column(db.Integer, default=0, nullable=False)
    last_activity_date = db.Column(db.Date)
    onboarded = db.Column(db.Boolean, default=False, nullable=False)
```

par :

```python
    total_points = db.Column(db.Integer, default=0, nullable=False)
    streak_days = db.Column(db.Integer, default=0, nullable=False)
    last_activity_date = db.Column(db.Date)
    # Bonus de complétion quotidienne (mode "Révision du jour"), distinct de
    # streak_days/last_activity_date qui restent purement informatifs.
    daily_completion_streak = db.Column(db.Integer, default=0, nullable=False)
    last_daily_completion_date = db.Column(db.Date)
    onboarded = db.Column(db.Boolean, default=False, nullable=False)
```

- [x] **Step 2: Créer le script de migration**

Créer `scripts/migrate_revision_modes.py` :

```python
"""Idempotent migration for the revision-modes feature (daily completion streak).

`db.create_all()` doesn't add columns to existing tables. Run this once against
an existing database (dev SQLite you don't want to wipe, or prod Postgres):

    python -m scripts.migrate_revision_modes

Fresh installs don't need it — `python seed.py` builds the full schema.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text  # noqa: E402

from app import create_app  # noqa: E402
from models import db  # noqa: E402

NEW_COLUMNS = {
    "student_profiles": {
        "daily_completion_streak": "INTEGER NOT NULL DEFAULT 0",
        "last_daily_completion_date": "DATE",
    },
}


def migrate() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()
        insp = inspect(db.engine)
        for table, columns in NEW_COLUMNS.items():
            if not insp.has_table(table):
                print(f"skip {table}: table absent (create_all will have made it)")
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for col, coltype in columns.items():
                if col in existing:
                    print(f"ok   {table}.{col} already present")
                    continue
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))
                print(f"add  {table}.{col} {coltype}")
        db.session.commit()
        print("migration complete")


if __name__ == "__main__":
    migrate()
```

- [x] **Step 3: Exécuter la migration sur la base de dev**

Run: `python -m scripts.migrate_revision_modes`
Expected: affiche `add  student_profiles.daily_completion_streak INTEGER NOT NULL DEFAULT 0`, `add  student_profiles.last_daily_completion_date DATE`, puis `migration complete`. Si la base de dev n'existe pas encore (`smiha.db` absent), lancer d'abord `python seed.py`.

- [x] **Step 4: Vérifier le schéma**

Run: `sqlite3 smiha.db ".schema student_profiles"`
Expected: la sortie contient `daily_completion_streak INTEGER NOT NULL DEFAULT 0` et `last_daily_completion_date DATE`.

- [x] **Step 5: Commit**

```bash
git add models.py scripts/migrate_revision_modes.py
git commit -m "feat: add daily completion streak columns to StudentProfile"
```

---

### Task 2 : Formules de points (TDD)

**Files:**
- Modify: `points.py`
- Test: `tests/test_points.py` (nouveau)

**Interfaces:**
- Consumes: rien (fonctions pures).
- Produces:
  - `compute_points(is_correct: bool, difficulty: int, speed: str, combo: int) -> dict` — **signature changée**, le paramètre `streak_days` est supprimé, la clé `"streakMultiplier"` disparaît du dict retourné.
  - `compute_daily_points(is_correct: bool, days_since_last_review: int, combo: int) -> dict` — nouveau, formule logarithmique cappée à 30. Dict retourné : `{"base": int, "comboMultiplier": float, "total": int}`.
  - `compute_stability_points(is_correct: bool, retrievability: float, combo: int) -> dict` — nouveau, formule basée sur `1 - retrievability` cappée à 8. Même forme de dict.
  - Utilisés par Task 3 (`blueprints/api.py`).

- [x] **Step 1: Écrire les tests (ils vont échouer — les fonctions n'existent pas encore avec cette signature)**

Créer `tests/test_points.py` :

```python
"""Tests for points.py scoring formulas.

pytest-compatible, but also runnable standalone (no pytest required):

    python tests/test_points.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from points import compute_points, compute_daily_points, compute_stability_points  # noqa: E402


def test_compute_points_wrong_answer_is_zero():
    b = compute_points(False, 2, "fast", 3)
    assert b["total"] == 0


def test_compute_points_has_no_streak_key():
    # streak multiplier removed — replaced by the explicit daily completion bonus
    b = compute_points(True, 2, "fast", 0)
    assert "streakMultiplier" not in b


def test_compute_points_combo_multiplier_applied():
    b1 = compute_points(True, 2, "medium", 0)
    b5 = compute_points(True, 2, "medium", 5)
    assert b5["total"] > b1["total"]


def test_compute_daily_points_wrong_answer_is_zero():
    b = compute_daily_points(False, 30, 0)
    assert b["total"] == 0


def test_compute_daily_points_increases_with_days():
    # 2 days since last review must score less than 30 days — the whole point
    # of this mode is to reward genuinely stale cards, not gaming via failure.
    b_short = compute_daily_points(True, 2, 0)
    b_long = compute_daily_points(True, 30, 0)
    assert b_long["total"] > b_short["total"]


def test_compute_daily_points_capped_at_30():
    b = compute_daily_points(True, 10_000, 5)  # huge gap + max combo multiplier
    assert b["total"] <= 30


def test_compute_stability_points_fresh_card_scores_high():
    # low retrievability (card mostly forgotten) -> near-max points
    b = compute_stability_points(True, 0.1, 0)
    assert b["total"] >= 6


def test_compute_stability_points_well_known_card_scores_low():
    # high retrievability (card solidly remembered) -> near-zero points
    b = compute_stability_points(True, 0.98, 0)
    assert b["total"] <= 1


def test_compute_stability_points_capped_at_8():
    b = compute_stability_points(True, 0.0, 5)  # zero retrievability + max combo
    assert b["total"] <= 8


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
```

- [x] **Step 2: Lancer les tests pour confirmer qu'ils échouent**

Run: `python -m pytest tests/test_points.py -v`
Expected: `ImportError: cannot import name 'compute_daily_points'` (ou `TypeError` sur l'appel `compute_points(True, 2, "fast", 0)` avec l'ancienne signature à 5 arguments) — les fonctions n'existent pas encore sous cette forme.

- [x] **Step 3: Réécrire `points.py`**

Remplacer tout le contenu de `points.py` par :

```python
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
```

- [x] **Step 4: Lancer les tests pour confirmer qu'ils passent**

Run: `python -m pytest tests/test_points.py -v`
Expected: 9 tests, tous `PASSED`.

- [x] **Step 5: Vérifier que les tests existants ne sont pas cassés**

Run: `python -m pytest tests/ -v`
Expected: `tests/test_fsrs.py` et `tests/test_calibration.py` passent toujours (aucun ne touche `points.py`).

- [x] **Step 6: Commit**

```bash
git add points.py tests/test_points.py
git commit -m "feat: split points formulas — normal study, daily revision (log-scale), stability revision (capped 8)"
```

---

### Task 3 : Intégration API — routage des points + bonus quotidien

**Files:**
- Modify: `blueprints/api.py`

**Interfaces:**
- Consumes: `compute_points(is_correct, difficulty, speed, combo)`, `compute_daily_points(is_correct, days_since_last_review, combo)`, `compute_stability_points(is_correct, retrievability, combo)` (Task 2) ; `fsrs.retrievability(elapsed_days, stability)` (déjà existant) ; `StudentProfile.daily_completion_streak` / `last_daily_completion_date` (Task 1).
- Produces: `POST /api/answer` accepte un champ JSON optionnel `mode` (`"study"` par défaut, ou `"revision_daily"` / `"revision_siman"` / `"revision_sujet"` / `"revision_random"`). La réponse JSON gagne un champ `"daily_bonus": int` (0 si aucun bonus attribué). Utilisé par Task 6 (`chapitre.js`).

- [x] **Step 1: Importer les nouvelles fonctions**

Dans `blueprints/api.py`, remplacer :

```python
from fsrs import (
    FsrsCardState,
    rating_for,
    roll_avg,
    schedule_next,
    soften_first_contact,
    RATING_LABEL,
)
```

par :

```python
from fsrs import (
    FsrsCardState,
    rating_for,
    retrievability,
    roll_avg,
    schedule_next,
    soften_first_contact,
    RATING_LABEL,
)
```

Et remplacer :

```python
from points import compute_points
```

par :

```python
from points import compute_daily_points, compute_points, compute_stability_points
```

- [x] **Step 2: Lire le champ `mode` et capturer le compte de cartes dues avant traitement**

Remplacer :

```python
    data = request.get_json(force=True)
    question_id = data.get("question_id")
    given_answer = data.get("given_answer", "")
    response_time_ms = int(data.get("response_time_ms", 0))
    combo = int(data.get("combo", 0))
```

par :

```python
    data = request.get_json(force=True)
    question_id = data.get("question_id")
    given_answer = data.get("given_answer", "")
    response_time_ms = int(data.get("response_time_ms", 0))
    combo = int(data.get("combo", 0))
    mode = data.get("mode", "study")
```

- [x] **Step 3: Calculer `breakdown` selon le mode (remplace l'appel unique à `compute_points`)**

Remplacer :

```python
    z_item, z_user = calibration.normalize_latency(response_time_ms, item_stats, user_speed)
    z_eff = z_item if z_item is not None else z_user
    bucket = calibration.bucket_from_z(z_item, z_user, q.difficulty, response_time_ms)
    rating = soften_first_contact(rating_for(is_correct, bucket), is_correct, is_first_contact)
    auto_grade = calibration.auto_grade_from_latency(is_correct, z_eff, bucket)
    new_combo = combo + 1 if is_correct else 0

    breakdown = compute_points(is_correct, q.difficulty, bucket, new_combo, sp.streak_days or 0)
```

par :

```python
    z_item, z_user = calibration.normalize_latency(response_time_ms, item_stats, user_speed)
    z_eff = z_item if z_item is not None else z_user
    bucket = calibration.bucket_from_z(z_item, z_user, q.difficulty, response_time_ms)
    rating = soften_first_contact(rating_for(is_correct, bucket), is_correct, is_first_contact)
    auto_grade = calibration.auto_grade_from_latency(is_correct, z_eff, bucket)
    new_combo = combo + 1 if is_correct else 0

    # Nombre de cartes dues AVANT ce traitement (utilisé pour le bonus de
    # complétion quotidienne — capturé avant l'upsert FSRS qui va déplacer
    # due_date de cette carte).
    due_before = 0
    if mode == "revision_daily":
        due_before = FsrsCard.query.filter(
            FsrsCard.user_id == user.id, FsrsCard.due_date <= date.today()
        ).count()

    if mode == "revision_daily":
        days_since = (date.today() - card.last_review.date()).days if (card and card.last_review) else 0
        breakdown = compute_daily_points(is_correct, days_since, new_combo)
    elif mode in ("revision_siman", "revision_sujet", "revision_random"):
        elapsed_for_r = (date.today() - card.last_review.date()).days if (card and card.last_review) else 0
        r = retrievability(elapsed_for_r, card.stability) if card else 0.0
        breakdown = compute_stability_points(is_correct, r, new_combo)
    else:
        breakdown = compute_points(is_correct, q.difficulty, bucket, new_combo)
```

- [x] **Step 4: Attribuer le bonus de complétion quotidienne après la mise à jour du profil**

Remplacer :

```python
    # 4. streak + points on the student profile
    today = date.today()
    new_streak = sp.streak_days or 0
    if sp.last_activity_date != today:
        yesterday = today - timedelta(days=1)
        new_streak = new_streak + 1 if sp.last_activity_date == yesterday else 1
    sp.total_points = (sp.total_points or 0) + breakdown["total"]
    sp.streak_days = new_streak
    sp.last_activity_date = today

    db.session.commit()
```

par :

```python
    # 4. streak + points on the student profile
    today = date.today()
    new_streak = sp.streak_days or 0
    if sp.last_activity_date != today:
        yesterday = today - timedelta(days=1)
        new_streak = new_streak + 1 if sp.last_activity_date == yesterday else 1
    sp.total_points = (sp.total_points or 0) + breakdown["total"]
    sp.streak_days = new_streak
    sp.last_activity_date = today

    # 5. bonus de complétion quotidienne — uniquement pour le mode "Révision
    # du jour", et seulement quand cette réponse fait tomber le nombre de
    # cartes dues à 0 (autoflush : la requête ci-dessous voit déjà le
    # card.due_date mis à jour en mémoire au step 2 du FSRS upsert).
    daily_bonus = 0
    if mode == "revision_daily" and due_before > 0 and sp.last_daily_completion_date != today:
        due_after = FsrsCard.query.filter(
            FsrsCard.user_id == user.id, FsrsCard.due_date <= today
        ).count()
        if due_after == 0:
            yesterday = today - timedelta(days=1)
            new_daily_streak = (
                (sp.daily_completion_streak or 0) + 1
                if sp.last_daily_completion_date == yesterday
                else 1
            )
            daily_bonus = 150 + 20 * (new_daily_streak - 1)
            sp.total_points += daily_bonus
            sp.daily_completion_streak = new_daily_streak
            sp.last_daily_completion_date = today

    db.session.commit()
```

- [x] **Step 5: Renvoyer `daily_bonus` dans la réponse JSON**

Remplacer :

```python
    return jsonify(
        {
            "is_correct": is_correct,
            "correct_key": nq["correctKey"],
            "points": breakdown["total"],
            "combo": new_combo,
            "streak": new_streak,
            "total_points": sp.total_points,
            "explanation": nq.get("explanation"),
            "seif": q.seif,
            "rating_badge": f"{label['emoji']} {label['label']}",
            "rating_tone": label["tone"],
        }
    )
```

par :

```python
    return jsonify(
        {
            "is_correct": is_correct,
            "correct_key": nq["correctKey"],
            "points": breakdown["total"],
            "combo": new_combo,
            "streak": new_streak,
            "total_points": sp.total_points,
            "explanation": nq.get("explanation"),
            "seif": q.seif,
            "rating_badge": f"{label['emoji']} {label['label']}",
            "rating_tone": label["tone"],
            "daily_bonus": daily_bonus,
        }
    )
```

- [x] **Step 6: Vérification manuelle (pas de client de test Flask dans ce projet)**

Run: `python app.py`, se connecter avec `student@example.com` / `password123`, répondre à une question via `/app/chapitre/...` (mode "study" implicite — le payload envoyé par `chapitre.js` n'a pas encore de champ `mode`, donc `data.get("mode", "study")` doit tomber sur `"study"` et se comporter EXACTEMENT comme avant).
Expected : la réponse rapporte des points identiques au comportement précédent (formule `compute_points` sans streak — donc légèrement inférieurs si le streak était ≥7 jours ; c'est le changement attendu de la Task 2, pas une régression).

- [x] **Step 7: Commit**

```bash
git add blueprints/api.py
git commit -m "feat: route /api/answer points through mode-specific formulas + daily completion bonus"
```

---

### Task 4 : Routes backend — hub + 4 modes de révision

**Files:**
- Modify: `blueprints/student.py`

**Interfaces:**
- Consumes: `allowed_sections()`, `question_in_sections()`, `get_profile()` (déjà existants dans ce fichier).
- Produces:
  - `_learned_question_ids(user_id: str) -> list[str]` — nouveau helper, IDs de questions avec ≥1 `UserAnswer` de l'utilisateur.
  - Route `student.revision` (`GET /app/revision`) — hub, render `student/revision_hub.html`.
  - Route `student.revision_jour` (`GET /app/revision/jour`) — ancien contenu de `revision()`, render `student/revision_jour.html`.
  - Route `student.revision_siman` (`GET /app/revision/siman`) — render `student/revision_siman_list.html`.
  - Route `student.revision_siman_detail` (`GET /app/revision/siman/<path:subject>/<int:siman>`) — render `student/chapitre.html`.
  - Route `student.revision_sujet` (`GET /app/revision/sujet`) — render `student/revision_sujet_list.html`.
  - Route `student.revision_sujet_detail` (`GET /app/revision/sujet/<path:subject>`) — render `student/chapitre.html`.
  - Route `student.revision_aleatoire` (`GET /app/revision/aleatoire`) — render `student/chapitre.html`.
  - Utilisées par Task 5 (templates) et déjà consommées par `url_for(...)` dans le hub.

- [x] **Step 1: Ajouter l'import `random` et le helper `_learned_question_ids`**

Remplacer les imports en tête de fichier :

```python
from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import distinct, func

from auth_helpers import current_user, login_required
from models import FsrsCard, Progression, Question, StudentProfile, UserAnswer, db
from question_types import normalize_db_question

bp = Blueprint("student", __name__, url_prefix="/app")
```

par :

```python
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import distinct, func

from auth_helpers import current_user, login_required
from models import FsrsCard, Progression, Question, StudentProfile, UserAnswer, db
from question_types import normalize_db_question

bp = Blueprint("student", __name__, url_prefix="/app")


def _learned_question_ids(user_id: str) -> list[str]:
    """IDs des questions pour lesquelles l'utilisateur a au moins une réponse
    enregistrée (peu importe si correcte), tous modes de révision non-"jour"
    confondus — "déjà apprise" = au moins une tentative.
    """
    rows = (
        db.session.query(UserAnswer.question_id)
        .filter(UserAnswer.user_id == user_id)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]
```

- [x] **Step 2: Transformer `/revision` en hub, déplacer l'ancien contenu vers `/revision/jour`**

Remplacer (le bloc actuel de la route `revision`, y compris son docstring de contexte) :

```python
@bp.route("/revision")
@login_required
def revision():
    sp = get_profile()
    today = date.today()

    due_cards = (
        db.session.query(FsrsCard, Question)
        .join(Question, Question.id == FsrsCard.question_id)
        .filter(
            FsrsCard.user_id == sp.id,
            FsrsCard.due_date <= today,
            Question.status == "approved",
            )
        .order_by(FsrsCard.stability.asc())
        .all()
    )
```

par :

```python
@bp.route("/revision")
@login_required
def revision():
    sp = get_profile()
    today = date.today()

    due_count = FsrsCard.query.filter(FsrsCard.user_id == sp.id, FsrsCard.due_date <= today).count()
    learned_ids = _learned_question_ids(sp.id)
    learned_count = len(learned_ids)

    eligible_subjects = 0
    if learned_ids:
        allowed = allowed_sections(sp.section)
        qs = [q for q in Question.query.filter(
            Question.status == "approved", Question.id.in_(learned_ids),
        ).all() if question_in_sections(q, allowed)]
        counts: dict[str, int] = {}
        for q in qs:
            if q.subject:
                counts[q.subject] = counts.get(q.subject, 0) + 1
        eligible_subjects = sum(1 for c in counts.values() if c >= 3)

    return render_template(
        "student/revision_hub.html",
        profile=sp,
        due_count=due_count,
        learned_count=learned_count,
        random_count=min(10, learned_count),
        eligible_subjects=eligible_subjects,
    )


@bp.route("/revision/jour")
@login_required
def revision_jour():
    sp = get_profile()
    today = date.today()

    due_cards = (
        db.session.query(FsrsCard, Question)
        .join(Question, Question.id == FsrsCard.question_id)
        .filter(
            FsrsCard.user_id == sp.id,
            FsrsCard.due_date <= today,
            Question.status == "approved",
            )
        .order_by(FsrsCard.stability.asc())
        .all()
    )
```

- [x] **Step 3: Renommer le template utilisé par l'ancienne logique**

Cette même fonction (maintenant `revision_jour`) se termine par le rendu du template. Remplacer :

```python
    return render_template(
        "student/revision.html",
        questions=questions,
        profile=sp,
        next_due_days=next_due_days,
        next_due_count=next_due_count,
    )
```

par :

```python
    return render_template(
        "student/revision_jour.html",
        questions=questions,
        profile=sp,
        next_due_days=next_due_days,
        next_due_count=next_due_count,
    )
```

- [x] **Step 4: Ajouter les routes "par siman"**

Juste après la fonction `revision_jour` (avant `@bp.post("/advance-revisions")`), ajouter :

```python
@bp.route("/revision/siman")
@login_required
def revision_siman():
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    learned_ids = _learned_question_ids(sp.id)

    groups = []
    if learned_ids:
        qs = [q for q in Question.query.filter(
            Question.status == "approved", Question.id.in_(learned_ids),
        ).all() if question_in_sections(q, allowed)]

        by_subject: dict[str, dict[int, dict]] = {}
        for q in qs:
            if not q.subject or q.siman is None:
                continue
            by_subject.setdefault(q.subject, {})
            by_subject[q.subject].setdefault(q.siman, {})
            by_subject[q.subject][q.siman][q.seif] = by_subject[q.subject][q.siman].get(q.seif, 0) + 1

        for subject in sorted(by_subject.keys()):
            simanim = []
            for siman, seif_counts in sorted(by_subject[subject].items()):
                seifim = [
                    {"seif": seif, "count": sc}
                    for seif, sc in sorted((k, v) for k, v in seif_counts.items() if k is not None)
                ]
                simanim.append({"siman": siman, "count": sum(seif_counts.values()), "seifim": seifim})
            groups.append({"subject": subject, "simanim": simanim})

    return render_template("student/revision_siman_list.html", groups=groups, profile=sp)


@bp.route("/revision/siman/<path:subject>/<int:siman>")
@login_required
def revision_siman_detail(subject: str, siman: int):
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    learned_ids = _learned_question_ids(sp.id)

    rows = [q for q in Question.query.filter(
        Question.subject == subject, Question.siman == siman,
        Question.status == "approved", Question.id.in_(learned_ids),
    ).order_by(Question.seif.asc()).all() if question_in_sections(q, allowed)]

    if not rows:
        flash("אין עדיין כרטיסים שנלמדו בסימן זה.", "info")
        return redirect(url_for("student.revision_siman"))

    questions = [
        {
            "id": q.id, "difficulty": q.difficulty, "seif": q.seif,
            "subject": q.subject, "siman": q.siman,
            "normalized": normalize_db_question(q.as_dict()),
        }
        for q in rows
    ]
    return render_template(
        "student/chapitre.html", subject=subject, siman=siman, questions=questions, profile=sp,
        mode="revision_siman", mode_label="חזרה לפי סימן", is_revision=True,
        back_url=url_for("student.revision_siman"),
    )


@bp.route("/revision/sujet")
@login_required
def revision_sujet():
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    learned_ids = _learned_question_ids(sp.id)

    subjects = []
    if learned_ids:
        qs = [q for q in Question.query.filter(
            Question.status == "approved", Question.id.in_(learned_ids),
        ).all() if question_in_sections(q, allowed)]
        counts: dict[str, int] = {}
        for q in qs:
            if q.subject:
                counts[q.subject] = counts.get(q.subject, 0) + 1
        subjects = sorted(
            ({"subject": s, "count": c} for s, c in counts.items() if c >= 3),
            key=lambda x: -x["count"],
        )

    return render_template("student/revision_sujet_list.html", subjects=subjects, profile=sp)


@bp.route("/revision/sujet/<path:subject>")
@login_required
def revision_sujet_detail(subject: str):
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    learned_ids = _learned_question_ids(sp.id)

    rows = [q for q in Question.query.filter(
        Question.subject == subject, Question.status == "approved", Question.id.in_(learned_ids),
    ).order_by(Question.siman.asc(), Question.seif.asc()).all() if question_in_sections(q, allowed)]

    if not rows:
        flash("אין עדיין כרטיסים שנלמדו בנושא זה.", "info")
        return redirect(url_for("student.revision_sujet"))

    questions = [
        {
            "id": q.id, "difficulty": q.difficulty, "seif": q.seif,
            "subject": q.subject, "siman": q.siman,
            "normalized": normalize_db_question(q.as_dict()),
        }
        for q in rows
    ]
    return render_template(
        "student/chapitre.html", subject=subject, siman=rows[0].siman, questions=questions, profile=sp,
        mode="revision_sujet", mode_label="חזרה לפי נושא", is_revision=True,
        back_url=url_for("student.revision_sujet"),
    )


@bp.route("/revision/aleatoire")
@login_required
def revision_aleatoire():
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    learned_ids = _learned_question_ids(sp.id)

    rows = [q for q in Question.query.filter(
        Question.status == "approved", Question.id.in_(learned_ids),
    ).all() if question_in_sections(q, allowed)]

    if not rows:
        flash("עדיין אין כרטיסים שנלמדו לחזרה אקראית.", "info")
        return redirect(url_for("student.revision"))

    sample = random.sample(rows, min(10, len(rows)))
    questions = [
        {
            "id": q.id, "difficulty": q.difficulty, "seif": q.seif,
            "subject": q.subject, "siman": q.siman,
            "normalized": normalize_db_question(q.as_dict()),
        }
        for q in sample
    ]
    return render_template(
        "student/chapitre.html", subject="חזרה אקראית", siman=sample[0].siman, questions=questions,
        profile=sp, mode="revision_random", mode_label="חזרה אקראית", is_revision=True,
        back_url=url_for("student.revision"),
    )


```

- [x] **Step 5: Vérification manuelle**

Run: `python app.py`, se connecter comme `student@example.com`, visiter `/app/revision` — la page ne doit plus planter (elle sera cassée visuellement tant que Task 5 n'a pas créé `revision_hub.html`, c'est attendu à ce stade). Visiter directement `/app/revision/jour` — doit fonctionner (le template `student/revision_jour.html` n'existe pas encore non plus, erreur `TemplateNotFound` attendue avant Task 5).

- [x] **Step 6: Commit**

```bash
git add blueprints/student.py
git commit -m "feat: add revision hub + siman/sujet/aleatoire routes (templates pending)"
```

---

### Task 5 : Templates — hub, listes, session

**Files:**
- Create: `templates/student/revision_hub.html`
- Create: `templates/student/revision_jour.html` (contenu déplacé de l'ancien `revision.html`)
- Create: `templates/student/revision_siman_list.html`
- Create: `templates/student/revision_sujet_list.html`
- Modify: `templates/student/chapitre.html`
- Delete: `templates/student/revision.html` (remplacé par `revision_hub.html`)
- Modify: `templates/student/home.html`
- Modify: `templates/student/_layout.html`

**Interfaces:**
- Consumes: routes de Task 4 (`student.revision_jour`, `student.revision_siman`, etc.), variables passées par ces routes (`due_count`, `learned_count`, `random_count`, `eligible_subjects`, `groups`, `subjects`, `questions`, `mode`, `mode_label`, `is_revision`, `back_url`).
- Produces: attributs `data-mode`, `data-mode-label`, `data-revision`, `data-back-url` sur `#player`, consommés par Task 6 (`chapitre.js`).

- [x] **Step 1: Créer `templates/student/revision_hub.html`**

```html
{% extends "student/_layout.html" %}
{% from "_icons.html" import icon_calendar, icon_book, icon_target, icon_refresh %}
{% block title %}חזרה — סמיכה{% endblock %}
{% block content %}
<div class="stack animate-slide-up">
  <h2 class="mb-2">בחר סוג חזרה</h2>

  <div class="stack-sm">
    <a href="{{ url_for('student.revision_jour') }}" class="folio-action">
      <div class="folio-action-body">
        <div class="folio-action-title row gap-1">
          חזרה יומית
          {% if due_count > 0 %}<span class="badge">{{ due_count }}</span>{% endif %}
        </div>
        <div class="folio-action-sub">
          {% if due_count > 0 %}{{ due_count }} כרטיסים ממתינים היום{% else %}אין כרטיסים ממתינים היום{% endif %}
        </div>
      </div>
      <div class="icon-box icon-box-primary">{{ icon_calendar(20) }}</div>
    </a>

    <a href="{{ url_for('student.revision_siman') }}" class="folio-action">
      <div class="folio-action-body">
        <div class="folio-action-title">חזרה לפי סימן</div>
        <div class="folio-action-sub">בחר סימן או סעיף שכבר למדת</div>
      </div>
      <div class="icon-box icon-box-primary">{{ icon_book(20) }}</div>
    </a>

    <a href="{{ url_for('student.revision_sujet') }}" class="folio-action">
      <div class="folio-action-body">
        <div class="folio-action-title row gap-1">
          חזרה לפי נושא
          {% if eligible_subjects > 0 %}<span class="badge">{{ eligible_subjects }}</span>{% endif %}
        </div>
        <div class="folio-action-sub">נושאים עם 3 כרטיסים ומעלה שכבר נלמדו</div>
      </div>
      <div class="icon-box icon-box-primary">{{ icon_target(20) }}</div>
    </a>

    <a href="{{ url_for('student.revision_aleatoire') }}" class="folio-action">
      <div class="folio-action-body">
        <div class="folio-action-title">חזרה אקראית</div>
        <div class="folio-action-sub">{{ random_count }} כרטיסים אקראיים מתוך מה שכבר למדת</div>
      </div>
      <div class="icon-box icon-box-primary">{{ icon_refresh(20) }}</div>
    </a>
  </div>
</div>
{% endblock %}
```

- [x] **Step 2: Créer `templates/student/revision_jour.html` (contenu de l'ancien `revision.html`)**

```html
{% extends "student/_layout.html" %}
{% set show_nav = false %}
{% block title %}חזרה יומית — סמיכה{% endblock %}
{% block content %}
{% if not questions %}
  <div class="stack animate-slide-up page-empty">
    <div style="font-size:3rem;line-height:1;">✓</div>
    <div>
      <h2 class="mb-2">כל הכרטיסים עודכנו!</h2>
      <p style="font-size:var(--text-sm);color:var(--muted-fg);">אין שאלות לחזרה היום. חזור מחר או המשך ללמוד.</p>
    </div>
    {% if next_due_days %}
    <div class="card card-narrow center-text">
      <div class="text-xs muted semibold mb-1">החזרה הבאה</div>
      <div class="text-xl bold accent">
        {% if next_due_days == 1 %}מחר{% else %}בעוד {{ next_due_days }} ימים{% endif %}
      </div>
      <div class="text-xs muted mt-1">{{ next_due_count }} כרטיסים</div>
    </div>
    {% endif %}
    <div class="stack-sm narrow-centered">
      <a href="{{ url_for('student.revision') }}" class="btn btn-primary btn-block">חזרה לתפריט</a>
      <a href="{{ url_for('student.parcours') }}" class="btn btn-outline btn-block">להמשיך ללמוד</a>
    </div>
  </div>
{% else %}
  <div id="player" class="animate-slide-up"
       data-questions='{{ questions | tojson }}'
       data-parcours-url="{{ url_for('student.parcours') }}"
       data-home-url="{{ url_for('student.home') }}"
       data-answer-url="{{ url_for('api.answer') }}"
       data-today-stats-url="{{ url_for('student.today_stats') }}"
       data-subject="חזרה"
       data-siman="יומית"
       data-streak="{{ profile.streak_days or 0 }}"
       data-revision="true"
       data-mode="revision_daily"
       data-mode-label="חזרה יומית"
       data-back-url="{{ url_for('student.revision') }}"></div>
  <script src="{{ url_for('static', filename='js/chapitre.js') }}"></script>
{% endif %}
{% endblock %}
```

- [x] **Step 3: Supprimer l'ancien `templates/student/revision.html`**

Run: `rm "templates/student/revision.html"` (ou `Remove-Item templates\student\revision.html` en PowerShell) — son contenu a été déplacé vers `revision_jour.html` au Step 2, et la route `revision()` (Task 4) rend maintenant `revision_hub.html`.

- [x] **Step 4: Créer `templates/student/revision_siman_list.html`**

```html
{% extends "student/_layout.html" %}
{% from "_icons.html" import icon_book, icon_check %}
{% block title %}חזרה לפי סימן — סמיכה{% endblock %}
{% block content %}
<div class="animate-slide-up">

  <div class="toc-title-block">
    <svg class="toc-ornament" viewBox="0 0 400 80" preserveAspectRatio="xMidYMid meet">
      <path d="M 20 40 Q 40 20 80 40 T 160 40" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      <path d="M 200 10 L 210 25 L 220 35 L 210 45 L 200 60 L 190 45 L 180 35 L 190 25 Z" fill="currentColor"/>
      <path d="M 220 40 Q 240 20 280 40 T 380 40" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>
    <div class="toc-title-inner">
      <p class="toc-title-heb">חזרה לפי סימן</p>
    </div>
    <svg class="toc-ornament toc-ornament-bottom" viewBox="0 0 400 80" preserveAspectRatio="xMidYMid meet">
      <path d="M 20 40 Q 40 60 80 40 T 160 40" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      <path d="M 200 70 L 210 55 L 220 45 L 210 35 L 200 20 L 190 35 L 180 45 L 190 55 Z" fill="currentColor"/>
      <path d="M 220 40 Q 240 60 280 40 T 380 40" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>
  </div>

  {% if not groups %}
    <div class="stack page-empty">
      <div style="color:var(--muted);">{{ icon_book(48) }}</div>
      <div>
        <h2 class="mb-2">עוד אין כרטיסים שנלמדו</h2>
        <p style="font-size:var(--text-sm);color:var(--muted);">למד כמה שאלות דרך המסלול, ואז תוכל לחזור עליהן כאן.</p>
      </div>
    </div>
  {% else %}
    {% for g in groups %}
    {% for s in g.simanim %}
    <details class="siman-item" {{ 'open' if loop.first and loop.index0 == 0 }}>
      <summary>
        <div class="toc-chapter-marker">
          <span class="toc-marker-rule"></span>
          <span class="toc-marker-num">{{ s.siman | to_hebrew }}</span>
          <span class="toc-marker-rule"></span>
        </div>
        <div class="toc-chapter-subject">{{ g.subject }}</div>
      </summary>
      <div class="seif-chips">
        {% if s.seifim %}
          {% for sf in s.seifim %}
          <a href="{{ url_for('student.revision_siman_detail', subject=g.subject, siman=s.siman) }}"
             class="seif-chip">
            <span class="seif-chip-num">{{ sf.seif | to_hebrew }}</span>
            <span class="seif-chip-count">{{ sf.count }}</span>
          </a>
          {% endfor %}
        {% else %}
          <p style="font-size:var(--text-sm);color:var(--muted);">אין סעיפים</p>
        {% endif %}
      </div>
    </details>
    {% endfor %}
    {% endfor %}
  {% endif %}

</div>
{% endblock %}
```

- [x] **Step 5: Créer `templates/student/revision_sujet_list.html`**

```html
{% extends "student/_layout.html" %}
{% from "_icons.html" import icon_target %}
{% block title %}חזרה לפי נושא — סמיכה{% endblock %}
{% block content %}
<div class="stack animate-slide-up">
  <h2 class="mb-2">חזרה לפי נושא</h2>

  {% if not subjects %}
    <div class="stack page-empty">
      <div style="color:var(--muted);">{{ icon_target(48) }}</div>
      <div>
        <h2 class="mb-2">עוד אין נושא עם מספיק כרטיסים</h2>
        <p style="font-size:var(--text-sm);color:var(--muted);">נדרשים לפחות 3 כרטיסים שנלמדו באותו נושא כדי שיופיע כאן.</p>
      </div>
    </div>
  {% else %}
    <div class="stack-sm">
      {% for s in subjects %}
      <a href="{{ url_for('student.revision_sujet_detail', subject=s.subject) }}" class="folio-action">
        <div class="folio-action-body">
          <div class="folio-action-title">{{ s.subject }}</div>
          <div class="folio-action-sub">{{ s.count }} כרטיסים שנלמדו</div>
        </div>
        <div class="folio-action-arrow">‹</div>
      </a>
      {% endfor %}
    </div>
  {% endif %}
</div>
{% endblock %}
```

- [x] **Step 6: Modifier `templates/student/chapitre.html` pour accepter `mode`/`mode_label`/`is_revision`/`back_url`**

Remplacer :

```html
    <div id="player" class="animate-slide-up"
         data-questions='{{ questions | tojson }}'
         data-parcours-url="{{ url_for('student.parcours') }}"
         data-home-url="{{ url_for('student.home') }}"
         data-answer-url="{{ url_for('api.answer') }}"
         data-today-stats-url="{{ url_for('student.today_stats') }}"
         data-subject="{{ subject }}"
         data-siman="{{ siman }}"
         data-streak="{{ profile.streak_days or 0 }}"></div>
```

par :

```html
    <div id="player" class="animate-slide-up"
         data-questions='{{ questions | tojson }}'
         data-parcours-url="{{ url_for('student.parcours') }}"
         data-home-url="{{ url_for('student.home') }}"
         data-answer-url="{{ url_for('api.answer') }}"
         data-today-stats-url="{{ url_for('student.today_stats') }}"
         data-subject="{{ subject }}"
         data-siman="{{ siman }}"
         data-streak="{{ profile.streak_days or 0 }}"
         data-revision="{{ 'true' if is_revision | default(false) else 'false' }}"
         data-mode="{{ mode | default('study') }}"
         data-mode-label="{{ mode_label | default('') }}"
         data-back-url="{{ back_url if back_url is defined and back_url else url_for('student.parcours') }}"></div>
```

Note : `chapitre()` et `chapitre_seif()` (routes existantes, non modifiées) ne passent pas `mode`/`mode_label`/`is_revision`/`back_url` — les valeurs par défaut (`"study"`, `""`, `false`, `parcours`) reproduisent exactement le comportement actuel.

- [x] **Step 7: Mettre à jour le lien "חזרה יומית" de `home.html` vers la route directe**

Dans `templates/student/home.html`, remplacer :

```html
    <a href="{{ url_for('student.revision') }}" class="folio-action">
      <div class="folio-action-body">
        <div class="folio-action-title row gap-1">
          חזרה יומית
```

par :

```html
    <a href="{{ url_for('student.revision_jour') }}" class="folio-action">
      <div class="folio-action-body">
        <div class="folio-action-title row gap-1">
          חזרה יומית
```

- [x] **Step 8: Élargir le surlignage actif de l'onglet "חזרה" dans `_layout.html`**

Dans `templates/student/_layout.html`, remplacer :

```html
      <a href="{{ url_for('student.revision') }}" class="{{ 'active' if request.endpoint == 'student.revision' }}">
        {{ icon_repeat() }}<span>חזרה</span></a>
```

par :

```html
      <a href="{{ url_for('student.revision') }}" class="{{ 'active' if request.endpoint and request.endpoint.startswith('student.revision') }}">
        {{ icon_repeat() }}<span>חזרה</span></a>
```

(le tab reste actif quel que soit le sous-mode de révision visité).

- [x] **Step 9: Vérification manuelle**

Run: `python app.py`. Se connecter comme `student@example.com`. Naviguer :
- `/app/home` → le lien "חזרה יומית" doit mener directement à `/app/revision/jour`.
- Onglet nav "חזרה" en bas → doit mener à `/app/revision` (hub avec 4 cartes) et rester surligné actif sur toutes les sous-pages `/app/revision/*`.
- `/app/revision` → 4 cartes s'affichent, avec badges corrects (due_count, eligible_subjects).
- `/app/revision/siman` → si l'étudiant de démo n'a encore répondu à aucune question, l'état vide doit s'afficher (message "עוד אין כרטיסים שנלמדו"). Répondre à quelques questions via `/app/parcours` d'abord, puis revérifier que les simanim/seifim apparaissent.
- `/app/revision/sujet` → nécessite ≥3 cartes apprises dans un même sujet pour apparaître ; vérifier l'état vide et l'état peuplé.
- `/app/revision/aleatoire` → doit lancer une session avec ≤10 cartes.
- Vérifier l'alignement RTL sur les 3 nouveaux templates (titres, chips, listes) — pas de texte qui déborde ou s'inverse mal.

- [x] **Step 10: Commit**

```bash
git add templates/student/revision_hub.html templates/student/revision_jour.html \
        templates/student/revision_siman_list.html templates/student/revision_sujet_list.html \
        templates/student/chapitre.html templates/student/home.html templates/student/_layout.html
git rm templates/student/revision.html
git commit -m "feat: add revision hub + siman/sujet templates, wire chapitre.html for revision modes"
```

---

### Task 6 : Front-end — `chapitre.js` (mode, label, bonus quotidien)

**Files:**
- Modify: `static/js/chapitre.js`

**Interfaces:**
- Consumes: `data-mode`, `data-mode-label`, `data-back-url` (Task 5) ; réponse JSON de `/api/answer` incluant `daily_bonus` (Task 3).
- Produces: `POST /api/answer` envoie désormais `mode` dans son payload.

- [x] **Step 1: Lire les nouveaux attributs `data-*` dans `cfg`**

Remplacer :

```javascript
  const cfg = {
    parcours: root.dataset.parcoursUrl,
    home: root.dataset.homeUrl,
    answer: root.dataset.answerUrl,
    todayStats: root.dataset.todayStatsUrl,
    subject: root.dataset.subject,
    siman: root.dataset.siman,
  };

  const isRevision = root.dataset.revision === "true";
```

par :

```javascript
  const cfg = {
    parcours: root.dataset.parcoursUrl,
    home: root.dataset.homeUrl,
    answer: root.dataset.answerUrl,
    todayStats: root.dataset.todayStatsUrl,
    subject: root.dataset.subject,
    siman: root.dataset.siman,
    mode: root.dataset.mode || "study",
    modeLabel: root.dataset.modeLabel || "חזרה",
    back: root.dataset.backUrl || root.dataset.parcoursUrl,
  };

  const isRevision = root.dataset.revision === "true";
```

- [x] **Step 2: Ajouter l'état pour le bonus quotidien accumulé**

Remplacer :

```javascript
  const state = {
    idx: 0,
    combo: 0,
    sessionPoints: 0,
    correctCount: 0,
    results: new Array(origQuestions.length).fill(null),
    chosen: null,
    opinionAnswers: {},
    revealed: false,
    feedback: null,
    showNext: false,
    start: Date.now(),
  };
```

par :

```javascript
  const state = {
    idx: 0,
    combo: 0,
    sessionPoints: 0,
    correctCount: 0,
    dailyBonus: 0,
    results: new Array(origQuestions.length).fill(null),
    chosen: null,
    opinionAnswers: {},
    revealed: false,
    feedback: null,
    showNext: false,
    start: Date.now(),
  };
```

- [x] **Step 3: Envoyer `mode` dans le payload de `/api/answer` et accumuler le bonus**

Remplacer :

```javascript
    let data;
    try {
      const res = await fetch(cfg.answer, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_id: q.id, given_answer: key, response_time_ms: elapsed, combo: state.combo,
        }),
      });
      data = await res.json();
    } catch (e) {
      data = { is_correct: guessCorrect, correct_key: nq.correctKey, points: 0,
               combo: guessCorrect ? state.combo + 1 : 0,
               explanation: nq.explanation, seif: q.seif, rating_badge: "", rating_tone: "" };
    }

    state.combo = data.combo;
    state.results[origIdx] = data.is_correct ? "correct" : "wrong";
```

par :

```javascript
    let data;
    try {
      const res = await fetch(cfg.answer, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_id: q.id, given_answer: key, response_time_ms: elapsed, combo: state.combo,
          mode: cfg.mode,
        }),
      });
      data = await res.json();
    } catch (e) {
      data = { is_correct: guessCorrect, correct_key: nq.correctKey, points: 0,
               combo: guessCorrect ? state.combo + 1 : 0,
               explanation: nq.explanation, seif: q.seif, rating_badge: "", rating_tone: "", daily_bonus: 0 };
    }

    state.combo = data.combo;
    state.results[origIdx] = data.is_correct ? "correct" : "wrong";
    if (data.daily_bonus) state.dailyBonus += data.daily_bonus;
```

- [x] **Step 4: Bouton de fin de session générique (plus "יומית" en dur)**

Remplacer :

```javascript
  function nextButton() {
    const isLast = state.idx + 1 >= queue.length;
    const btn = document.createElement("button");
    btn.className = "btn btn-primary btn-block btn-lg animate-slide-up mt-5";
    btn.textContent = isLast
      ? (isRevision ? "סיים חזרות יומיות" : "סיים סימן")
      : "שאלה הבאה ←";
    btn.addEventListener("click", next);
    return btn;
  }
```

par :

```javascript
  function nextButton() {
    const isLast = state.idx + 1 >= queue.length;
    const btn = document.createElement("button");
    btn.className = "btn btn-primary btn-block btn-lg animate-slide-up mt-5";
    btn.textContent = isLast
      ? (isRevision ? "סיים חזרה" : "סיים סימן")
      : "שאלה הבאה ←";
    btn.addEventListener("click", next);
    return btn;
  }
```

- [x] **Step 5: Généraliser l'écran de fin de révision (titre dynamique + affichage du bonus)**

Remplacer :

```javascript
    root.innerHTML = "";
    const wrap = el("div", "stack center-text animate-slide-up player-complete");

    const doneMark = el("div", {
      style: "height:4rem;width:4rem;border-radius:999px;background:var(--brand-dim);color:var(--brand);" +
        "display:flex;align-items:center;justify-content:center;margin:0 auto;",
    }, icon("check", 32));
    wrap.appendChild(doneMark);
    wrap.appendChild(el("h2", "text-2xl bold mt-4", "סיום חזרות היומיות!"));
    wrap.appendChild(el("p", "text-sm muted", "עשית עבודה מצוינת היום"));

    const grid = el("div", "grid grid-3 mt-6");

    const col1 = el("div", "card center-text");
    col1.appendChild(el("div", "text-2xl extrabold accent", "+" + data.points_today));
    col1.appendChild(el("div", "text-xs muted mt-1", "נקודות היום"));
    grid.appendChild(col1);

    const col2 = el("div", "card center-text");
    col2.appendChild(el("div", "text-2xl extrabold", String(data.cards_reviewed)));
    col2.appendChild(el("div", "text-xs muted mt-1", "כרטיסים"));
    grid.appendChild(col2);

    const col3 = el("div", "card center-text");
    const pct = data.cards_reviewed
      ? Math.round((data.correct_today / data.cards_reviewed) * 100)
      : 0;
    col3.appendChild(el("div", "text-2xl extrabold success", pct + "%"));
    col3.appendChild(el("div", "text-xs muted mt-1", "דיוק"));
    grid.appendChild(col3);

    wrap.appendChild(grid);
```

par :

```javascript
    root.innerHTML = "";
    const wrap = el("div", "stack center-text animate-slide-up player-complete");

    const doneMark = el("div", {
      style: "height:4rem;width:4rem;border-radius:999px;background:var(--brand-dim);color:var(--brand);" +
        "display:flex;align-items:center;justify-content:center;margin:0 auto;",
    }, icon("check", 32));
    wrap.appendChild(doneMark);
    wrap.appendChild(el("h2", "text-2xl bold mt-4", "סיום " + cfg.modeLabel + "!"));
    wrap.appendChild(el("p", "text-sm muted", "עשית עבודה מצוינת היום"));

    if (state.dailyBonus > 0) {
      const bonusPill = el("div", "pill pill-accent animate-pop-in mt-3", icon("flame", 14), "בונוס השלמה יומית +" + state.dailyBonus);
      wrap.appendChild(bonusPill);
    }

    const grid = el("div", "grid grid-3 mt-6");

    const col1 = el("div", "card center-text");
    col1.appendChild(el("div", "text-2xl extrabold accent", "+" + data.points_today));
    col1.appendChild(el("div", "text-xs muted mt-1", "נקודות היום"));
    grid.appendChild(col1);

    const col2 = el("div", "card center-text");
    col2.appendChild(el("div", "text-2xl extrabold", String(data.cards_reviewed)));
    col2.appendChild(el("div", "text-xs muted mt-1", "כרטיסים"));
    grid.appendChild(col2);

    const col3 = el("div", "card center-text");
    const pct = data.cards_reviewed
      ? Math.round((data.correct_today / data.cards_reviewed) * 100)
      : 0;
    col3.appendChild(el("div", "text-2xl extrabold success", pct + "%"));
    col3.appendChild(el("div", "text-xs muted mt-1", "דיוק"));
    grid.appendChild(col3);

    wrap.appendChild(grid);
```

- [x] **Step 6: Utiliser `cfg.back` pour le bouton retour**

Remplacer :

```javascript
    backBtn.addEventListener("click", () => { window.location.href = cfg.parcours; });
```

par :

```javascript
    backBtn.addEventListener("click", () => { window.location.href = cfg.back; });
```

- [x] **Step 7: Afficher le libellé de mode générique dans l'en-tête (au lieu de "חזרה יומית" en dur)**

Remplacer :

```javascript
    if (isRevision) {
      const revLabel = el("span", "");
      revLabel.textContent = "חזרה יומית";
      revLabel.style.cssText = "font-family:'Secular One',sans-serif;font-size:var(--text-sm);color:var(--muted);";
      header.appendChild(revLabel);
    } else {
      header.appendChild(el("div", "pill pill-accent", icon("coin", 14), String(state.sessionPoints)));
    }
```

par :

```javascript
    if (isRevision) {
      const revLabel = el("span", "");
      revLabel.textContent = cfg.modeLabel;
      revLabel.style.cssText = "font-family:'Secular One',sans-serif;font-size:var(--text-sm);color:var(--muted);";
      header.appendChild(revLabel);
    } else {
      header.appendChild(el("div", "pill pill-accent", icon("coin", 14), String(state.sessionPoints)));
    }
```

- [x] **Step 8: Vérification manuelle en navigateur**

Run: `python app.py`. Se connecter comme `student@example.com`.
1. Répondre à toutes les cartes dues via `/app/revision/jour` → l'écran de fin doit afficher "סיום חזרה יומית!" et, si c'est un jour de complétion, le pill "בונוס השלמה יומית +150" (ou plus selon le streak).
2. Faire une session `/app/revision/siman/<subject>/<siman>` (via un siman déjà appris) → écran de fin doit afficher "סיום חזרה לפי סימן!" sans pill de bonus (mode non-jour).
3. Faire une session `/app/revision/aleatoire` → écran de fin "סיום חזרה אקראית!".
4. Vérifier que la flèche retour en haut de chaque session renvoie bien vers la bonne liste (siman → liste siman, sujet → liste sujet, aléatoire/jour → hub).
5. Vérifier `/app/chapitre/<subject>/<siman>` (étude normale, hors révision) — comportement strictement identique à avant (pas de régression sur le flux principal d'apprentissage).

- [x] **Step 9: Commit**

```bash
git add static/js/chapitre.js
git commit -m "feat: chapitre.js sends revision mode to the API, shows daily completion bonus"
```

---

### Task 7 : Vérification end-to-end + nettoyage

**Files:**
- Aucun fichier nouveau — vérification manuelle complète du parcours (règle du `README.md` : ne pas déclarer une modification terminée sans avoir navigué dans les pages impactées).

- [x] **Step 1: Rejouer la suite de tests automatisés complète**

Run: `python -m pytest tests/ -v`
Expected: tous les tests passent (`test_fsrs.py`, `test_calibration.py`, `test_points.py`).

- [x] **Step 2: Parcours complet en navigateur (étudiant de démo)**

Avec `python app.py` lancé et connecté comme `student@example.com` :
1. `/app/home` → vérifier badge streak, badge points, lien "חזרה יומית" fonctionnel.
2. `/app/parcours` → répondre à quelques questions dans 2-3 simanim différents (pour peupler les modes siman/sujet/aléatoire).
3. `/app/revision` (hub) → les 4 cartes affichent des compteurs cohérents avec ce qui vient d'être appris.
4. Tester les 4 modes de bout en bout (jour / siman / sujet / aléatoire), en vérifiant à chaque fois :
   - Les points affichés pendant la session correspondent à l'ordre de grandeur attendu (≤30 en mode jour, ≤8 dans les 3 autres).
   - L'écran de fin de session affiche le bon libellé.
   - Le bonus quotidien ne s'affiche qu'en mode jour, et seulement quand toutes les cartes dues du jour sont épuisées.
5. `/app/profil` et `/app/settings` → vérifier qu'ils s'affichent normalement (non touchés par ce plan, contrôle de non-régression).
6. Recharger `/app/home` après une session de révision du jour complète → `total_points` doit refléter le bonus de complétion.

- [x] **Step 3: Vérifier le cas "aucune carte due" sur `/app/revision/jour`**

Utiliser `/app/advance-revisions` (outil de test existant) pour vider la file du jour, puis revisiter `/app/revision/jour` → l'état vide doit s'afficher avec un lien "חזרה לתפריט" fonctionnel vers le hub.

- [x] **Step 4: Vérifier le RTL sur les 3 nouveaux templates**

Zoomer/inspecter `/app/revision`, `/app/revision/siman`, `/app/revision/sujet` — texte hébreu aligné à droite, chips/badges non coupés, pas de débordement horizontal.

- [x] **Step 5: Mettre à jour le README si nécessaire**

Si de nouvelles routes publiques changent la liste documentée dans `README.md` (section "Routes et API"), ajouter les nouvelles routes `/app/revision/jour`, `/app/revision/siman[/…]`, `/app/revision/sujet[/…]`, `/app/revision/aleatoire` au tableau existant, et documenter le champ `mode` optionnel de `POST /api/answer` dans la section correspondante.

- [x] **Step 6: Commit final**

```bash
git add README.md
git commit -m "docs: document revision modes routes and /api/answer mode field"
```

---

## Self-Review

**1. Couverture de la spec :**
- Hub + 4 modes → Tasks 4-5. ✅
- 3 formules de points distinctes (étude / jour / stabilité) → Task 2. ✅
- Suppression du multiplicateur streak → Task 2 (`compute_points` sans `streak_days`). ✅
- Bonus de complétion quotidienne + streak dédié → Task 1 (colonnes) + Task 3 (logique). ✅
- Filtrage "déjà appris" pour siman/sujet/aléatoire → Task 4 (`_learned_question_ids`). ✅
- Seuil ≥3 cartes pour le mode sujet → Task 4 (`revision_sujet`/hub). ✅
- Max 10 cartes aléatoires, resélectionnées à chaque fois → Task 4 (`random.sample`, pas de graine fixe, requête relancée à chaque visite). ✅
- Utilisation de `retrievability` (pas de constante arbitraire) → Task 2/3. ✅
- Migration DB idempotente suivant le patron existant → Task 1. ✅

**2. Placeholders :** aucun "TODO"/"TBD" — toutes les étapes contiennent du code complet.

**3. Cohérence des types/signatures :**
- `compute_points(is_correct, difficulty, speed, combo)` (4 args, sans `streak_days`) — cohérent entre Task 2 (définition) et Task 3 (appel).
- `compute_daily_points(is_correct, days_since_last_review, combo)` et `compute_stability_points(is_correct, retrievability, combo)` — cohérents entre Task 2 et Task 3.
- `mode` valeurs (`"study"`, `"revision_daily"`, `"revision_siman"`, `"revision_sujet"`, `"revision_random"`) — identiques dans Task 3 (dispatch), Task 4 (routes qui les passent au template), Task 5 (`data-mode`), Task 6 (`cfg.mode` envoyé au fetch).
- `daily_bonus` — présent dans la réponse JSON (Task 3), lu par `chapitre.js` (Task 6).
- Routes Flask (`student.revision_jour`, `student.revision_siman`, `student.revision_siman_detail`, `student.revision_sujet`, `student.revision_sujet_detail`, `student.revision_aleatoire`) — noms identiques entre définition (Task 4) et tous les `url_for(...)` dans les templates (Task 5).

---

**Plan complete and saved to `docs/superpowers/plans/2026-07-05-revision-modes.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — je dispatche un subagent frais par tâche, avec revue entre chaque tâche, itération rapide.
2. **Inline Execution** — j'exécute les tâches dans cette session avec executing-plans, exécution par lot avec points de contrôle.

Quelle approche préférez-vous ?
